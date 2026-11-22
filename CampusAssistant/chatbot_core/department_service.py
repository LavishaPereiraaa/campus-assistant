"""Department/admin DB answerers (DB-only)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


from .db import fetch_all_dict, fetch_one_dict


def get_departments_snapshot() -> str:
    return "The requested information is currently unavailable."


def get_students_below_attendance(department: str, threshold: float = 75.0) -> str:
    # Compute avg attendance per student in that department
    rows = fetch_all_dict(
        """
        SELECT s.student_id, s.name, AVG(a.attendance_percent) as avg_att
        FROM approved_students s
        JOIN student_attendance_records a
          ON a.student_id=s.student_id
         AND a.department=s.department
        WHERE s.department=%s
        GROUP BY s.student_id, s.name
        HAVING avg_att < %s
        ORDER BY avg_att ASC
        LIMIT 50
        """,
        (department, threshold),
    )
    if not rows:
        return "The requested information is currently unavailable."

    lines = [f"{r['name']} ({r['student_id']}): {round(r['avg_att'],1)}%" for r in rows]
    return "📉 Students with Attendance Below {thr}%\n".format(thr=threshold) + "\n".join(lines)


def get_all_students_with_backlogs(department: str) -> str:
    """Get all students with backlogs."""
    rows = fetch_all_dict(
        """
        SELECT s.student_id, s.name, COUNT(*) as backlog_count
        FROM approved_students s
        JOIN student_results r
          ON r.student_id=s.student_id AND r.department=s.department
        WHERE s.department=%s AND r.marks < 40
        GROUP BY s.student_id, s.name
        ORDER BY backlog_count DESC
        """,
        (department,),
    )
    if not rows:
        return "No students with backlogs found."

    lines = [f"{r['name']} ({r['student_id']}): {r['backlog_count']} backlogs" for r in rows]
    return "📚 Students with Backlogs\n" + "\n".join(lines)


def get_placement_statistics(department: str) -> str:
    """Get placement statistics for the department."""
    # Total placed
    placed_row = fetch_one_dict(
        """
        SELECT COUNT(DISTINCT student_id) as placed
        FROM placements
        WHERE department=%s AND status='Selected'
        """,
        (department,),
    )
    placed = placed_row.get("placed", 0) if placed_row else 0

    # Total companies
    comp_row = fetch_one_dict(
        """
        SELECT COUNT(DISTINCT company) as companies
        FROM placements
        WHERE department=%s
        """,
        (department,),
    )
    companies = comp_row.get("companies", 0) if comp_row else 0

    # Average package
    avg_row = fetch_one_dict(
        """
        SELECT AVG(package) as avg_package
        FROM placements
        WHERE department=%s
        """,
        (department,),
    )
    avg_pkg = round(avg_row["avg_package"], 2) if avg_row and avg_row.get("avg_package") else 0

    # Total students in department
    total_row = fetch_one_dict(
        """
        SELECT COUNT(*) as total
        FROM approved_students
        WHERE department=%s
        """,
        (department,),
    )
    total = total_row.get("total", 0) if total_row else 0

    placement_rate = round((placed / total) * 100, 1) if total > 0 else 0

    return (
        f"📊 Placement Statistics for {department}\n"
        f"Total Students: {total}\n"
        f"Students Placed: {placed}\n"
        f"Placement Rate: {placement_rate}%\n"
        f"Companies Visited: {companies}\n"
        f"Average Package: {avg_pkg} LPA"
    )


def get_attendance_report(department: str) -> str:
    """Generate department attendance report."""
    row = fetch_one_dict(
        """
        SELECT AVG(attendance_percent) as avg_att,
               MIN(attendance_percent) as min_att,
               MAX(attendance_percent) as max_att
        FROM student_attendance_records
        WHERE department=%s
        """,
        (department,),
    )
    if not row or row.get("avg_att") is None:
        return "No attendance data available."

    # Count below 75%
    below_row = fetch_one_dict(
        """
        SELECT COUNT(DISTINCT student_id) as below_count
        FROM student_attendance_records
        WHERE department=%s AND attendance_percent < 75
        """,
        (department,),
    )
    below = below_row.get("below_count", 0) if below_row else 0

    return (
        f"📈 Attendance Report - {department}\n"
        f"Average Attendance: {round(row['avg_att'], 1)}%\n"
        f"Highest: {round(row['max_att'], 1)}%\n"
        f"Lowest: {round(row['min_att'], 1)}%\n"
        f"Below 75%: {below} students"
    )


def get_semester_analytics(department: str) -> str:
    """Get semester-wise analytics."""
    rows = fetch_all_dict(
        """
        SELECT semester_number,
               AVG(marks) as avg_marks,
               MAX(marks) as max_marks,
               MIN(marks) as min_marks
        FROM student_results
        WHERE department=%s
        GROUP BY semester_number
        ORDER BY semester_number
        """,
        (department,),
    )
    if not rows:
        return "No semester analytics available."

    lines = [
        f"Semester {r['semester_number']}: Avg={round(r['avg_marks'],1)}%, Max={r['max_marks']}, Min={r['min_marks']}"
        for r in rows
    ]
    return "📊 Semester Analytics\n" + "\n".join(lines)


def get_students_by_semester(department: str, semester: int) -> str:
    """Get all students in a specific semester."""
    rows = fetch_all_dict(
        """
        SELECT s.student_id, s.name,
               ROUND((SUM(r.marks)/NULLIF(SUM(r.max_marks),0))*100, 1) as percentage
        FROM approved_students s
        JOIN student_results r
          ON r.student_id=s.student_id AND r.department=s.department
        WHERE s.department=%s AND r.semester_number=%s
        GROUP BY s.student_id, s.name
        ORDER BY percentage DESC
        """,
        (department, semester),
    )
    if not rows:
        return f"No student data found for Semester {semester}."

    lines = [f"{r['name']} ({r['student_id']}): {r['percentage']}%" for r in rows]
    return f"📚 Students in Semester {semester}\n" + "\n".join(lines)


def get_subject_performance(department: str, subject_name: str) -> str:
    """Get performance for a specific subject across all students."""
    rows = fetch_all_dict(
        """
        SELECT s.student_id, s.name, r.marks, r.max_marks,
               ROUND((r.marks/r.max_marks)*100, 1) as percentage
        FROM approved_students s
        JOIN student_results r
          ON r.student_id=s.student_id AND r.department=s.department
        WHERE r.department=%s AND r.subject_name LIKE %s
        ORDER BY percentage DESC
        LIMIT 30
        """,
        (department, f"%{subject_name}%"),
    )
    if not rows:
        return f"No performance data found for {subject_name}."

    lines = [f"{r['name']}: {r['percentage']}%" for r in rows]
    return f"📊 Performance - {subject_name}\n" + "\n".join(lines)


def get_failed_in_subject(department: str, subject_name: str) -> str:
    """Get students who failed a specific subject."""
    rows = fetch_all_dict(
        """
        SELECT s.student_id, s.name, r.marks, r.max_marks
        FROM approved_students s
        JOIN student_results r
          ON r.student_id=s.student_id AND r.department=s.department
        WHERE r.department=%s AND r.subject_name LIKE %s AND r.marks < 40
        ORDER BY r.marks ASC
        """,
        (department, f"%{subject_name}%"),
    )
    if not rows:
        return f"No students failed in {subject_name}."

    lines = [f"{r['name']} ({r['student_id']}): {r['marks']}/{r['max_marks']}" for r in rows]
    return f"❌ Failed in {subject_name}\n" + "\n".join(lines)


def get_department_timetable(department: str, semester: int = None) -> str:
    """Get timetable for department/semester."""
    if semester:
        rows = fetch_all_dict(
            """
            SELECT day, subject, time_slot, semester_number
            FROM timetable_entries
            WHERE department=%s AND semester_number=%s
            ORDER BY FIELD(day,'Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'), id
            """,
            (department, semester),
        )
        title = f"Semester {semester}"
    else:
        rows = fetch_all_dict(
            """
            SELECT day, subject, time_slot, semester_number
            FROM timetable_entries
            WHERE department=%s
            ORDER BY FIELD(day,'Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'), id
            """,
            (department,),
        )
        title = "All Semesters"

    if not rows:
        return "Timetable not available."

    by_day: dict = {}
    for r in rows:
        by_day.setdefault(r['day'], []).append(f"{r['time_slot']}: {r['subject']}")

    parts = []
    for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']:
        if day in by_day:
            parts.append(f"\n📅 {day}:\n" + "\n".join(by_day[day]))

    return f"🗓️ Timetable - {title}" + "".join(parts)


def get_today_schedule(department: str) -> str:
    """Get today's schedule for the department."""
    rows = fetch_all_dict(
        """
        SELECT day, subject, time_slot, semester_number
        FROM timetable_entries
        WHERE department=%s AND day = DAYNAME(CURDATE())
        ORDER BY id
        """,
        (department,),
    )
    if not rows:
        return "No classes scheduled for today."

    lines = [f"Sem {r['semester_number']}: {r['time_slot']} - {r['subject']}" for r in rows]
    return "🗓️ Today's Department Schedule\n" + "\n".join(lines)


def get_department_overview(department: str) -> str:
    """Get comprehensive department overview."""
    # Student count
    student_row = fetch_one_dict(
        "SELECT COUNT(*) as cnt FROM approved_students WHERE department=%s",
        (department,),
    )
    student_count = student_row.get("cnt", 0) if student_row else 0

    # Attendance
    att_row = fetch_one_dict(
        "SELECT AVG(attendance_percent) as avg_att FROM student_attendance_records WHERE department=%s",
        (department,),
    )
    avg_att = round(att_row["avg_att"], 1) if att_row and att_row.get("avg_att") else 0

    # Placements
    placed_row = fetch_one_dict(
        "SELECT COUNT(DISTINCT student_id) as placed FROM placements WHERE department=%s AND status='Selected'",
        (department,),
    )
    placed = placed_row.get("placed", 0) if placed_row else 0

    # Backlogs
    backlog_row = fetch_one_dict(
        """
        SELECT COUNT(DISTINCT s.student_id) as backlog_students
        FROM approved_students s
        JOIN student_results r ON r.student_id=s.student_id AND r.department=s.department
        WHERE s.department=%s AND r.marks < 40
        """,
        (department,),
    )
    backlog = backlog_row.get("backlog_students", 0) if backlog_row else 0

    return (
        f"📊 Department Overview - {department}\n"
        f"Total Students: {student_count}\n"
        f"Average Attendance: {avg_att}%\n"
        f"Students Placed: {placed}\n"
        f"Students with Backlogs: {backlog}"
    )