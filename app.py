from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
from selection import extract_selected_rows, resolve_selected_row_index

SNAPSHOT_FILE = Path(__file__).resolve().parent / "latest_snapshot.json"
STALE_AFTER_HOURS = 36


def apply_shadeui_theme() -> None:
    st.markdown(
        """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700&display=swap');

            :root {
                --shade-bg: #f8fafc;
                --shade-surface: #ffffff;
                --shade-border: #e2e8f0;
                --shade-muted: #64748b;
                --shade-text: #0f172a;
                --shade-accent: #111827;
            }

            html, body, [class*="css"]  {
                font-family: "Manrope", sans-serif;
                color: var(--shade-text);
            }

            .stApp {
                background: radial-gradient(circle at top right, #eef2ff 0%, #f8fafc 40%, #f8fafc 100%);
            }

            .block-container {
                padding-top: 2rem;
                max-width: 1240px;
            }

            [data-testid="stMetric"] {
                background: var(--shade-surface);
                border: 1px solid var(--shade-border);
                border-radius: 14px;
                padding: 0.9rem 1rem;
            }

            [data-testid="stMetricLabel"] {
                color: var(--shade-muted);
                font-weight: 600;
            }

            [data-testid="stMetricValue"] {
                color: var(--shade-accent);
                font-weight: 700;
            }

            .shade-card {
                background: var(--shade-surface);
                border: 1px solid var(--shade-border);
                border-radius: 14px;
                padding: 0.95rem 1rem;
            }

            .shade-title {
                font-size: 2.05rem;
                font-weight: 700;
                letter-spacing: -0.02em;
                margin-bottom: 0.35rem;
            }

            .shade-subtitle {
                color: var(--shade-muted);
                font-size: 0.98rem;
                margin-bottom: 0;
            }

            [data-testid="stExpander"] {
                border: 1px solid var(--shade-border);
                border-radius: 12px;
                background: var(--shade-surface);
            }

            [data-testid="stLinkButton"] a {
                border-radius: 10px;
                border: 1px solid var(--shade-border);
                background: #ffffff;
                color: var(--shade-text);
            }

            [data-testid="stAlert"] {
                border-radius: 12px;
            }

            /* Hide Streamlit dataframe row-selector checkbox column while keeping row click selection. */
            [data-testid="stDataFrame"] [role="columnheader"][aria-colindex="1"],
            [data-testid="stDataFrame"] [role="gridcell"][aria-colindex="1"] {
                display: none !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


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


def format_timestamp(value: str) -> str:
    parsed = parse_iso(value)
    if parsed is None:
        return "N/A"
    local = parsed.astimezone()
    return local.strftime("%Y-%m-%d %H:%M")


def format_date(value: str) -> str:
    parsed = parse_iso(value)
    if parsed is None:
        return "N/A"
    return parsed.astimezone().strftime("%Y-%m-%d")


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


def render_expandable_breakdown(score_breakdown: dict) -> None:
    details = (score_breakdown or {}).get("details", {})
    components = details.get("component_breakdown", {})
    ordered = ["family_fit", "quietness", "spec", "value", "penalties"]
    top_rows = build_score_breakdown_rows(score_breakdown)
    points_by_component = {row["Component"]: row["Points"] for row in top_rows}

    for component_key in ordered:
        component_label = component_key.replace("_", " ").title()
        component_points = points_by_component.get(component_label)
        if component_key == "penalties":
            component_label = "Penalties"
            component_points = points_by_component.get("Penalties")

        if component_points is None:
            continue

        title = f"{component_label}: {component_points}"
        payload = components.get(component_key, {})
        with st.expander(title, expanded=False):
            if not isinstance(payload, dict) or not payload:
                st.write("No sub-categories available.")
                continue

            rows: list[dict[str, str]] = []
            for key, value in payload.items():
                if isinstance(value, dict):
                    for nested_key, nested_value in value.items():
                        rows.append(
                            {
                                "Sub-category": f"{key.replace('_', ' ').title()}: {nested_key.replace('_', ' ').title()}",
                                "Value": _format_sub_value(nested_value),
                            }
                        )
                else:
                    rows.append(
                        {
                            "Sub-category": key.replace("_", " ").title(),
                            "Value": _format_sub_value(value),
                        }
                    )
            if rows:
                st.table(pd.DataFrame(rows))
            else:
                st.write("No sub-categories available.")


def highlight_new_rows(row: pd.Series) -> list[str]:
    if row.get("New") != "New":
        return [""] * len(row)
    return ["background-color: #ecfdf5; font-weight: 600;" for _ in row]


def main() -> None:
    st.set_page_config(page_title="Car Agent Rankings", layout="wide")
    apply_shadeui_theme()

    snapshot = load_snapshot()
    generated_at = snapshot.get("generated_at") or ""

    st.markdown(
        """
        <div class="shade-card">
            <div class="shade-title">Car Agent Rankings</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")

    cars = snapshot.get("cars", [])
    new_count = sum(1 for car in cars if car.get("is_new_since_last_scan"))

    meta_cols = st.columns(4)
    meta_cols[0].metric("Active listings", int(snapshot.get("total_active", 0)))
    meta_cols[1].metric("Source run ID", snapshot.get("source_run_id") or "N/A")
    meta_cols[2].metric("New this scan", new_count)
    meta_cols[3].metric("Generated at", format_timestamp(generated_at))

    if is_stale(generated_at):
        st.warning("Data may be stale (older than 36 hours).")

    if not cars:
        st.info("No cars available in snapshot yet.")
        st.stop()

    df = pd.DataFrame(
        [
            {
                "Rank": index + 1,
                "Model": car.get("model", "unknown"),
                "Score": car.get("score", 0),
                "Year": car.get("year"),
                "Engine": car.get("engine", "unknown"),
                "Price": format_price(car.get("price_sek")),
                "Mileage": format_mileage(car.get("mileage_mil")),
                "Date advertised": format_date(car.get("advertised_at") or car.get("first_seen_at") or ""),
                "New": "New" if car.get("is_new_since_last_scan") else "",
                "Link": car.get("url", ""),
                "Listing ID": car.get("listing_id", ""),
            }
            for index, car in enumerate(cars)
        ]
    )
    styled_df = df.style.apply(highlight_new_rows, axis=1)

    st.subheader("Ranked Cars")
    selection_event = st.dataframe(
        styled_df,
        use_container_width=True,
        hide_index=True,
        key="ranked_cars_table",
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "Rank": st.column_config.NumberColumn(width="small"),
            "Score": st.column_config.NumberColumn(width="small"),
            "Year": st.column_config.NumberColumn(width="small"),
            "New": st.column_config.TextColumn(width="small"),
            "Link": st.column_config.LinkColumn("Link", display_text="Open"),
        },
    )

    selected_rows = extract_selected_rows(selection_event)
    prior_index = st.session_state.get("selected_car_row_index")
    if not isinstance(prior_index, int):
        prior_index = None

    selected_index = resolve_selected_row_index(
        total_rows=len(cars),
        selected_rows=selected_rows,
        prior_index=prior_index,
    )
    if selected_index is None:
        st.stop()

    st.session_state["selected_car_row_index"] = selected_index
    selected = cars[selected_index]

    st.subheader("Listing details")
    with st.container(border=True):
        st.markdown(f"### {selected.get('title') or selected.get('model', 'Car')} ({selected.get('listing_id')})")
        info_cols = st.columns(4)
        info_cols[0].write(f"**Model:** {selected.get('model', 'unknown')}")
        info_cols[1].write(f"**Year:** {selected.get('year', 'N/A')}")
        info_cols[2].write(f"**Engine:** {selected.get('engine', 'unknown')}")
        info_cols[3].write(f"**Score:** {selected.get('score', 0)}")

        st.write(f"**Price:** {format_price(selected.get('price_sek'))}")
        st.write(f"**Mileage:** {format_mileage(selected.get('mileage_mil'))}")
        st.write(f"**Date advertised:** {format_date(selected.get('advertised_at') or selected.get('first_seen_at') or '')}")
        if selected.get("is_new_since_last_scan"):
            st.success("New since the last scan.")
        if selected.get("url"):
            st.link_button("Open Listing", selected["url"])

        st.subheader("Score Breakdown")
        breakdown = selected.get("score_breakdown", {})
        if build_score_breakdown_rows(breakdown):
            render_expandable_breakdown(breakdown)
        else:
            st.info("No score breakdown available for this listing.")


if __name__ == "__main__":
    main()
