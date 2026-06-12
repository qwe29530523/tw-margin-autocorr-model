from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ENV_NAMES = {"FRED_API_KEY", "EIA_API_KEY", "BLS_API_KEY", "USE_YAHOO", "MOCK_MODE"}


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    fred_api_key: str | None
    eia_api_key: str | None
    bls_api_key: str | None
    use_yahoo: bool
    mock_mode: bool
    env_file_loaded: bool = False
    env_file_path: str | None = None

    @property
    def warnings(self) -> list[str]:
        warnings: list[str] = []
        if self.mock_mode:
            warnings.append("MOCK_MODE=true; using fixture data.")
        for label, key in [
            ("FRED_API_KEY", self.fred_api_key),
            ("EIA_API_KEY", self.eia_api_key),
            ("BLS_API_KEY", self.bls_api_key),
        ]:
            if not key:
                warnings.append(f"{label} missing; data source will use mock mode or missing warning.")
        if not self.use_yahoo:
            warnings.append("USE_YAHOO=false; market asset backtest overlays disabled.")
        return warnings


def load_settings() -> Settings:
    env_file = _find_env_file()
    env_values = _read_env_file(env_file) if env_file else {}
    fred_key = _env_value("FRED_API_KEY", env_values) or None
    eia_key = _env_value("EIA_API_KEY", env_values) or None
    bls_key = _env_value("BLS_API_KEY", env_values) or None
    mock_mode = _env_bool_value(_env_value("MOCK_MODE", env_values), True)
    return Settings(
        fred_api_key=fred_key,
        eia_api_key=eia_key,
        bls_api_key=bls_key,
        use_yahoo=_env_bool_value(_env_value("USE_YAHOO", env_values), False),
        mock_mode=mock_mode,
        env_file_loaded=env_file is not None,
        env_file_path=str(env_file) if env_file else None,
    )


def _env_bool_value(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_value(name: str, env_values: dict[str, str]) -> str | None:
    value = os.getenv(name)
    if value is not None:
        return value
    return env_values.get(name)


def _find_env_file() -> Path | None:
    current = Path.cwd().resolve()
    for directory in [current, *current.parents]:
        for filename in [".env", ".env.local"]:
            candidate = directory / filename
            if candidate.exists():
                return candidate
    return None


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if key not in ENV_NAMES:
            continue
        values[key] = value.strip().strip('"').strip("'")
    return values
