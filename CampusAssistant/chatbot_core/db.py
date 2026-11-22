"""DB access helpers for chatbot.

Uses existing database.db.get_db_config/connect_db.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from database.db import connect_db


def fetch_one_dict(sql: str, params: Sequence[Any]) -> Optional[Dict[str, Any]]:
    conn = connect_db()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, params)
        return cur.fetchone()
    finally:
        conn.close()


def fetch_all_dict(sql: str, params: Sequence[Any]) -> List[Dict[str, Any]]:
    conn = connect_db()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, params)
        return list(cur.fetchall() or [])
    finally:
        conn.close()

