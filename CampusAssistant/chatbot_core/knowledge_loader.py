"""Load JSON knowledge base (static) only once."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class KnowledgeBundle:
    # raw category->list(entries)
    entries: Dict[str, List[Dict[str, Any]]]
    # intent->entry list
    intent_map: Dict[str, List[Dict[str, Any]]]


def _load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_knowledge(knowledge_dir: str | Path) -> KnowledgeBundle:
    knowledge_dir = Path(knowledge_dir)

    # Required static files
    filenames = [
        "academics.json",
        "departments.json",
        "placements.json",
        "attendance_policy.json",
        # Some repos use examinations.json + examination_rules.json; load whichever exists.
        "examination_rules.json",
        "examinations.json",
        "scholarships.json",
        "hostel.json",
        # admission.json may be missing in this project; treat it as optional.
        "admission.json",
        "faculty.json",
        "college_info.json",
        "faq.json",
        "student_services.json",
    ]


    raw_entries: Dict[str, List[Dict[str, Any]]] = {}
    intent_map: Dict[str, List[Dict[str, Any]]] = {}

    for name in filenames:
        p = knowledge_dir / name
        if not p.exists():
            continue
        data = _load_json(p)
        # Support either {Category:[...]} or {entries:[...]}
        if isinstance(data, dict):
            if "Category" in data and isinstance(data.get("Answer"), (str, dict, list)):
                data = [data]
            if "entries" in data and isinstance(data["entries"], list):
                data_list = data["entries"]
            elif all(isinstance(v, list) for v in data.values()):
                # e.g. {"Category": [...]} is already handled above
                # Otherwise we treat each key as category list
                for cat, arr in data.items():
                    if isinstance(arr, list):
                        raw_entries.setdefault(cat, []).extend(arr)
                        for entry in arr:
                            intent = entry.get("Intent")
                            if intent:
                                intent_map.setdefault(intent, []).append(entry)
                continue
            else:
                # If it is list-like but wrapped
                data_list = data if isinstance(data, list) else []
        else:
            data_list = []

        if isinstance(data_list, list):
            for entry in data_list:
                cat = entry.get("Category") or "General"
                raw_entries.setdefault(cat, []).append(entry)
                intent = entry.get("Intent")
                if intent:
                    intent_map.setdefault(intent, []).append(entry)

    return KnowledgeBundle(entries=raw_entries, intent_map=intent_map)

