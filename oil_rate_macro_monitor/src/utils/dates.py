from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo


TAIPEI_TZ = ZoneInfo("Asia/Taipei")


def today_taipei() -> date:
    return datetime.now(TAIPEI_TZ).date()


def timestamp_for_filename() -> str:
    return datetime.now(TAIPEI_TZ).strftime("%Y%m%d_%H%M%S")
