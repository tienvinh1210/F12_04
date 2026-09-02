from __future__ import annotations

from typing import Any


def anonymize_records(records: list[dict], is_admin: bool) -> list[dict]:
    if is_admin:
        return records
    return [{**r, "eid": "*****"} if "eid" in r else r for r in records]


def anonymize_value(value: Any, is_admin: bool, field: str = "eid") -> Any:
    if field == "eid" and not is_admin:
        return "*****"
    return value
