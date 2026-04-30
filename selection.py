from __future__ import annotations

from typing import Any


def extract_selected_rows_from_aggrid(selection_event: Any, *, index_key: str = "_row_index") -> list[int]:
    if not isinstance(selection_event, dict):
        return []

    selected_rows = selection_event.get("selected_rows")
    if not isinstance(selected_rows, list):
        return []

    selected: list[int] = []
    for row in selected_rows:
        if not isinstance(row, dict):
            continue
        value = row.get(index_key)
        try:
            index = int(value)
        except (TypeError, ValueError):
            continue
        if index >= 0:
            selected.append(index)
    return selected


def extract_selected_rows(selection_event: Any) -> list[int]:
    if not selection_event:
        return []

    selection = getattr(selection_event, "selection", None)
    if selection is None and isinstance(selection_event, dict):
        selection = selection_event.get("selection")

    rows = getattr(selection, "rows", None)
    if rows is None and isinstance(selection, dict):
        rows = selection.get("rows")

    if rows is None:
        rows = getattr(selection_event, "rows", None)
    if rows is None and isinstance(selection_event, dict):
        rows = selection_event.get("rows")

    if not isinstance(rows, list):
        return []

    selected: list[int] = []
    for value in rows:
        try:
            index = int(value)
        except (TypeError, ValueError):
            continue
        if index >= 0:
            selected.append(index)
    return selected


def resolve_selected_row_index(
    *,
    total_rows: int,
    selected_rows: list[int] | None,
    prior_index: int | None,
) -> int | None:
    if total_rows <= 0:
        return None

    candidates: list[int] = []
    if selected_rows:
        candidates.append(selected_rows[0])
    if prior_index is not None:
        candidates.append(prior_index)
    candidates.append(0)

    for index in candidates:
        if 0 <= index < total_rows:
            return index

    return 0
