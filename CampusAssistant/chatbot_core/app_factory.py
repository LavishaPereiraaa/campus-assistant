"""Create chatbot core and expose handler used by Flask routes."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from .intent_classifier import IntentClassifier
from .knowledge_loader import load_knowledge
from .router import ChatbotRouter


def create_chatbot_router(app_root: str | Path) -> ChatbotRouter:
    app_root = Path(app_root)
    knowledge_dir = app_root / "knowledge"

    bundle = load_knowledge(knowledge_dir)

    # Build intent definitions from knowledge (Keywords/Synonyms per entry)
    intent_definitions: Dict[str, Dict[str, Any]] = {}

    for intent, entries in bundle.intent_map.items():
        # aggregate keywords/synonyms
        keywords = set()
        synonyms = set()
        for e in entries:
            for k in (e.get("Keywords") or []):
                keywords.add(k)
            for s in (e.get("Synonyms") or []):
                synonyms.add(s)
        if keywords or synonyms:
            intent_definitions[intent] = {
                "Keywords": list(keywords),
                "Synonyms": list(synonyms),
            }

    # Define dynamic system intents handled directly by router.py
    SYSTEM_INTENTS = {
        "attendance_query": {"Keywords": ["attendance", "attend", "present", "presence", "missed", "class"], "Synonyms": []},
        "attendance_policy_query": {"Keywords": ["attendance policy", "minimum attendance"], "Synonyms": []},
        "attendance_calculation_query": {"Keywords": ["attendance calculation", "calculate attendance"], "Synonyms": []},
        "attendance_below75_query": {"Keywords": ["below 75", "low attendance", "shortage"], "Synonyms": []},
        "exam_eligibility_query": {"Keywords": ["eligible", "exam eligibility"], "Synonyms": []},
        "exam_query": {"Keywords": ["exam", "examination", "test"], "Synonyms": []},
        "result_query": {"Keywords": ["result", "results", "marks", "score", "grade"], "Synonyms": []},
        "marks_query": {"Keywords": ["marks", "mark"], "Synonyms": []},
        "cgpa_query": {"Keywords": ["cgpa", "cumulative", "overall cgpa"], "Synonyms": []},
        "sgpa_query": {"Keywords": ["sgpa", "semester gpa"], "Synonyms": []},
        "semester_result_query": {"Keywords": ["semester result"], "Synonyms": []},
        "backlog_query": {"Keywords": ["backlog", "fail", "failed"], "Synonyms": []},
        "subjects_to_improve_query": {"Keywords": ["improve", "subjects to improve"], "Synonyms": []},
        "timetable_query": {"Keywords": ["timetable", "schedule", "class timing"], "Synonyms": []},
        "subjects_query": {"Keywords": ["subject", "subjects", "syllabus", "course"], "Synonyms": []},
        "profile_query": {"Keywords": ["profile", "my profile", "my details", "my info"], "Synonyms": []},
        "placement_query": {"Keywords": ["placement", "placements", "company", "package", "salary", "job"], "Synonyms": []},
        "full_information_query": {"Keywords": ["full information", "my full information", "show my full", "complete profile"], "Synonyms": []},
        
        # Department specific intents
        "analytics_query": {"Keywords": ["analytics", "overview", "summary"], "Synonyms": []},
        "attendance_below_query": {"Keywords": ["below", "shortage"], "Synonyms": []},
        "attendance_report_query": {"Keywords": ["attendance report"], "Synonyms": []},
        "semester_analytics_query": {"Keywords": ["semester analytics"], "Synonyms": []},
        "subject_performance_query": {"Keywords": ["subject performance", "failed in subject"], "Synonyms": []}
    }

    # Merge SYSTEM_INTENTS into intent_definitions
    for intent, payload in SYSTEM_INTENTS.items():
        if intent not in intent_definitions:
            intent_definitions[intent] = {"Keywords": [], "Synonyms": []}
        
        intent_definitions[intent]["Keywords"].extend(payload["Keywords"])
        intent_definitions[intent]["Synonyms"].extend(payload["Synonyms"])

    classifier = IntentClassifier(intent_definitions)
    return ChatbotRouter(bundle=bundle, classifier=classifier)

