"""Session context memory."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ChatContext:
    last_intent: str | None = None
    last_topic: str | None = None


def get_context(session: Dict[str, Any]) -> ChatContext:
    return ChatContext(
        last_intent=session.get("ctx_last_intent"),
        last_topic=session.get("ctx_last_topic"),
    )


def set_context(session: Dict[str, Any], *, intent: str | None, topic: str | None) -> None:
    if intent is not None:
        session["ctx_last_intent"] = intent
    if topic is not None:
        session["ctx_last_topic"] = topic


def clear_context(session: Dict[str, Any]) -> None:
    """Clear stored chatbot context for the current session."""
    session.pop("ctx_last_intent", None)
    session.pop("ctx_last_topic", None)


