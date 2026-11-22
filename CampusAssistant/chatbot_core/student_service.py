"""Student DB answerers (DB-only)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .db import fetch_all_dict, fetch_one_dict


def require_student_exists(student_id: str, department: str) -> bool:
    row = fetch_one_dict(
        """
        SELECT 1 FROM approved_students
        WHERE student_id=%s AND department=%s
        """,
        (student_id, department),
    )
    return row is not None


def get_profile(student_id: str, department: str) -> str:
    row = fetch_one_dict(
        """
        SELECT student_id, name, email, image_path, department
        FROM approved_students
        WHERE student_id=%s AND department=%s
        """,
        (student_id, department),
    )
    if not row:
        return "The requested information is currently unavailable."

    return (
        "👤 Student Profile\n"
        f"Name: {row.get('name','-')}\n"
        f"Student ID: {row.get('student_id','-')}\n"
        f"Department: {row.get('department','-')}\n"
        f"Email: {row.get('email','-')}"
    )


def get_attendance_summary(student_id: str, department: str) -> str:
    row = fetch_one_dict(
        """
        SELECT AVG(attendance_percent) as avg_att
        FROM student_attendance_records
        WHERE student_id=%s AND department=%s
        """,
        (student_id, department),
    )
    if not row or row.get("avg_att") is None:
        return "The requested information is currently unavailable."

    return (
        "📚 Attendance Summary\n"
        f"Overall Attendance: {round(row['avg_att'], 1)}%"
    )


def get_marks_and_result(student_id: str, department: str) -> str:
    sem_rows = fetch_all_dict(
        """
        SELECT semester_number,
               SUM(marks) as total_points,
               SUM(max_marks) as total_max,
               ROUND((SUM(marks)/NULLIF(SUM(max_marks),0))*100, 1) as avg_percent
        FROM student_results
        WHERE student_id=%s AND department=%s
        GROUP BY semester_number
        ORDER BY semester_number
        """,
        (student_id, department),
    )
    if not sem_rows:
        return "The requested information is currently unavailable."

    # CGPA from totals
    totals = fetch_one_dict(
        """
        SELECT SUM(marks) as total_points, SUM(max_marks) as total_max
        FROM student_results
        WHERE student_id=%s AND department=%s
        """,
        (student_id, department),
    )
    cgpa = None
    if totals and totals.get("total_max") and totals["total_max"] > 0:
        cgpa = round((totals['total_points'] / totals['total_max']) * 10, 2)

    lines = [f"Semester {r['semester_number']}: {r.get('avg_percent','-')}%" for r in sem_rows]

    return (
        "📊 Semester Result Summary\n" + "\n".join(lines) +
        (f"\n\nYour CGPA: {cgpa}" if cgpa is not None else "")
    )


def get_registered_subjects(student_id: str, department: str) -> str:
    # Use results join to ensure subject existence
    rows = fetch_all_dict(
        """
        SELECT sr.semester_number, sr.subject_name, sr.subject_code
        FROM (
            SELECT semester_number, subject_name, subject_code
            FROM semester_subjects
            WHERE department=%s
        ) ss
        JOIN student_results sr
          ON sr.department=%s
         AND sr.semester_number=ss.semester_number
         AND sr.subject_name=ss.subject_name
        WHERE sr.student_id=%s
        GROUP BY sr.semester_number, sr.subject_name, sr.subject_code
        ORDER BY sr.semester_number, sr.subject_name
        """,
        (department, department, student_id),
    )

    if not rows:
        return "The requested information is currently unavailable."

    grouped: Dict[Any, List[str]] = {}
    for r in rows:
        grouped.setdefault(r['semester_number'], []).append(r['subject_name'])

    parts = [f"Sem {sem}: {', '.join(names)}" for sem, names in sorted(grouped.items())]
    return "📚 Registered Subjects\n" + "\n".join(parts)


def get_timetable_sample(student_id: str, department: str) -> str:
    rows = fetch_all_dict(
        """
        SELECT day, subject
        FROM timetable_entries
        WHERE department=%s
        ORDER BY FIELD(day,'Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'), id
        LIMIT 25
        """,
        (department,),
    )
    if not rows:
        return "The requested information is currently unavailable."

    grouped: Dict[str, List[str]] = {}
    for r in rows:
        grouped.setdefault(r['day'], []).append(r['subject'])

    parts = [f"{d}: {', '.join(subs)}" for d, subs in grouped.items()]
    return "🗓️ Timetable (Sample)\n" + "\n".join(parts)


def get_placements(student_id: str, department: str) -> str:
    rows = fetch_all_dict(
        """
        SELECT company, package
        FROM placements
        WHERE department=%s
        ORDER BY company
        LIMIT 8
        """,
        (department,),
    )
    if not rows:
        return "The requested information is currently unavailable."

    drives = ", ".join([f"{r['company']} ({r['package']})" for r in rows])
    return "📌 Top Placement Drives\n" + drives


def get_subject_attendance(student_id: str, department: str) -> str:
    """Get attendance broken down by subject."""
    rows = fetch_all_dict(
        """
        SELECT subject, ROUND(AVG(attendance_percent), 1) as avg_att
        FROM student_attendance_records
        WHERE student_id=%s AND department=%s
        GROUP BY subject
        ORDER BY avg_att ASC
        """,
        (student_id, department),
    )
    if not rows:
        return "No subject-wise attendance data available."

    lines = [f"{r['subject']}: {r['avg_att']}%" for r in rows]
    return "📚 Subject-wise Attendance\n" + "\n".join(lines)


def get_lowest_attendance_subject(student_id: str, department: str) -> str:
    """Get the subject with lowest attendance."""
    row = fetch_one_dict(
        """
        SELECT subject, ROUND(AVG(attendance_percent), 1) as avg_att
        FROM student_attendance_records
        WHERE student_id=%s AND department=%s
        GROUP BY subject
        ORDER BY avg_att ASC
        LIMIT 1
        """,
        (student_id, department),
    )
    if not row:
        return "No attendance data available."

    return f"{row['subject']} has the lowest attendance at {row['avg_att']}%."


def get_classes_to_attend(student_id: str, department: str) -> str:
    """Calculate classes needed to reach 75% attendance."""
    rows = fetch_all_dict(
        """
        SELECT subject,
               SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as present,
               COUNT(*) as total,
               ROUND(AVG(attendance_percent), 1) as avg_att
        FROM student_attendance_records
        WHERE student_id=%s AND department=%s
        GROUP BY subject
        """,
        (student_id, department),
    )
    if not rows:
        return "No attendance data available."

    needed = []
    for r in rows:
        if r['avg_att'] < 75:
            # Need 75% - current
            needed_classes = max(0, int((0.75 * r['total']) - r['present']))
            if needed_classes > 0:
                needed.append(f"{r['subject']}: {needed_classes} more classes")

    if not needed:
        return "You meet the 75% attendance requirement across all subjects."

    return "📚 Classes Needed to Reach 75%:\n" + "\n".join(needed)


def get_exams_list(student_id: str, department: str) -> str:
    """Get upcoming exams for the student."""
    rows = fetch_all_dict(
        """
        SELECT subject, exam_date
        FROM exam_schedule
        WHERE department=%s
        AND exam_date >= CURDATE()
        ORDER BY exam_date
        LIMIT 10
        """,
        (department,),
    )

    if not rows:
        return "No upcoming exams scheduled."

    lines = [f"{r['subject']} - {r['exam_date']}" for r in rows]

    return "📝 Upcoming Exams\n" + "\n".join(lines)


def get_exam_eligibility(student_id: str, department: str) -> str:
    """Check if student is eligible for exams based on attendance."""
    row = fetch_one_dict(
        """
        SELECT AVG(attendance_percent) as avg_att
        FROM student_attendance_records
        WHERE student_id=%s AND department=%s
        """,
        (student_id, department),
    )
    if not row or row.get("avg_att") is None:
        return "Unable to determine eligibility. Attendance data unavailable."

    avg_att = row['avg_att']
    if avg_att >= 75:
        return f"Yes! Your attendance ({round(avg_att, 1)}%) satisfies the minimum 75% requirement."
    else:
        return f"No. Your attendance ({round(avg_att, 1)}%) is below the 75% requirement."


def get_backlog_count(student_id: str, department: str) -> str:
    """Get count of backlogs."""
    row = fetch_one_dict(
        """
        SELECT COUNT(*) as backlog_count
        FROM student_results
        WHERE student_id=%s AND department=%s AND marks < 40
        """,
        (student_id, department),
    )
    if not row:
        return "No backlog data available."

    count = row.get("backlog_count", 0)
    return f"You have {count} backlog subject(s)."


def get_subjects_to_improve(student_id: str, department: str) -> str:
    """Get subjects where marks are below passing threshold."""
    rows = fetch_all_dict(
        """
        SELECT subject_name, marks, max_marks,
               ROUND((marks/max_marks)*100, 1) as pct
        FROM student_results
        WHERE student_id=%s AND department=%s AND marks < 40
        ORDER BY pct ASC
        """,
        (student_id, department),
    )
    if not rows:
        return "You have no subjects to improve. All subjects passed!"

    lines = [f"{r['subject_name']}: {r['marks']}/{r['max_marks']} ({r['pct']}%)" for r in rows]
    return "📚 Subjects to Improve:\n" + "\n".join(lines)


def get_timetable_today(student_id: str, department: str) -> str:
    """Get today's timetable."""
    rows = fetch_all_dict(
        """
        SELECT day, subject, time_slot
        FROM timetable_entries
        WHERE department=%s
        AND day = DAYNAME(CURDATE())
        ORDER BY id
        """,
        (department,),
    )
    if not rows:
        return "No classes scheduled for today."

    lines = [f"{r['time_slot']}: {r['subject']}" for r in rows]
    return "🗓️ Today's Timetable\n" + "\n".join(lines)


def get_timetable_full(student_id: str, department: str) -> str:
    """Get full weekly timetable (department-wide)."""
    rows = fetch_all_dict(
        """
        SELECT day, subject
        FROM timetable_entries
        WHERE department=%s
        ORDER BY FIELD(day,'Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'), id
        """,
        (department,),
    )
    if not rows:
        return "Timetable not available."

    # Group by day in the order we want to display
    by_day: dict = {}
    for r in rows:
        by_day.setdefault(r["day"], []).append(r["subject"])

    parts = []
    for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]:
        if day in by_day:
            parts.append(f"\n📅 {day}:\n" + "\n".join(by_day[day]))

    return "🗓️ Weekly Timetable" + "".join(parts)


def get_semester_result(student_id: str, department: str) -> str:
    """Get semester-by-semester results."""
    rows = fetch_all_dict(
        """
        SELECT semester_number,
               SUM(marks) as total_marks,
               SUM(max_marks) as total_max,
               ROUND((SUM(marks)/NULLIF(SUM(max_marks),0))*100, 1) as percentage
        FROM student_results
        WHERE student_id=%s AND department=%s
        GROUP BY semester_number
        ORDER BY semester_number
        """,
        (student_id, department),
    )
    if not rows:
        return "No semester results available."

    lines = [f"Semester {r['semester_number']}: {r['percentage']}%" for r in rows]
    return "📊 Semester Results\n" + "\n".join(lines)


def get_sgpa(student_id: str, department: str) -> str:
    """Get SGPA for current/last semester."""
    row = fetch_one_dict(
        """
        SELECT semester_number,
               SUM(marks) as total_marks,
               SUM(max_marks) as total_max,
               ROUND((SUM(marks)/NULLIF(SUM(max_marks),0))*10, 2) as sgpa
        FROM student_results
        WHERE student_id=%s AND department=%s
        GROUP BY semester_number
        ORDER BY semester_number DESC
        LIMIT 1
        """,
        (student_id, department),
    )
    if not row:
        return "No SGPA data available."

    return f"Your SGPA (Semester {row['semester_number']}): {row['sgpa']}"


def get_cgpa(student_id: str, department: str) -> str:
    """Get overall CGPA."""
    row = fetch_one_dict(
        """
        SELECT SUM(marks) as total_marks, SUM(max_marks) as total_max
        FROM student_results
        WHERE student_id=%s AND department=%s
        """,
        (student_id, department),
    )
    if not row or not row.get("total_max") or row["total_max"] == 0:
        return "No CGPA data available."

    cgpa = round((row['total_marks'] / row['total_max']) * 10, 2)
    return f"Your CGPA: {cgpa}"


def get_placement_status(student_id: str, department: str) -> str:
    """Get placement drive status."""
    rows = fetch_all_dict(
        """
        SELECT company, package, status
        FROM placements
        WHERE student_id=%s
        ORDER BY company
        """,
        (student_id,),
    )
    if not rows:
        return "You have not been shortlisted for any placements yet."

    lines = [f"{r['company']} - {r['package']} ({r['status']})" for r in rows]
    return "📌 Placement Status\n" + "\n".join(lines)


def get_placement_companies(student_id: str, department: str) -> str:
    """Get placement companies visiting for department."""
    rows = fetch_all_dict(
        """
        SELECT company, package, eligibility_criteria
        FROM placements
        WHERE department=%s
        ORDER BY package DESC
        LIMIT 10
        """,
        (department,),
    )
    if not rows:
        return "No placement drives currently scheduled."

    lines = [f"{r['company']} - {r['package']} LPA (Eligible: {r['eligibility_criteria']}%)" for r in rows]
    return "📌 Visiting Companies\n" + "\n".join(lines)


def get_full_information(student_id: str, department: str) -> str:
    # Compose from individual DB calls, all DB-only
    profile = get_profile(student_id, department)
    att = get_attendance_summary(student_id, department)
    res = get_marks_and_result(student_id, department)
    subj = get_registered_subjects(student_id, department)
    pl = get_placements(student_id, department)
    tt = get_timetable_sample(student_id, department)

    # If any are unavailable, we still compose but keep exact unavailable phrases
    return (
        "📌 Campus ERP — Full Student Information\n\n" +
        profile + "\n\n" +
        att + "\n\n" +
        res + "\n\n" +
        subj + "\n\n" +
        pl + "\n\n" +
        tt
    )

