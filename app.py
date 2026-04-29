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


def build_score_breakdown_rows(score_breakdown: dict) -> list[dict[str, str]]:
    ordered_keys = ["family_fit", "quietness", "spec", "value", "penalties", "total"]
    rows: list[dict[str, str]] = []
    for key in ordered_keys:
        if key not in score_breakdown:
            continue
        value = score_breakdown.get(key)
        label = key.replace("_", " ").title()
        if key == "total":
            label = "Total Score"
        rows.append({"Component": label, "Points": value})
    return rows


def _format_sub_value(value) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def build_component_subrows(score_breakdown: dict) -> list[dict[str, str]]:
    details = (score_breakdown or {}).get("details", {})
    components = details.get("component_breakdown", {})
    ordered = ["family_fit", "quietness", "spec", "value", "penalties"]

    rows: list[dict[str, str]] = []
    for component in ordered:
        payload = components.get(component, {})
        if not isinstance(payload, dict) or not payload:
            continue
        label = component.replace("_", " ").title()
        for key, value in payload.items():
            if isinstance(value, dict):
                for nested_key, nested_value in value.items():
                    rows.append(
                        {
                            "Category": label,
                            "Sub-category": f"{key.replace('_', ' ').title()}: {nested_key.replace('_', ' ').title()}",
                            "Value": _format_sub_value(nested_value),
                        }
                    )
                continue
            rows.append(
                {
                    "Category": label,
                    "Sub-category": key.replace("_", " ").title(),
                    "Value": _format_sub_value(value),
                }
            )
    return rows


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
    breakdown = selected.get("score_breakdown", {})
    breakdown_rows = build_score_breakdown_rows(breakdown)
    if breakdown_rows:
        st.table(pd.DataFrame(breakdown_rows))
    else:
        st.info("No score breakdown available for this listing.")

    subrows = build_component_subrows(breakdown)
    if subrows:
        st.markdown("**Sub-categories by Component**")
        st.table(pd.DataFrame(subrows))

    details = breakdown.get("details", {})
    if details:
        st.subheader("Score Debug Details")
        normalized = details.get("normalized", {})
        if normalized:
            st.markdown("**Normalized Scores**")
            normalized_rows = [{"Metric": k.replace("_", " ").title(), "Value": v} for k, v in normalized.items()]
            st.table(pd.DataFrame(normalized_rows))

        penalties = details.get("penalties", {})
        if penalties:
            st.markdown("**Penalty Contributors**")
            penalty_rows = [{"Penalty": k.replace("_", " ").title(), "Value": v} for k, v in penalties.items()]
            st.table(pd.DataFrame(penalty_rows))
