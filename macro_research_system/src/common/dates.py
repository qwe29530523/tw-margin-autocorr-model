from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo


def today_taipei() -> date:
    return datetime.now(ZoneInfo("Asia/Taipei")).date()
