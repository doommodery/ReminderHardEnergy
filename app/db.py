from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.config import settings


SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    event_uid TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    source_field TEXT NOT NULL,
    case_number TEXT,
    claimant TEXT,
    respondent TEXT,
    event_date TEXT NOT NULL,
    event_time TEXT,
    event_datetime TEXT NOT NULL,
    date_raw TEXT,
    status TEXT,
    source_row INTEGER,
    is_active INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_uid TEXT NOT NULL,
    reminder_code TEXT NOT NULL,
    sent_at TEXT NOT NULL,
    UNIQUE(event_uid, reminder_code)
);

CREATE INDEX IF NOT EXISTS idx_events_event_datetime ON events(event_datetime);
CREATE INDEX IF NOT EXISTS idx_events_active ON events(is_active);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
"""


def _ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, definition: str) -> None:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    existing = {row[1] for row in rows}
    if column_name not in existing:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def init_db() -> None:
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(settings.db_path) as conn:
        conn.executescript(SCHEMA)

        # Мягкая миграция для уже существующей БД.
        _ensure_column(conn, "events", "event_type", "TEXT NOT NULL DEFAULT 'hearing'")
        _ensure_column(conn, "events", "source_field", "TEXT NOT NULL DEFAULT 'Дата судебного заседания'")

        conn.commit()


@contextmanager
def get_conn():
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()