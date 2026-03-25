from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import settings
from app.downloader import SpreadsheetDownloader
from app.parser import SpreadsheetParser
from app.repository import EventRepository


REMINDER_LABELS = {
    "7d": "за 7 дней",
    "3d": "за 3 дня",
    "1d": "за 1 день",
}

EVENT_TYPE_LABELS = {
    "hearing": "Судебное заседание",
    "deadline": "Срок подготовки документов",
}

EVENT_TYPE_ICONS = {
    "hearing": "⚖️",
    "deadline": "📄",
}


class CourtScheduleService:
    def __init__(self):
        self.repo = EventRepository()
        self.downloader = SpreadsheetDownloader(settings.source_url)
        self.parser = SpreadsheetParser(settings.source_sheet_name, settings.tz, settings.default_event_time)
        self.tz = ZoneInfo(settings.tz)

    def sync(self) -> dict[str, int]:
        file_path = self.downloader.download(settings.file_cache_path)
        events = self.parser.parse(file_path)
        return self.repo.replace_events(events)

    def format_event(self, row) -> str:
        event_type = row["event_type"]
        icon = EVENT_TYPE_ICONS.get(event_type, "📅")
        title = EVENT_TYPE_LABELS.get(event_type, "Событие")

        pieces = [f"{icon} {title}"]
        pieces.append(f"📅 {row['event_date']} {row['event_time'] or ''}".strip())

        if row["case_number"]:
            pieces.append(f"Дело: {row['case_number']}")

        if row["claimant"] or row["respondent"]:
            pieces.append(f"Стороны: {row['claimant'] or '—'} → {row['respondent'] or '—'}")

        if row["source_field"]:
            pieces.append(f"Источник: {row['source_field']}")

        if row["date_raw"] and row["date_raw"] not in {row["event_date"], f"{row['event_date']} {row['event_time'] or ''}".strip()}:
            pieces.append(f"Исходное значение: {row['date_raw']}")

        if row["status"]:
            pieces.append(f"Статус: {row['status']}")

        return "\n".join(pieces)

    def format_reminder_header(self, row) -> str:
        event_type = row["event_type"]
        reminder_code = row["reminder_code"]

        event_label = {
            "hearing": "о судебном заседании",
            "deadline": "о сроке подготовки документов",
        }.get(event_type, "о событии")

        reminder_label = REMINDER_LABELS.get(reminder_code, reminder_code)
        return f"⏰ Напоминание {event_label} {reminder_label}"

    def events_for_date(self, date_iso: str) -> str:
        rows = self.repo.upcoming_by_date(date_iso)
        if not rows:
            return f"На {date_iso} событий не найдено."

        body = "\n\n".join(self.format_event(r) for r in rows)
        return f"События на {date_iso}:\n\n{body}"

    def next_events(self, limit: int = 10) -> str:
        rows = self.repo.next_events(limit=limit)
        if not rows:
            return "Предстоящих событий нет."

        body = "\n\n".join(self.format_event(r) for r in rows)
        return f"Ближайшие события:\n\n{body}"

    def due_notifications(self):
        now = datetime.now(self.tz)
        now_iso = now.strftime("%Y-%m-%d %H:%M:%S")
        return self.repo.due_notifications(now_iso), now

    def mark_sent(self, event_uid: str, reminder_code: str, dt: datetime) -> None:
        self.repo.mark_notification_sent(event_uid, reminder_code, dt.strftime("%Y-%m-%d %H:%M:%S"))