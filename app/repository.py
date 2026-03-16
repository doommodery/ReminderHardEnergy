from __future__ import annotations

from datetime import datetime

from app.db import get_conn
from app.models import CourtEvent


class EventRepository:
    def replace_events(self, events: list[CourtEvent]) -> dict[str, int]:
        now = datetime.utcnow().isoformat(timespec='seconds')
        with get_conn() as conn:
            conn.execute('UPDATE events SET is_active = 0')
            for event in events:
                conn.execute(
                    """
                    INSERT INTO events (
                        event_uid, case_number, claimant, respondent, event_date, event_time,
                        event_datetime, date_raw, status, source_row, is_active, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                    ON CONFLICT(event_uid) DO UPDATE SET
                        case_number=excluded.case_number,
                        claimant=excluded.claimant,
                        respondent=excluded.respondent,
                        event_date=excluded.event_date,
                        event_time=excluded.event_time,
                        event_datetime=excluded.event_datetime,
                        date_raw=excluded.date_raw,
                        status=excluded.status,
                        source_row=excluded.source_row,
                        is_active=1,
                        updated_at=excluded.updated_at
                    """,
                    (
                        event.event_uid,
                        event.case_number,
                        event.claimant,
                        event.respondent,
                        event.event_date,
                        event.event_time,
                        event.event_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                        event.date_raw,
                        event.status,
                        event.source_row,
                        now,
                    ),
                )
            active_count = conn.execute('SELECT COUNT(*) AS cnt FROM events WHERE is_active = 1').fetchone()['cnt']
        return {'active_events': int(active_count), 'loaded': len(events)}

    def upcoming_by_date(self, date_iso: str):
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM events
                WHERE is_active = 1 AND event_date = ?
                ORDER BY event_datetime ASC
                """,
                (date_iso,),
            ).fetchall()
            return rows

    def next_events(self, limit: int = 10):
        now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM events
                WHERE is_active = 1 AND event_datetime >= ?
                ORDER BY event_datetime ASC
                LIMIT ?
                """,
                (now, limit),
            ).fetchall()
            return rows

    def due_notifications(self, current_dt_iso: str):
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT e.*, x.reminder_code FROM (
                    SELECT event_uid, '24h' AS reminder_code, datetime(event_datetime, '-24 hours') AS remind_at FROM events WHERE is_active = 1
                    UNION ALL
                    SELECT event_uid, '12h' AS reminder_code, datetime(event_datetime, '-12 hours') AS remind_at FROM events WHERE is_active = 1
                    UNION ALL
                    SELECT event_uid, '6h' AS reminder_code, datetime(event_datetime, '-6 hours') AS remind_at FROM events WHERE is_active = 1
                    UNION ALL
                    SELECT event_uid, '2h' AS reminder_code, datetime(event_datetime, '-2 hours') AS remind_at FROM events WHERE is_active = 1
                ) x
                JOIN events e ON e.event_uid = x.event_uid
                LEFT JOIN notifications n ON n.event_uid = x.event_uid AND n.reminder_code = x.reminder_code
                WHERE n.id IS NULL
                  AND x.remind_at <= datetime(?)
                  AND e.event_datetime >= datetime(?)
                ORDER BY e.event_datetime ASC
                """,
                (current_dt_iso, current_dt_iso),
            ).fetchall()
            return rows

    def mark_notification_sent(self, event_uid: str, reminder_code: str, sent_at_iso: str) -> None:
        with get_conn() as conn:
            conn.execute(
                'INSERT OR IGNORE INTO notifications(event_uid, reminder_code, sent_at) VALUES (?, ?, ?)',
                (event_uid, reminder_code, sent_at_iso),
            )
