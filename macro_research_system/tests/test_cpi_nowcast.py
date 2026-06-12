from src.systems.oil_rates_cpi.processors.cpi_nowcast import build_cpi_nowcast


def test_cpi_nowcast_does_not_peek_actual():
    components = {
        "energy_proxy_mom": 0.02,
        "food_proxy_mom": 0.003,
        "shelter_proxy_mom": 0.004,
        "actual_headline_cpi_mom": 0.99,
    }

    result = build_cpi_nowcast(components)

    assert result["headline_cpi_mom_nowcast"] != 0.99
    assert "actual" not in result["used_fields"]


def test_cpi_nowcast_preserves_asof_date():
    result = build_cpi_nowcast({"energy_proxy_mom": 0.01, "cpi_asof_date": "2026-05"})

    assert result["cpi_asof_date"] == "2026-05"
