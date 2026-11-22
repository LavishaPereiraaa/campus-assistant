"""Flask blueprint for chatbot AJAX endpoints."""

from __future__ import annotations

from flask import Blueprint, jsonify, request, session

from .app_factory import create_chatbot_router
from .suggestions import get_suggested_questions
from pathlib import Path



bp = Blueprint("chatbot_core", __name__)

_router = None


def _get_router():
    global _router
    if _router is None:
        _router = create_chatbot_router(Path(__file__).resolve().parents[1])
    return _router


@bp.post("/api/chat/general")
def api_chat_general():
    msg = request.json.get("message", "")
    out = _get_router().handle_general(msg, session)
    last_intent = session.get("ctx_last_intent")
    # suggested questions based on role + context
    role = "department" if session.get("admin") else ("student" if session.get("student_id") else "general")
    suggestions = get_suggested_questions(role=role, last_intent=last_intent, max_items=8)
    return jsonify({"reply": out, "suggestions": suggestions})



@bp.post("/api/chat/student")
def api_chat_student():
    msg = request.json.get("message", "")
    if "student_id" not in session:
        return jsonify({"reply": "Please log in to access your academic information."}), 401

    student_id = session.get("student_id")
    # Resolve department strictly from DB student profile to avoid spoofing
    department = session.get("department") or "Computer Science"

    out = _get_router().handle_student(msg, student_id=student_id, department=department, session=session)
    last_intent = session.get("ctx_last_intent")
    suggestions = get_suggested_questions(role="student", last_intent=last_intent, max_items=8)
    return jsonify({"reply": out, "suggestions": suggestions})


@bp.post("/api/chat/department")
def api_chat_department():
    msg = request.json.get("message", "")
    if not session.get("admin"):
        return jsonify({"reply": "You do not have permission to access this information."}), 403

    department = session.get("department") or "Computer Science"
    out = _get_router().handle_department(msg, department=department, session=session)
    last_intent = session.get("ctx_last_intent")
    suggestions = get_suggested_questions(role="department", last_intent=last_intent, max_items=8)
    return jsonify({"reply": out, "suggestions": suggestions})


