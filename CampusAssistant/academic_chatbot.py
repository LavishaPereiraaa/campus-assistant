"""
AI-Powered Academic Assistant
============================
A 4-layer intelligent chatbot system for campus information.

Layer 1: Database Intelligence - Query MySQL database
Layer 2: Knowledge Base - Search structured JSON files
Layer 3: AI Matching Engine - TF-IDF + Cosine Similarity + Confidence
Layer 4: Safety Validation - Student ownership verification
"""

from __future__ import annotations

import os
import json
import re
from typing import Dict, List, Tuple, Optional
from pathlib import Path

# Configuration
CONF_HIGH = 0.80
CONF_MEDIUM = 0.60

# Intent patterns
INTENT_KEYWORDS = {
    "attendance_query": ["attendance", "attend", "present", "presence"],
    "result_query": ["result", "results", "marks", "score", "grade", "marks"],
    "cgpa_query": ["cgpa", "cumulative", "overall cgpa"],
    "sgpa_query": ["sgpa", "semester gpa"],
    "placement_query": ["placement", "placements", "company", "package", "salary", "lpa", "job"],
    "department_query": ["department", "dept", "branch"],
    "faculty_query": ["faculty", "teacher", "professor", "lecturer"],
    "timetable_query": ["timetable", "schedule", "class timing"],
    "exam_query": ["exam", "examination", "test", "semester exam"],
    "notice_query": ["notice", "announcement", "circular"],
    "subject_query": ["subject", "subjects", "syllabus", "course"],
    "scholarship_query": ["scholarship", "scholarships", "fellowship"],
    "profile_query": ["profile", "my profile", "my details", "my profile information", "my info"],
    "marks_query": ["marks", "mark"],
    "full_information_query": ["full information", "my full information", "show my full", "complete profile", "my complete information"],
    "fees_query": ["fee", "fees", "tuition", "payment", "cost"],
    "library_query": ["library", "books", "book"],
    "hostel_query": ["hostel", "room", "accommodation"],
}


def _normalize(text: str) -> str:
    """Normalize text for matching."""
    return " ".join((text or "").strip().lower().split())


def _detect_intent(message: str) -> Optional[str]:
    """Detect user intent from message."""
    msg = _normalize(message)
    for intent, keywords in INTENT_KEYWORDS.items():
        if any(kw in msg for kw in keywords):
            return intent
    return None


def _load_json_file(filepath: str) -> Dict:
    """Load a JSON file safely."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


# ==============================================================================
# LAYER 1: DATABASE INTELLIGENCE
# ==============================================================================

def _get_db_connection():
    """Get MySQL database connection."""
    try:
        import mysql.connector
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        for env_file in [os.path.join(base, ".env"), os.path.join(base, ".env.local")]:
            if os.path.exists(env_file):
                with open(env_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        key, val = line.split("=", 1)
                        os.environ[key.strip()] = val.strip().strip('"').strip("'")
        from database.db import get_db_config
        cfg = get_db_config()
        return mysql.connector.connect(**cfg)
    except Exception as e:
        print(f"DB connection error: {e}")
        return None


def _db_get_student_data(student_id: str, department: str, intent: str) -> Tuple[Optional[str], float]:
    """Query database for student-specific data."""
    conn = _get_db_connection()
    if not conn:
        return None, 0.0

    try:
        cursor = conn.cursor(dictionary=True)

        # ----- Profile + full information (student-scoped) -----
        if intent in ["profile_query", "full_information_query"]:
            cursor.execute(
                """
                SELECT student_id, name, email, image_path, department
                FROM approved_students
                WHERE student_id=%s AND department=%s
                """,
                (student_id, department),
            )
            prof = cursor.fetchone()
            if not prof:
                return None, 0.0

            if intent == "profile_query":
                return (
                    f"👤 Student Profile\n"
                    f"Name: {prof['name']}\n"
                    f"Student ID: {prof['student_id']}\n"
                    f"Department: {prof['department']}\n"
                    f"Email: {prof['email']}" ,
                    0.95,
                )

            # full_information_query: build composite from DB only
            cursor.execute(
                """
                SELECT AVG(attendance_percent) as avg_att
                FROM student_attendance_records
                WHERE student_id=%s AND department=%s
                """,
                (student_id, department),
            )
            att_row = cursor.fetchone()
            overall_att = round(att_row['avg_att'], 1) if att_row and att_row.get('avg_att') is not None else None

            cursor.execute(
                """
                SELECT SUM(marks) as total_points, SUM(max_marks) as total_max
                FROM student_results
                WHERE student_id=%s AND department=%s
                """,
                (student_id, department),
            )
            totals = cursor.fetchone()
            cgpa = None
            if totals and totals.get('total_max') and totals['total_max'] > 0:
                cgpa = round((totals['total_points'] / totals['total_max']) * 10, 2) if totals['total_points'] is not None else None

            cursor.execute(
                """
                SELECT company, package
                FROM placements
                WHERE department=%s
                ORDER BY company
                LIMIT 5
                """,
                (department,),
            )
            place_rows = cursor.fetchall() or []
            placement_lines = "-" 
            if place_rows:
                placement_lines = ", ".join([f"{p['company']} ({p['package']})" for p in place_rows])

            cursor.execute(
                """
                SELECT day, subject
                FROM timetable_entries
                WHERE department=%s
                ORDER BY FIELD(day,'Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'), id
                LIMIT 12
                """,
                (department,),
            )
            tt_rows = cursor.fetchall() or []
            tt_grouped = {}
            for r in tt_rows:
                tt_grouped.setdefault(r['day'], []).append(r['subject'])
            tt_lines = [f"{d}: {', '.join(s)}" for d, s in sorted(tt_grouped.items(), key=lambda x: x[0])] if tt_grouped else []

            return (
                "📌 Campus ERP — Full Student Information\n\n"
                "👤 Student Profile\n"
                f"Name: {prof['name']}\n"
                f"Student ID: {prof['student_id']}\n"
                f"Department: {prof['department']}\n"
                f"Email: {prof['email']}\n\n"
                "📚 Attendance\n"
                f"Overall Attendance: {overall_att if overall_att is not None else 'N/A'}%\n\n"
                "📊 Result / CGPA\n"
                f"CGPA: {cgpa if cgpa is not None else 'N/A'}\n\n"
                "📌 Top Placement Drives\n"
                f"{placement_lines}\n\n"
                "🗓️ Timetable (Sample)\n"
                ("\n".join(tt_lines) if tt_lines else "-"),
                0.90,
            )


        if intent == "attendance_query":
            cursor.execute("""
                SELECT AVG(attendance_percent) as avg_att FROM student_attendance_records
                WHERE student_id=%s AND department=%s
            """, (student_id, department))
            result = cursor.fetchone()
            if result and result.get('avg_att'):
                return f"Your attendance: {round(result['avg_att'], 1)}%", 0.95

        elif intent in ["result_query", "cgpa_query", "sgpa_query"]:
            cursor.execute("""
                SELECT semester_number, SUM(marks) as total_marks, SUM(max_marks) as max_marks
                FROM student_results WHERE student_id=%s AND department=%s
                GROUP BY semester_number
            """, (student_id, department))
            rows = cursor.fetchall()
            if rows:
                total_points = sum(r['total_marks'] or 0 for r in rows)
                total_max = sum(r['max_marks'] or 0 for r in rows)
                if total_max > 0:
                    cgpa = round((total_points / total_max) * 10, 2)
                    return f"Your CGPA: {cgpa}", 0.95

        elif intent == "subject_query":
            cursor.execute("""
                SELECT subject_name, subject_code FROM semester_subjects
                WHERE department=%s ORDER BY semester_number, subject_name LIMIT 10
            """, (department,))
            rows = cursor.fetchall()
            if rows:
                subjects = ", ".join([f"{r['subject_name']}" for r in rows])
                return f"Subjects: {subjects}", 0.90

        elif intent == "placement_query":
            cursor.execute("""
                SELECT company, package FROM placements
                WHERE department=%s ORDER BY company LIMIT 10
            """, (department,))
            rows = cursor.fetchall()
            if rows:
                placements = ", ".join([f"{r['company']} ({r['package']})" for r in rows])
                return f"Placements: {placements}", 0.90

        elif intent == "timetable_query":
            cursor.execute("""
                SELECT day, subject FROM timetable_entries
                WHERE department=%s ORDER BY day, id LIMIT 15
            """, (department,))
            rows = cursor.fetchall()
            if rows:
                timetable = {}
                for r in rows:
                    day = r['day']
                    if day not in timetable:
                        timetable[day] = []
                    timetable[day].append(r['subject'])
                lines = [f"{d}: {', '.join(s)}" for d, s in timetable.items()]
                return "\n".join(lines), 0.90

    except Exception as e:
        print(f"DB query error: {e}")
    finally:
        conn.close()

    return None, 0.0


# ==============================================================================
# LAYER 2: KNOWLEDGE BASE
# ==============================================================================

def _load_knowledge() -> Dict:
    """Load all knowledge base files."""
    kb = {}
    knowledge_dir = Path(__file__).parent / "knowledge"

    for filename in ["academics.json", "attendance.json", "examinations.json", "departments.json",
                    "placements.json", "scholarships.json", "college_info.json", "student_services.json"]:
        filepath = knowledge_dir / filename
        if filepath.exists():
            key = filename.replace(".json", "")
            kb[key] = _load_json_file(str(filepath))
    return kb


def _search_knowledge(intent: str, message: str) -> Tuple[Optional[str], float]:
    """Search knowledge base for answers."""
    msg = _normalize(message)
    kb = _load_knowledge()

    # Map intent to knowledge file
    intent_to_kb = {
        "attendance_query": "attendance",
        "exam_query": "examinations",
        "department_query": "departments",
        "placement_query": "placements",
        "scholarship_query": "scholarships",
        "fees_query": "college_info",
        "hostel_query": "student_services",
        "library_query": "student_services",
    }

    kb_key = intent_to_kb.get(intent)
    if kb_key and kb_key in kb:
        content = kb[kb_key]

        # Check various fields based on intent
        if "minimum_attendance_required" in content:
            return f"Minimum attendance required: {content['minimum_attendance_required']}%", 0.85
        if "exam_schedule" in content:
            return f"Exams are typically in {content['exam_schedule'].get('semester_exams', 'December')}", 0.85
        if "departments" in content:
            depts = content["departments"]
            if isinstance(depts, list):
                dlist = ", ".join([d.get("name", "") for d in depts[:5]])
                return f"Departments: {dlist}", 0.85
        if "top_recruiters" in content:
            return f"Top recruiters: {', '.join(content['top_recruiters'][:5])}", 0.85
        if "scholarships" in content:
            sch = content["scholarships"]
            if isinstance(sch, list) and sch:
                return f"Scholarships: {sch[0].get('name', '')} - {sch[0].get('eligibility', '')}", 0.85

    return None, 0.0


# ==============================================================================
# LAYER 3: AI MATCHING (FAQ)
# ==============================================================================

def _load_faq_data() -> Tuple[List[str], List[str]]:
    """Load FAQ dataset."""
    dataset_path = os.path.join(os.path.dirname(__file__), "data", "campus_data.json")
    try:
        with open(dataset_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return [], []

    intents = []
    answers = []
    for key, value in data.items():
        parts = str(key).split("::")
        phrase = parts[1] if len(parts) > 1 else key
        intents.append(_normalize(phrase))
        answers.append(str(value) if value else "")

    return intents, answers


def _ai_match(message: str, intent: Optional[str]) -> Tuple[Optional[str], float]:
    """AI matching with TF-IDF or keyword fallback."""
    msg = _normalize(message)
    phrases, answers = _load_faq_data()

    if not phrases:
        return None, 0.0

    # TF-IDF matching (if sklearn available)
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        train_texts = [f"{phrases[i]} {answers[i]}" for i in range(len(phrases))]
        vectorizer = TfidfVectorizer(lowercase=True, ngram_range=(1, 2))
        X = vectorizer.fit_transform(train_texts)
        q = vectorizer.transform([msg])
        sims = cosine_similarity(q, X).flatten()

        best_idx = int(sims.argmax())
        best_score = float(sims[best_idx])

        threshold = CONF_MEDIUM if intent else 0.25
        if best_score >= threshold:
            return answers[best_idx], best_score
    except ImportError:
        print("sklearn not available, using keyword fallback")
    except Exception as e:
        print(f"AI match error: {e}")

    # Keyword fallback - simple token matching
    msg_tokens = set(msg.split())
    best_answer = None
    best_score = 0.0

    for i, phrase in enumerate(phrases):
        phrase_tokens = set(phrase.split())
        if phrase_tokens:
            score = len(msg_tokens & phrase_tokens) / len(phrase_tokens)
            # Boost score if category matches
            if intent and any(kw in phrase for kw in INTENT_KEYWORDS.get(intent, [])):
                score += 0.3
            if score > best_score:
                best_score = score
                best_answer = answers[i]

    if best_score >= 0.25:
        return best_answer, best_score

    return None, 0.0


# ==============================================================================
# MAIN RESPONSE
# ==============================================================================

def get_academic_response(
    user_message: str,
    student_id: Optional[str] = None,
    department: Optional[str] = None
) -> str:
    """Get AI-powered academic response."""

    msg = _normalize(user_message)
    intent = _detect_intent(msg)

    # Layer 1: Database (for student-specific queries)
    if student_id and department and intent in [
        "attendance_query",
        "marks_query",
        "result_query",
        "cgpa_query",
        "sgpa_query",
        "subject_query",
        "profile_query",
        "exam_query",
        "placement_query",
        "timetable_query",
        "full_information_query",
    ]:
        answer, conf = _db_get_student_data(student_id, department, intent)
        if answer:
            return answer

        # If we detected a student-specific intent but DB returned nothing,
        # we must not fall back to generic FAQ / TF-IDF answers.
        if conf == 0.0 and intent in ["attendance_query","marks_query","result_query","cgpa_query","sgpa_query","subject_query","profile_query","exam_query","placement_query","timetable_query","full_information_query"]:
            return "The requested information is currently unavailable."

    # Layer 2: Knowledge Base
    if intent:
        answer, conf = _search_knowledge(intent, msg)
        if answer and conf >= CONF_MEDIUM:
            return answer

    # Layer 3: AI Matching (lower threshold for more responses)
    answer, conf = _ai_match(msg, intent)
    if answer:
        return answer

    # Fallback responses based on detected intent
    fallbacks = {
        "attendance_query": "Minimum 75% attendance is required for all students.",
        "result_query": "Results are published at the end of each semester.",
        "cgpa_query": "CGPA is calculated based on your semester performance.",
        "sgpa_query": "SGPA is your semester grade point average.",
        "fees_query": "Semester fee is Rs. 45,000 per semester.",
        "exam_query": "Semester exams are typically held in December.",
        "placement_query": "Top companies like TCS, Infosys, Wipro visit campus for placements.",
        "department_query": "The college offers Computer Science, Electronics, Mechanical, Civil, and Electrical engineering.",
        "faculty_query": "Our faculty members are highly qualified with industry experience.",
        "timetable_query": "Timetable varies by department and semester. Check your department notice board.",
        "notice_query": "Check the noticeboard for latest announcements.",
        "subject_query": "Subjects vary by semester. Contact your department for details.",
        "scholarship_query": "Scholarships are available for eligible students. Apply at the beginning of the year.",
        "library_query": "Library timing is 8 AM to 6 PM on all weekdays.",
        "hostel_query": "Hostel facilities are available. Contact the warden for availability.",
    }

    if intent and intent in fallbacks:
        return fallbacks[intent]

    # General fallback for unrecognized queries
    return "For detailed information, please contact your department office or check the noticeboard."


# ==============================================================================
# COMPATIBILITY WRAPPERS
# ==============================================================================

def get_student_chatbot_response(
    user_message: str,
    student_id: Optional[str] = None,
    department: Optional[str] = None
) -> str:
    """Student chatbot response."""
    return get_academic_response(user_message, student_id, department)


def get_department_chatbot_response(
    user_message: str,
    department: Optional[str] = None
) -> str:
    """Department chatbot response."""
    return get_academic_response(user_message, None, department)


def get_chatbot_response(user_message: str) -> str:
    """General chatbot response."""
    return get_academic_response(user_message, None, None)