from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    base_dir: Path
    config_dir: Path
    raw_dir: Path
    processed_dir: Path
    reports_dir: Path
    fred_api_key: str | None
    eia_api_key: str | None
    use_yahoo: bool
    wti_curve_api_url: str | None
    wti_curve_api_key: str | None
    wti_curve_api_source: str
    wti_curve_api_source_type: str
    wti_curve_api_key_header: str
    wti_curve_api_key_prefix: str


def load_settings() -> Settings:
    load_dotenv(BASE_DIR / ".env")
    return Settings(
        base_dir=BASE_DIR,
        config_dir=BASE_DIR / "config",
        raw_dir=BASE_DIR / "data" / "raw",
        processed_dir=BASE_DIR / "data" / "processed",
        reports_dir=BASE_DIR / "data" / "reports",
        fred_api_key=os.getenv("FRED_API_KEY") or None,
        eia_api_key=os.getenv("EIA_API_KEY") or None,
        use_yahoo=(os.getenv("USE_YAHOO", "false").strip().lower() == "true"),
        wti_curve_api_url=os.getenv("WTI_CURVE_API_URL") or None,
        wti_curve_api_key=os.getenv("WTI_CURVE_API_KEY") or None,
        wti_curve_api_source=os.getenv("WTI_CURVE_API_SOURCE", "wti_curve_api"),
        wti_curve_api_source_type=os.getenv("WTI_CURVE_API_SOURCE_TYPE", "production_api"),
        wti_curve_api_key_header=os.getenv("WTI_CURVE_API_KEY_HEADER", "Authorization"),
        wti_curve_api_key_prefix=os.getenv("WTI_CURVE_API_KEY_PREFIX", "Bearer"),
    )
