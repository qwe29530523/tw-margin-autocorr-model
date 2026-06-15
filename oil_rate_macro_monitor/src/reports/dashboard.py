from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


BASE_DIR = Path(__file__).resolve().parents[2]
PROCESSED_DIR = BASE_DIR / "data" / "processed"
REPORTS_DIR = BASE_DIR / "data" / "reports"


def load_processed(name: str) -> pd.DataFrame:
    parquet = PROCESSED_DIR / f"{name}.parquet"
    csv = PROCESSED_DIR / f"{name}.csv"
    if parquet.exists():
        return pd.read_parquet(parquet)
    if csv.exists():
        return pd.read_csv(csv)
    return pd.DataFrame()


def main() -> None:
    st.set_page_config(page_title="Oil + Rates Macro Monitor", layout="wide")
    st.title("Oil + Rates Macro Monitor")

    oil = load_processed("oil_curve")
    cracks = load_processed("crack_spreads")
    rates = load_processed("rates")
    inventory = load_processed("inventory")

    if not oil.empty:
        st.subheader("WTI / Brent")
        st.plotly_chart(px.line(oil, x="date", y=["wti", "brent"]), use_container_width=True)
    if not cracks.empty:
        st.subheader("Crack Spreads")
        st.plotly_chart(px.line(cracks, x="date", y=["gasoline_crack", "diesel_crack"]), use_container_width=True)
    if not rates.empty:
        st.subheader("Rates")
        st.plotly_chart(
            px.line(rates, x="date", y=["ten_year", "two_year", "ten_year_two_year_spread"]),
            use_container_width=True,
        )
    if not inventory.empty:
        st.subheader("Inventory Proxy")
        st.plotly_chart(px.line(inventory, x="date", y="total_petroleum_inventory_proxy"), use_container_width=True)

    st.subheader("Latest Regime Inputs")
    latest_rows = []
    for name, frame in [("oil", oil), ("cracks", cracks), ("rates", rates), ("inventory", inventory)]:
        if not frame.empty:
            row = frame.tail(1).copy()
            row.insert(0, "table", name)
            latest_rows.append(row)
    if latest_rows:
        st.dataframe(pd.concat(latest_rows, ignore_index=True), use_container_width=True)

    reports = sorted(REPORTS_DIR.glob("oil_rate_macro_report_*.md"), reverse=True)
    st.subheader("Latest Markdown Report")
    if reports:
        st.markdown(reports[0].read_text(encoding="utf-8"))
    else:
        st.info("No report found. Run `python -m src.main report` first.")


if __name__ == "__main__":
    main()
