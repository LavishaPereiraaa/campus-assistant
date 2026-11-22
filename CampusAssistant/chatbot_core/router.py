"""Route request to student/department/general pipelines."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from .config import CONF_MIN
from .context_memory import ChatContext, get_context, set_context, clear_context
from .department_service import (
    get_students_below_attendance,
    get_all_students_with_backlogs,
    get_placement_statistics,
    get_attendance_report,
    get_semester_analytics,
    get_students_by_semester,
    get_subject_performance,
    get_failed_in_subject,
    get_department_timetable,
    get_today_schedule,
    get_department_overview,
)
from .intent_classifier import IntentClassifier, IntentResult
from .knowledge_answerer import choose_knowledge_answer
from .knowledge_loader import KnowledgeBundle
from .student_service import (
    get_full_information,
    get_marks_and_result,
    get_attendance_summary,
    get_profile,
    get_subject_attendance,
    get_lowest_attendance_subject,
    get_classes_to_attend,
    get_exams_list,
    get_exam_eligibility,
    get_backlog_count,
    get_subjects_to_improve,
    get_timetable_today,
    get_timetable_full,
    get_semester_result,
    get_sgpa,
    get_cgpa,
    get_placement_status,
    get_placement_companies,
    get_registered_subjects,
    get_placements,
    get_timetable_sample,
)


def _extract_semester(text: str) -> Optional[int]:
    """Extract semester number from text like 'semester 5' or 'sem 3'."""
    match = re.search(r'sem(?:ester)?\s*(\d+)', text.lower())
    if match:
        return int(match.group(1))
    return None


def _extract_subject(text: str) -> Optional[str]:
    """Extract subject name from text."""
    # Remove common patterns
    cleaned = re.sub(r'(subject|subject:|in)\s*', '', text.lower())
    cleaned = cleaned.strip()
    if cleaned and len(cleaned) > 2:
        return cleaned.title()
    return None


class ChatbotRouter:
    def __init__(self, *, bundle: KnowledgeBundle, classifier: IntentClassifier):
        self.bundle = bundle
        self.classifier = classifier

    def handle_general(self, message: str, session: Dict[str, Any]) -> str:
        ir: IntentResult = self.classifier.classify(message)
        if not ir.intent or ir.confidence < CONF_MIN:
            return "I'm sorry, I couldn't understand your request. Please try asking in a different way."

        ans, conf = choose_knowledge_answer(self.bundle, ir.intent)
        if not ans or conf < CONF_MIN:
            return "I'm sorry, I couldn't understand your request. Please try asking in a different way."

        set_context(session, intent=ir.intent, topic=None)
        return ans

    def handle_student(self, message: str, *, student_id: str, department: str, session: Dict[str, Any]) -> str:
        ir: IntentResult = self.classifier.classify(message)
        msg_lower = message.lower()

        # Handle follow-up questions using context
        ctx = get_context(session)
        if not ir.intent or ir.confidence < CONF_MIN:
            # Check if we can use context for follow-ups
            if ctx.last_intent:
                # Handle follow-up questions based on previous intent
                if ctx.last_intent == "attendance_query":
                    if "lowest" in msg_lower or "which subject" in msg_lower:
                        return get_lowest_attendance_subject(student_id, department)
                    elif "subject" in msg_lower or "subject wise" in msg_lower:
                        return get_subject_attendance(student_id, department)
                    elif "class" in msg_lower or "missed" in msg_lower:
                        return get_classes_to_attend(student_id, department)
                    else:
                        return get_attendance_summary(student_id, department)

                if ctx.last_intent in ["result_query", "cgpa_query", "sgpa_query"]:
                    if "semester" in msg_lower:
                        return get_semester_result(student_id, department)
                    elif "sgpa" in msg_lower:
                        return get_sgpa(student_id, department)
                    elif "cgpa" in msg_lower:
                        return get_cgpa(student_id, department)
                    else:
                        return get_marks_and_result(student_id, department)

            return "I'm sorry, I couldn't understand your request. Please try asking in a different way."

        set_context(session, intent=ir.intent, topic=None)

        # Full information
        if ir.intent == "full_information_query":
            return get_full_information(student_id, department)

        # Attendance (student-specific)
        if ir.intent in ["attendance_query", "attendance_policy_query", "attendance_calculation_query"]:
            # Policy/calculation knowledge should generally be answered from the knowledge base.
            # But keep the student-attendance UI working for the main "attendance" intent.
            if ir.intent == "attendance_query":
                if "subject" in msg_lower or "subject wise" in msg_lower:
                    return get_subject_attendance(student_id, department)
                elif "lowest" in msg_lower or "which subject" in msg_lower:
                    return get_lowest_attendance_subject(student_id, department)
                elif "class" in msg_lower or "missed" in msg_lower or "how many" in msg_lower:
                    return get_classes_to_attend(student_id, department)
                else:
                    return get_attendance_summary(student_id, department)

            # For knowledge-only attendance intents, fall through to knowledge answerer.

        if ir.intent == "attendance_below75_query":
            # Knowledge intent: if user asks consequences, answer from knowledge base.
            # If user asks student-specific consequences (low attendance), provide student eligibility.
            if any(w in msg_lower for w in ["my", "student", "me", "i have", "i\"m", "eligible", "exam"]):
                return get_exam_eligibility(student_id, department)

            # otherwise, fall through to knowledge answerer.


        # Exam eligibility
        if ir.intent == "exam_eligibility_query" or "eligible" in msg_lower:
            return get_exam_eligibility(student_id, department)

        # Exam list
        if ir.intent == "exam_query" or "exam" in msg_lower:
            return get_exams_list(student_id, department)

        # Result, marks, CGPA, SGPA
        if ir.intent in ["result_query", "marks_query"]:
            return get_marks_and_result(student_id, department)

        if ir.intent == "cgpa_query":
            return get_cgpa(student_id, department)

        if ir.intent == "sgpa_query":
            return get_sgpa(student_id, department)

        if ir.intent == "semester_result_query":
            return get_semester_result(student_id, department)

        # Backlogs
        if ir.intent == "backlog_query":
            return get_backlog_count(student_id, department)

        if ir.intent == "subjects_to_improve_query":
            return get_subjects_to_improve(student_id, department)

        # Timetable
        if ir.intent == "timetable_query":
            if "today" in msg_lower:
                return get_timetable_today(student_id, department)
            elif "full" in msg_lower or "week" in msg_lower:
                return get_timetable_full(student_id, department)
            else:
                return get_timetable_sample(student_id, department)

        # Subjects
        if ir.intent == "subjects_query":
            return get_registered_subjects(student_id, department)

        # Profile
        if ir.intent == "profile_query":
            return get_profile(student_id, department)

        # Placements
        if ir.intent == "placement_query":
            if "status" in msg_lower or "shortlisted" in msg_lower:
                return get_placement_status(student_id, department)
            else:
                return get_placements(student_id, department)

        # Default - try knowledge base
        ans, conf = choose_knowledge_answer(self.bundle, ir.intent)
        if ans and conf >= CONF_MIN:
            return ans

        return "The requested information is currently unavailable."

    def handle_department(self, message: str, *, department: str, session: Dict[str, Any]) -> str:
        ir: IntentResult = self.classifier.classify(message)
        msg_lower = message.lower()

        if not ir.intent or ir.confidence < CONF_MIN:
            return "I'm sorry, I couldn't understand your request. Please try asking in a different way."

        set_context(session, intent=ir.intent, topic=None)

        # Overview
        if ir.intent == "analytics_query" or "overview" in msg_lower or "summary" in msg_lower:
            return get_department_overview(department)

        # Attendance quick navigation (opens attendance management screen)
        if "attendance" in msg_lower:
            # If user asks for attendance, take them to the management page.
            # If semester is present, prefill it; student_id is handled by user via UI.
            sem = _extract_semester(message)
            if sem:
                return f"Opening Department Attendance…\n\nGo to: /department-attendance?department={department}&semester={sem}"
            return f"Opening Department Attendance…\n\nGo to: /department-attendance?department={department}"

        # Attendance below threshold
        if ir.intent == "attendance_below_query" or "below" in msg_lower:
            threshold = 75.0
            if "80" in msg_lower:
                threshold = 80.0
            elif "60" in msg_lower:
                threshold = 60.0
            return get_students_below_attendance(department, threshold)

        # Attendance report
        if ir.intent == "attendance_report_query":
            return get_attendance_report(department)


        # Backlogs
        if ir.intent == "backlog_query" or "backlog" in msg_lower:
            return get_all_students_with_backlogs(department)

        # Placements
        if ir.intent == "placement_query" or "placement" in msg_lower:
            return get_placement_statistics(department)

        # Semester analytics
        if ir.intent == "semester_analytics_query" or "analytics" in msg_lower:
            return get_semester_analytics(department)

        # Students by semester
        if "semester" in msg_lower or "sem" in msg_lower:
            sem = _extract_semester(message)
            if sem:
                return get_students_by_semester(department, sem)
            return get_semester_analytics(department)

        # Subject performance
        if ir.intent == "subject_performance_query" or "failed" in msg_lower:
            subj = _extract_subject(message)
            if subj:
                if "fail" in msg_lower:
                    return get_failed_in_subject(department, subj)
                return get_subject_performance(department, subj)
            return "Please specify a subject name."

        # Timetable
        if ir.intent == "timetable_query":
            sem = _extract_semester(message)
            if "today" in msg_lower:
                return get_today_schedule(department)
            return get_department_timetable(department, sem)

        # Today schedule
        if "today" in msg_lower:
            return get_today_schedule(department)

        # Default
        return "The requested information is currently unavailable."