"""SQLite-backed state store for durable state persistence"""
import os
import json
import sqlite3
from typing import Any, Optional
from datetime import datetime

from .logging import get_logger

_conn: Optional[sqlite3.Connection] = None
_db_path = "./state/trading_state.db"


def _get_connection() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        os.makedirs(os.path.dirname(_db_path), exist_ok=True)
        _conn = sqlite3.connect(_db_path, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
    return _conn


def init_state_store() -> None:
    logger = get_logger()
    logger.log("state_store_init", {"path": _db_path})
    
    conn = _get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.commit()
    logger.log("state_store_ready", {"path": _db_path})


def get_state(key: str, default: Any = None) -> Any:
    try:
        conn = _get_connection()
        cursor = conn.execute("SELECT value FROM state WHERE key = ?", (key,))
        row = cursor.fetchone()
        if row:
            return json.loads(row["value"])
        return default
    except Exception as e:
        get_logger().error(f"State get error: {e}", key=key)
        return default


def set_state(key: str, value: Any) -> None:
    # Validate inputs
    if not isinstance(key, str) or not key.strip():
        raise ValueError("State key must be a non-empty string")
    
    try:
        conn = _get_connection()
        # Ensure value is JSON serializable
        json_value = json.dumps(value, default=str)
        now = datetime.utcnow().isoformat() + "Z"
        conn.execute("""
            INSERT OR REPLACE INTO state (key, value, updated_at)
            VALUES (?, ?, ?)
        """, (key, json_value, now))
        conn.commit()
    except (TypeError, ValueError) as e:
        get_logger().error(f"State serialization error: {e}", key=key)
        raise ValueError(f"Cannot serialize value for key '{key}': {e}")
    except Exception as e:
        get_logger().error(f"State set error: {e}", key=key)
        raise


def delete_state(key: str) -> None:
    try:
        conn = _get_connection()
        conn.execute("DELETE FROM state WHERE key = ?", (key,))
        conn.commit()
    except Exception as e:
        get_logger().error(f"State delete error: {e}", key=key)


def close_state_store() -> None:
    global _conn
    if _conn:
        _conn.close()
        _conn = None
