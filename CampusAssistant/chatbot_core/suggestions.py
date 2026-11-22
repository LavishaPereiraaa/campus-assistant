"""Role-based suggested questions.

These suggestions are static (template-side) but the selection can be made
based on role + last user intent stored in session.

No DB calls here; DB-backed answering is done by chatbot_core/router.py.
"""

from __future__ import annotations

from typing import Any, Dict, List


STUDENT_SUGGESTIONS: List[Dict[str, str]] = [
    {"icon": "fa-solid fa-list-check", "q": "What is my attendance?"},
    {"icon": "fa-solid fa-layer-group", "q": "Show my subject-wise attendance."},
    {"icon": "fa-solid fa-arrow-down-long", "q": "Which subject has the lowest attendance?"},
    {"icon": "fa-solid fa-book", "q": "Show my registered subjects."},
    {"icon": "fa-solid fa-calendar-day", "q": "Show today's timetable."},
    {"icon": "fa-solid fa-calendar-check", "q": "Show tomorrow's timetable."},
    {"icon": "fa-solid fa-file-lines", "q": "What is my exam schedule?"},
    {"icon": "fa-solid fa-chart-column", "q": "Show my semester results."},
    {"icon": "fa-solid fa-medal", "q": "What is my CGPA?"},
    {"icon": "fa-solid fa-award", "q": "What is my SGPA?"},
    {"icon": "fa-solid fa-book-open", "q": "Show my internal marks."},
    {"icon": "fa-solid fa-shield-check", "q": "Am I eligible for exams?"},
    {"icon": "fa-solid fa-briefcase", "q": "Show my placement status."},
    {"icon": "fa-solid fa-building-columns", "q": "Which companies am I eligible for?"},
    {"icon": "fa-solid fa-user", "q": "Show my profile."},
    {"icon": "fa-solid fa-bell", "q": "Show my notifications."},
    {"icon": "fa-solid fa-chalkboard-user", "q": "Who teaches Python?"},
    {"icon": "fa-solid fa-hashtag", "q": "How many subjects do I have this semester?"},
    {"icon": "fa-solid fa-triangle-exclamation", "q": "What are my pending backlogs?"},
    {"icon": "fa-solid fa-mountain-sun", "q": "Show my academic progress."},
]


DEPARTMENT_SUGGESTIONS: List[Dict[str, str]] = [
    {"icon": "fa-solid fa-users", "q": "Show all students."},
    {"icon": "fa-solid fa-user-xmark", "q": "Show students below 75% attendance."},
    {"icon": "fa-solid fa-chart-line", "q": "Generate attendance report."},
    {"icon": "fa-solid fa-chart-column", "q": "Show semester results."},
    {"icon": "fa-solid fa-list-ol", "q": "Show pass/fail statistics."},
    {"icon": "fa-solid fa-briefcase", "q": "Show placement statistics."},
    {"icon": "fa-solid fa-calendar-day", "q": "Show today's timetable."},
    {"icon": "fa-solid fa-chalkboard", "q": "Show faculty list."},
    {"icon": "fa-solid fa-sticky-note", "q": "Show department notices."},
    {"icon": "fa-solid fa-magnifying-glass-chart", "q": "Generate department analytics."},
    {"icon": "fa-solid fa-triangle-exclamation", "q": "Show students with backlogs."},
    {"icon": "fa-solid fa-building", "q": "Show company-wise placements."},
    {"icon": "fa-solid fa-chart-pie", "q": "Show subject performance."},
    {"icon": "fa-solid fa-chart-simple", "q": "Show semester-wise reports."},
    {"icon": "fa-solid fa-handshake-angle", "q": "Show pending student approvals."},
]


GENERAL_SUGGESTIONS: List[Dict[str, str]] = [
    {"icon": "fa-solid fa-building-columns", "q": "How do I apply for admission?"},
    {"icon": "fa-solid fa-graduation-cap", "q": "What courses are offered?"},
    {"icon": "fa-solid fa-shield-halved", "q": "What is the attendance policy?"},
    {"icon": "fa-solid fa-file-lines", "q": "What are the examination rules?"},
    {"icon": "fa-solid fa-hand-holding-heart", "q": "Tell me about scholarships."},
    {"icon": "fa-solid fa-bed", "q": "Hostel facilities."},
    {"icon": "fa-solid fa-book-open", "q": "Library timings."},
    {"icon": "fa-solid fa-phone", "q": "College contact information."},
    {"icon": "fa-solid fa-calendar-days", "q": "Academic calendar."},
    {"icon": "fa-solid fa-route", "q": "Placement process."},
    {"icon": "fa-solid fa-receipt", "q": "Fee payment information."},
    {"icon": "fa-solid fa-tree-city", "q": "Campus facilities."},
]


def get_suggested_questions(*, role: str, last_intent: str | None = None, max_items: int = 7) -> List[Dict[str, str]]:
    """Return 6-8 suggestions depending on role and current context.

    role: "student" | "department" | "general"
    last_intent: intent name stored in session by chatbot_core/router.py
    """

    pool = GENERAL_SUGGESTIONS
    if role == "student":
        pool = STUDENT_SUGGESTIONS
    elif role == "department":
        pool = DEPARTMENT_SUGGESTIONS

    # Context-aware reordering (no guessing; only highlight relevant chips)
    # This is safe because it only reorders suggestions.
    if last_intent:
        intent = last_intent.lower()
        boosted = []
        if "attendance" in intent:
            boosted = ["What is my attendance?", "Show my subject-wise attendance.", "Which subject has the lowest attendance?"]
        elif "timetable" in intent:
            boosted = ["Show today's timetable.", "Show tomorrow's timetable."]
        elif "exam" in intent or "eligibility" in intent:
            boosted = ["What is my exam schedule?", "Am I eligible for exams"]
        elif "result" in intent or "marks" in intent or "cgpa" in intent or "sgpa" in intent:
            boosted = ["Show my semester results.", "What is my CGPA?", "What is my SGPA?", "Show my internal marks"]
        elif "placement" in intent:
            boosted = ["Show my placement status.", "Which companies am I eligible for?"]

        if boosted:
            # stable filter to keep order from pool
            boosted_set = set(boosted)
            head = [x for x in pool if x["q"] in boosted_set]
            tail = [x for x in pool if x["q"] not in boosted_set]
            pool = head + tail

    return pool[:max_items]

