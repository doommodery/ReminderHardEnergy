from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class CourtEvent:
    event_uid: str
    case_number: str | None
    claimant: str | None
    respondent: str | None
    event_date: str
    event_time: str | None
    event_datetime: datetime
    date_raw: str
    status: str | None
    source_row: int
