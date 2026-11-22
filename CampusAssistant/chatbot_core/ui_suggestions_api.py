"""Optional API helper to serve suggested questions.

Not used by default; kept for future extension.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .suggestions import get_suggested_questions


def build_suggestions_payload(*, role: str, last_intent: str | None = None, max_items: int = 7) -> List[Dict[str, str]]:
    return get_suggested_questions(role=role, last_intent=last_intent, max_items=max_items)

