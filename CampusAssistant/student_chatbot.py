"""Student-facing chatbot.

Flask app expects:
  - get_student_chatbot_response(message: str) -> str

Uses static campus_data.json plus live database data for subjects and placements.
"""

from __future__ import annotations

import os
import json
from typing import Dict, List, Tuple, Optional


def _normalize(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def _get_db_connection():
    """Get a DB connection, loading .env file if needed.

    IMPORTANT: If MySQL/connector isn't available (common during local testing),
    fall back to static-only responses instead of crashing.
    """
    try:
        import mysql.connector
        import os


        # Always ensure env vars are loaded from .env file(s)
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
                break

        from database.db import get_db_config
        cfg = get_db_config()
        return mysql.connector.connect(**cfg)
    except Exception as e:
        print(f"DB connection error: {e}")
        return None


def _load_static_dataset(dataset_path: str) -> Dict[str, str]:
    if not os.path.exists(dataset_path):
        return {}
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items() if v is not None}


def _parse_intent_key(intent_key: str) -> str:
    parts = str(intent_key).split("::")
    topic = parts[0] if len(parts) > 0 else ""
    phrase = parts[1] if len(parts) > 1 else intent_key
    return _normalize(f"{topic} {phrase}")


def _get_dynamic_intents(student_id: Optional[str] = None, department: Optional[str] = None) -> Tuple[List[str], List[str], List[str]]:
    """Build dynamic intent entries from live database for subjects and placements."""
    intents = []
    answers = []
    intent_texts = []

    # If DB is not reachable (or mysql.connector not installed),
    # keep working with static FAQ-only intents.
    conn = _get_db_connection()
    if not conn:
        return [], [], []


    try:
        cursor = conn.cursor()

        # --- Subjects by semester ---
        for sem in [1, 2, 3, 4]:
            cursor.execute("""
                SELECT subject_name, subject_code FROM semester_subjects
                WHERE department=%s AND semester_number=%s
                ORDER BY subject_name
            """, (department or 'Computer Science', sem))
            rows = cursor.fetchall()
            if rows:
                subj_list = ", ".join([f"{r[0]} ({r[1]})" for r in rows if r[1]])
                default_list = ", ".join([r[0] for r in rows])
                key = f"subjects::semester {sem} subjects::0"
                intents.append(key)
                answers.append(f"Subjects in Semester {sem}: {subj_list}")
                intent_texts.append(_normalize(f"subjects semester {sem}"))

                key2 = f"subjects::list semester {sem} subjects::0"
                intents.append(key2)
                answers.append(f"Semester {sem} subjects: {default_list}")
                intent_texts.append(_normalize(f"list semester {sem} subjects"))

        # --- All subjects (any semester) ---
        cursor.execute("""
            SELECT subject_name, subject_code, semester_number FROM semester_subjects
            WHERE department=%s ORDER BY semester_number, subject_name
        """, (department or 'Computer Science',))
        all_rows = cursor.fetchall()
        if all_rows:
            all_subj = "; ".join([f"Sem {r[2]}: {r[0]} ({r[1]})" for r in all_rows if r[1]])
            key = "subjects::all subjects list::0"
            intents.append(key)
            answers.append(f"All subjects: {all_subj}")
            intent_texts.append(_normalize("all subjects semester"))

        # --- Placements ---
        cursor.execute("""
            SELECT company, package, department FROM placements
            ORDER BY department, company
        """)
        placement_rows = cursor.fetchall()
        if placement_rows:
            # All placements
            all_placements = "; ".join([f"{r[0]} - {r[1]}" for r in placement_rows])
            key = "placement::all placement companies::0"
            intents.append(key)
            answers.append(f"Placement companies and packages: {all_placements}")
            intent_texts.append(_normalize("placement companies package lpa"))

            # By department
            if department:
                cursor.execute("""
                    SELECT company, package FROM placements
                    WHERE department=%s ORDER BY company
                """, (department,))
                dept_rows = cursor.fetchall()
                if dept_rows:
                    dept_placements = "; ".join([f"{r[0]} - {r[1]}" for r in dept_rows])
                    key = f"placement::{department} placements::0"
                    intents.append(key)
                    answers.append(f"{department} placement companies: {dept_placements}")
                    intent_texts.append(_normalize(f"placement {department} company lpa package"))

            # Individual company lookups
            for row in placement_rows:
                company_lower = row[0].lower()
                key = f"placement::{company_lower} package::0"
                intents.append(key)
                answers.append(f"{row[0]} package: {row[1]} per annum")
                intent_texts.append(_normalize(f"{company_lower} package lpa salary"))

        # --- Syllabus/exam ---
        cursor.execute("""
            SELECT subject_name FROM semester_subjects
            WHERE department=%s ORDER BY semester_number
        """, (department or 'Computer Science',))
        subj_rows = cursor.fetchall()
        if subj_rows:
            subj_names = ", ".join([r[0] for r in subj_rows])
            key = "syllabus::subjects list::0"
            intents.append(key)
            answers.append(f"All subjects in {department or 'your department'}: {subj_names}")
            intent_texts.append(_normalize("syllabus subject list"))

    finally:
        conn.close()

    return intents, answers, intent_texts


def _build_model(student_id: Optional[str] = None, department: Optional[str] = None):
    """Build the full intent model from static + dynamic data."""
    dataset_path = os.path.join(os.path.dirname(__file__), "data", "campus_data.json")
    static_dataset = _load_static_dataset(dataset_path)

    static_intents = list(static_dataset.keys())
    static_answers = [static_dataset[k] for k in static_intents]
    static_texts = [_parse_intent_key(k) for k in static_intents]

    dyn_intents, dyn_answers, dyn_texts = _get_dynamic_intents(student_id, department)

    all_intents = static_intents + dyn_intents
    all_answers = static_answers + dyn_answers
    all_texts = static_texts + dyn_texts

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        train_texts = [f"{_parse_intent_key(k)}. {all_answers[i]}" for i, k in enumerate(all_intents)]
        vectorizer = TfidfVectorizer(lowercase=True, ngram_range=(1, 2), stop_words=None)
        X = vectorizer.fit_transform(train_texts)

        return {
            "type": "tfidf",
            "intents": all_intents,
            "answers": all_answers,
            "vectorizer": vectorizer,
            "X": X,
            "cosine_similarity": cosine_similarity,
            "intent_texts": all_texts,
        }
    except Exception:
        return {
            "type": "keyword",
            "intents": all_intents,
            "answers": all_answers,
            "intent_texts": all_texts,
        }


def _detect_category(msg: str) -> Optional[str]:
    if not msg:
        return None
    rules = [
        ("fees", {"fee", "fees", "tuition", "semester fee", "payment", "cost"}),
        ("attendance", {"attendance", "attend"}),
        ("subjects", {"subject", "subjects", "syllabus"}),
        ("placement", {"placement", "placements", "company", "companies"}),
        ("exam", {"exam", "exams", "timetable", "schedule", "examination"}),
        ("library", {"library", "books", "book"}),
        ("admission", {"admission", "admissions", "apply", "application"}),
    ]
    for cat, needles in rules:
        if any(n in msg for n in needles):
            return cat
    return None


def get_student_chatbot_response(user_message: str, student_id: Optional[str] = None, department: Optional[str] = None) -> str:
    msg = _normalize(user_message)
    if not msg:
        return "Sorry, I don't understand. Please try asking about fees, attendance, subjects, placements, or exams."

    category = _detect_category(msg)
    model = _build_model(student_id, department)

    # TF-IDF path (restricted by confidence threshold)
    if model["type"] == "tfidf":
        q = model["vectorizer"].transform([msg])
        sims = model["cosine_similarity"](q, model["X"]).flatten()
        best_idx = int(sims.argmax())
        best_score = float(sims[best_idx])

        # safer threshold to avoid wrong answers
        threshold = 0.10 if category else 0.14
        if best_score >= threshold:
            return model["answers"][best_idx]
        return "Sorry, I don't understand. Try asking about fees, attendance, subjects, placements, exams, library, or admission."

    # Keyword fallback
    msg_tokens = set(msg.split())
    best_score = -1.0
    best_answer = "Sorry, I don't understand. Try asking about fees, attendance, subjects, placements, exams, library, or admission."

    for intent_key, intent_text, answer in zip(model["intents"], model["intent_texts"], model["answers"]):
        # intent_key starts with topic::...
        parsed = _parse_intent_key(intent_key)
        # _parse_intent_key returns a normalized "topic phrase" string in this file.
        topic_tokens = set(parsed.split()) if parsed else set()
        score = 0.0

        # prefer matching the detected category using the parsed intent token set
        if topic_tokens and category and category in topic_tokens:
            score += 2.0

        if intent_text and intent_text in msg:
            score += 1.0
        it_tokens = set(intent_text.split()) if intent_text else set()
        if it_tokens:
            score += len(msg_tokens & it_tokens) / max(1, len(it_tokens))
        if score > best_score:
            best_score = score
            best_answer = answer

    if best_score < 1.0:
        return "Sorry, I don't understand. Try asking about fees, attendance, subjects, placements, exams, library, or admission."
    return best_answer


