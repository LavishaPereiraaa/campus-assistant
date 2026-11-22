"""General knowledge answer selection.

For now: exact intent lookup within knowledge files. If none or low confidence => refusal.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .intent_classifier import _normalize, IntentResult
from .knowledge_loader import KnowledgeBundle


def choose_knowledge_answer(bundle: KnowledgeBundle, intent: str) -> Tuple[Optional[str], float]:
    entries = bundle.intent_map.get(intent) or []
    if not entries:
        return None, 0.0

    # Prefer by Priority then first
    def prio(e: Dict[str, Any]) -> int:
        try:
            return int(e.get("Priority", 0))
        except Exception:
            return 0

    entries_sorted = sorted(entries, key=prio, reverse=True)
    ans = entries_sorted[0].get("Answer")
    if isinstance(ans, (dict, list)):
        ans = str(ans)
    if not ans:
        return None, 0.0

    # Confidence from priority heuristic
    conf = min(0.95, 0.55 + 0.05 * prio(entries_sorted[0]))
    return str(ans), float(conf)

