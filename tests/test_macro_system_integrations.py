from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from macro_research_system.src.integrations import (  # noqa: E402
    build_macro_system_summary,
    load_oil_rate_summary,
    load_tw_margin_summary,
)


def test_tw_margin_adapter_falls_back_when_env_root_is_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("TW_MARGIN_SYSTEM_ROOT", raising=False)
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True)
    source_path = output_dir / "signal_summary.json"
    source_path.write_text(
        json.dumps({"signal": "LOCAL_TIGHT", "score": 0.75}),
        encoding="utf-8",
    )

    summary = load_tw_margin_summary(repo_root=tmp_path)

    assert summary["status"] == "OK"
    assert summary["schema_key"] == "taiwan_local_liquidity"
    assert summary["source_path"] == str(source_path)
    assert summary["data"]["signal"] == "LOCAL_TIGHT"


def test_oil_rate_adapter_falls_back_when_env_root_is_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("OIL_INFLATION_SYSTEM_ROOT", raising=False)
    report_dir = tmp_path / "oil_rate_macro_monitor" / "data" / "reports"
    report_dir.mkdir(parents=True)
    source_path = report_dir / "oil_rate_macro_report.json"
    source_path.write_text(
        json.dumps({"oil_macro_regime": "PHYSICAL_TIGHT", "risk": "ELEVATED"}),
        encoding="utf-8",
    )

    summary = load_oil_rate_summary(repo_root=tmp_path)

    assert summary["status"] == "OK"
    assert summary["schema_key"] == "global_oil_inflation_pressure"
    assert summary["source_path"] == str(source_path)
    assert summary["data"]["oil_macro_regime"] == "PHYSICAL_TIGHT"


def test_aggregator_writes_summary_when_both_systems_are_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("TW_MARGIN_SYSTEM_ROOT", raising=False)
    monkeypatch.delenv("OIL_INFLATION_SYSTEM_ROOT", raising=False)
    output_path = tmp_path / "macro_research_system" / "data" / "outputs" / "macro_system_summary.json"

    summary = build_macro_system_summary(
        repo_root=tmp_path,
        output_path=output_path,
        write=True,
    )

    assert summary["schema_version"] == "1.0"
    assert summary["status"] == "MISSING"
    assert "taiwan_local_liquidity" in summary
    assert "global_oil_inflation_pressure" in summary
    assert "final_macro_risk_gate" in summary
    assert summary["taiwan_local_liquidity"]["status"] == "MISSING"
    assert summary["global_oil_inflation_pressure"]["status"] == "MISSING"
    assert summary["final_macro_risk_gate"]["status"] == "MISSING"
    assert output_path.exists()
