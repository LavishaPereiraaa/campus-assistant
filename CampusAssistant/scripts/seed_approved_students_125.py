from __future__ import annotations

import os
import random
import string
import sys
from datetime import date, timedelta
from typing import Dict, List, Tuple

import mysql.connector

# Allow running this script from anywhere (so `import database.db` works)
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Reuse existing env-loading logic
from database.db import get_db_config


def _rand_str(n: int) -> str:
    return "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(n))


def _seed_students(limit: int, image_path: str) -> None:
    cfg = get_db_config()
    conn = mysql.connector.connect(**cfg)
    try:
        conn.start_transaction()
        cur = conn.cursor()

        # Departments present in semester_subjects
        cur.execute(
            """
            SELECT DISTINCT department
            FROM semester_subjects
            ORDER BY department
            """
        )
        departments = [r[0] for r in cur.fetchall()]
        if not departments:
            raise RuntimeError("No departments found in semester_subjects; seed subjects first.")

        # All semesters in semester_subjects
        cur.execute(
            """
            SELECT DISTINCT semester_number
            FROM semester_subjects
            ORDER BY semester_number
            """
        )
        semesters = [r[0] for r in cur.fetchall()]
        if not semesters:
            raise RuntimeError("No semesters found in semester_subjects; seed subjects first.")

        # Map (department, semester) -> list of (subject_name, subject_code)
        cur.execute(
            """
            SELECT department, semester_number, subject_name, subject_code
            FROM semester_subjects
            ORDER BY department, semester_number, subject_name
            """
        )
        rows = cur.fetchall()
        subj_map: Dict[Tuple[str, int], List[Tuple[str, str | None]]] = {}
        for dept, sem, sname, scode in rows:
            subj_map.setdefault((dept, int(sem)), []).append((sname, scode))

        # Determine starting point to avoid student_id collisions
        # We'll use student_id like "S{dept_short}{seq:03d}"
        # (No need to "touch" DB with COUNT; leaving unread results can break subsequent queries.)

        # Generate and insert students
        created = 0
        used_student_ids = set()
        # Load existing student_ids to be safe
        cur.execute("SELECT student_id FROM approved_students")
        used_student_ids.update(r[0] for r in cur.fetchall())

        # Distribute students roughly evenly across departments.
        # IMPORTANT: if student_id collides, we must keep trying until we seed `limit`.
        created = 0
        seq = 1
        attempts = 0
        max_attempts = max(50, limit * 20)

        while created < limit and attempts < max_attempts:
            attempts += 1

            dept = departments[(created + attempts) % len(departments)]

            name = f"Student {seq}"
            gender = random.choice(["Male", "Female"])
            dob = date.today() - timedelta(days=random.randint(18 * 365, 25 * 365))
            email = f"student{seq}@example.com"
            password = "pass123"

            # For image icon: seed same uploaded file for all
            # UI expects image_path under static/, with or without 'uploads/' prefix.
            # Templates in department_dashboard.html add 'uploads/' if missing.
            # We'll store without leading slash and without "static/".
            if image_path.startswith("static/"):
                stored_image_path = image_path[len("static/") :]
            else:
                stored_image_path = image_path

            # Insert approved student
            cur.execute(
                """
                INSERT INTO approved_students
                  (student_id, name, password, gender, date_of_birth, email, image_path, department)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    student_id,
                    name,
                    password,
                    gender,
                    dob,
                    email,
                    stored_image_path,
                    dept,
                ),
            )
            used_student_ids.add(student_id)

            # Seed attendance + results across semesters/subjects
            student_subjects_sem = 0
            for sem in semesters:
                subj_list = subj_map.get((dept, int(sem)), [])
                if not subj_list:
                    continue

                # Attendance per subject
                # We'll create a small set of attendance rows per subject (1..3 records)
                for (subject_name, _subject_code) in subj_list:
                    # create 1..2 attendance records per subject
                    records_n = random.choice([1, 2])
                    for _k in range(records_n):
                        attendance_date = date.today() - timedelta(days=random.randint(1, 120))

                        # Bias attendance to produce both eligibility outcomes:
                        # - about half of students/subjects below 75%
                        # - about half at/above 75%
                        if random.random() < 0.5:
                            # below 75 (keep a reasonable range)
                            attendance_percent = random.randint(40, 74)
                        else:
                            # >= 75
                            attendance_percent = random.randint(75, 98)

                        cur.execute(
                            """
                            INSERT INTO student_attendance_records
                              (department, semester_number, subject, attendance_date, student_id, attendance_percent)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON DUPLICATE KEY UPDATE
                              attendance_percent=VALUES(attendance_percent),
                              attendance_date=VALUES(attendance_date)
                            """,
                            (
                                dept,
                                int(sem),
                                subject_name,
                                attendance_date,
                                student_id,
                                attendance_percent,
                            ),
                        )

                # Results per subject
                for (subject_name, _subject_code) in subj_list:
                    max_marks = 100

                    # Bias marks to produce both backlog and pass results:
                    # - about 40% below 40 (backlog)
                    # - about 60% passing (>=40)
                    if random.random() < 0.4:
                        marks = random.randint(0, 39)
                    else:
                        marks = random.randint(40, 100)

                    cur.execute(
                        """
                        INSERT INTO student_results
                          (student_id, department, semester_number, subject_name, marks, max_marks)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                          marks=VALUES(marks),
                          max_marks=VALUES(max_marks)
                        """,
                        (
                            student_id,
                            dept,
                            int(sem),
                            subject_name,
                            marks,
                            max_marks,
                        ),
                    )
                    student_subjects_sem += 1

            created += 1
            if created >= limit:
                break

        conn.commit()
        print(f"Seeded {created} approved students (with attendance + results).")
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def main() -> None:
    # Use the uploaded JPG path you provided
    image_path = "static/uploads/360_F_123093367_c7WoJ0uHCkepbgLasnGFBKK8sSNiJw6l.jpg"
    _seed_students(limit=125, image_path=image_path)


if __name__ == "__main__":
    main()
