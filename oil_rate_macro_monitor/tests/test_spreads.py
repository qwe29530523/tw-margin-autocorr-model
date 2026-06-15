import pandas as pd

from src.processors.crack_spread import calculate_crack_spreads


def test_gasoline_crack_uses_gallons_per_barrel_conversion():
    prices = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-02"]),
            "wti": [80.0],
            "rb": [2.50],
            "ho": [2.80],
        }
    )

    result = calculate_crack_spreads(prices)

    assert result.loc[0, "gasoline_crack"] == 25.0


def test_diesel_crack_uses_gallons_per_barrel_conversion():
    prices = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-02"]),
            "wti": [80.0],
            "rb": [2.50],
            "ho": [2.80],
        }
    )

    result = calculate_crack_spreads(prices)

    assert result.loc[0, "diesel_crack"] == 37.6


def test_crack_spreads_include_20d_change_and_ma_fields():
    prices = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=25),
            "wti": [80.0] * 25,
            "rb": [2.0 + i * 0.01 for i in range(25)],
            "ho": [2.5 + i * 0.02 for i in range(25)],
        }
    )

    result = calculate_crack_spreads(prices)

    for column in [
        "gasoline_crack_20d_change",
        "diesel_crack_20d_change",
        "gasoline_crack_20d_ma",
        "diesel_crack_20d_ma",
    ]:
        assert column in result.columns
