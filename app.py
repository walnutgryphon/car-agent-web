from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

SNAPSHOT_FILE = Path(__file__).resolve().parent / "latest_snapshot.json"
STALE_AFTER_HOURS = 36


def parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def is_stale(generated_at_iso: str) -> bool:
    parsed = parse_iso(generated_at_iso)
    if parsed is None:
        return True
    return (datetime.now(timezone.utc) - parsed) > timedelta(hours=STALE_AFTER_HOURS)


def format_price(value: int | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:,} SEK".replace(",", " ")


def format_mileage(value: int | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:,} mil".replace(",", " ")


def load_snapshot() -> dict:
    if not SNAPSHOT_FILE.exists():
        return {"generated_at": "", "source_run_id": None, "total_active": 0, "cars": []}
    return json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))


st.set_page_config(page_title="Car Agent Rankings", layout="wide")
st.title("Car Agent Rankings")

snapshot = load_snapshot()

meta_cols = st.columns(3)
meta_cols[0].metric("Active listings", int(snapshot.get("total_active", 0)))
meta_cols[1].metric("Source run ID", snapshot.get("source_run_id") or "N/A")
meta_cols[2].metric("Generated at", snapshot.get("generated_at") or "N/A")

if is_stale(snapshot.get("generated_at", "")):
    st.warning("Data may be stale (older than 36 hours).")

cars = snapshot.get("cars", [])
if not cars:
    st.info("No cars available in snapshot yet.")
    st.stop()

df = pd.DataFrame(
    [
        {
            "Model": car.get("model", "unknown"),
            "Score": car.get("score", 0),
            "Year": car.get("year"),
            "Engine": car.get("engine", "unknown"),
            "Price": format_price(car.get("price_sek")),
            "Mileage": format_mileage(car.get("mileage_mil")),
            "Link": car.get("url", ""),
            "Listing ID": car.get("listing_id", ""),
        }
        for car in cars
    ]
)

st.subheader("Ranked Cars")
st.dataframe(df, use_container_width=True, hide_index=True)

selected_id = st.selectbox("Select a car for rationale", [car.get("listing_id", "") for car in cars], index=0)
selected = next((car for car in cars if car.get("listing_id", "") == selected_id), None)

if selected:
    st.markdown(f"### {selected.get('title') or selected.get('model', 'Car')} ({selected.get('listing_id')})")
    info_cols = st.columns(4)
    info_cols[0].write(f"**Model:** {selected.get('model', 'unknown')}")
    info_cols[1].write(f"**Year:** {selected.get('year', 'N/A')}")
    info_cols[2].write(f"**Engine:** {selected.get('engine', 'unknown')}")
    info_cols[3].write(f"**Score:** {selected.get('score', 0)}")

    st.write(f"**Price:** {format_price(selected.get('price_sek'))}")
    st.write(f"**Mileage:** {format_mileage(selected.get('mileage_mil'))}")
    if selected.get("url"):
        st.link_button("Open Listing", selected["url"])

    st.subheader("Score Breakdown")
    st.json(selected.get("score_breakdown", {}))
