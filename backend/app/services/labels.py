"""Lightweight label helpers — no pandas (safe for Vercel cold auth/chart paths)."""
from __future__ import annotations

from typing import Any

from app.constants import MEASURE_LABELS


def friendly_label(col: str) -> str:
    if col in ("treatment", "treatment_display"):
        return "Treatment"
    if col == "eid":
        return "EID"
    if col == "date":
        return "Date"
    if col in MEASURE_LABELS:
        return MEASURE_LABELS[col]
    return col.replace("_", " ").title()


def treatment_display(val: Any) -> str:
    if val is None:
        return "No Treatment"
    try:
        if val != val:  # NaN
            return "No Treatment"
    except Exception:
        pass
    return str(val)


def label_from_combo(combo: dict, varying_dims: list[str], all_overall: bool) -> str:
    if all_overall or not varying_dims:
        if all(v == "Overall" for v in combo.values()):
            return "Overall Average"
        parts = [
            f"{friendly_label(d)}: {combo[d]}"
            for d in ("sex", "treatment", "breed", "mob", "eid")
            if combo.get(d) and combo[d] != "Overall"
        ]
        return " | ".join(parts) if parts else "Overall Average"
    return " | ".join(f"{friendly_label(d)}: {combo[d]}" for d in varying_dims)


def full_label_from_combo(combo: dict, is_admin: bool) -> str:
    parts = []
    for col in ("sex", "treatment", "breed", "mob"):
        parts.append(f"{friendly_label(col)}: {combo.get(col, 'Overall')}")
    eid = combo.get("eid", "Overall") if is_admin else "*****"
    parts.append(f"EID: {eid}")
    return ", ".join(parts)
