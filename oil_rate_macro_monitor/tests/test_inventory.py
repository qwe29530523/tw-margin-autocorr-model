import pandas as pd

from src.processors.inventory import process_inventory


def test_inventory_maps_wcrexus2_to_crude_exports_and_keeps_units():
    eia = pd.DataFrame(
        [
            {"date": "2026-05-22", "series_id": "WCREXUS2", "value": 4440, "units": "MBBL/D"},
            {"date": "2026-05-29", "series_id": "WCREXUS2", "value": 5874, "units": "MBBL/D"},
        ]
    )

    result = process_inventory(eia)
    latest = result.iloc[-1]

    assert latest["crude_exports"] == 5874
    assert latest["crude_exports_units"] == "MBBL/D"


def test_inventory_does_not_map_lower_48_field_production_to_crude_exports():
    eia = pd.DataFrame(
        [
            {
                "date": "2026-05-29",
                "series_id": "W_EPC0_FPF_R48_MBBLD",
                "value": 13295,
                "units": "MBBL/D",
            }
        ]
    )

    result = process_inventory(eia)
    latest = result.iloc[-1]

    assert pd.isna(latest["crude_exports"])
