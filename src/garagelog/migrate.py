"""Schema migrations for garage.json.

Author: Marwan Helmy

Migration history:
  v0 -> v1: wrap flat vehicle list into structured garage object
  v1 -> v2: add make, bays, tags, audit buckets; normalize vehicle fields
  v2 -> v3: add inspection_logs, recurring, mileage/weather/issue/odometer/labels buckets
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Callable

from .errors import MigrationError
from .storage import DEFAULT_CELLAR, SCHEMA_VERSION

LATEST_SCHEMA_VERSION = 3

MIGRATION_NOTES = {
    0: "legacy flat list or empty file",
    1: "structured garage with vehicles array and schema_version",
    2: "make/bays/tags/audit + normalized vehicle metadata",
    3: "inspection_logs, recurring, environmental logs, labels metadata",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def migrate_v0_to_v1(raw: Any) -> dict[str, Any]:
    """v0 was sometimes just a list of vehicles."""
    if isinstance(raw, list):
        return {
            "schema_version": 1,
            "vehicles": raw,
            "make": [],
            "bays": [],
            "service_events": [],
            "tags": [],
            "notes": [],
            "audit": [],
            "plugins": [],
        }
    if isinstance(raw, dict) and "vehicles" not in raw and raw.get("schema_version") is None:
        # maybe single vehicle dict?
        if "name" in raw and "id" in raw:
            return migrate_v0_to_v1([raw])
    if isinstance(raw, dict):
        out = deepcopy(raw)
        out.setdefault("vehicles", [])
        out["schema_version"] = 1
        return out
    raise MigrationError(0, 1, "cannot migrate v0 payload: %s" % type(raw))


def migrate_v1_to_v2(data: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(data)
    out["schema_version"] = 2
    for bucket in ("make", "bays", "tags", "audit", "plugins", "recurring"):
        out.setdefault(bucket, [])

    normalized = []
    for vehicle in out.get("vehicles", []):
        p = dict(vehicle)
        p.setdefault("active", True)
        p.setdefault("tags", [])
        p.setdefault("metadata", {})
        p.setdefault("service_interval_days", 7)
        if "make" in p and "make_id" not in p:
            # old inline make string -> stub make row
            sid = p.pop("make", "unknown")
            p["make_id"] = sid
            if not any(s.get("id") == sid for s in out["make"]):
                out["make"].append({
                    "id": sid,
                    "common_name": sid,
                    "created_at": _utc_now(),
                })
        p.setdefault("make_id", "unknown")
        normalized.append(p)
    out["vehicles"] = normalized
    out.setdefault("service_events", [])
    out.setdefault("notes", [])
    return out


def migrate_v2_to_v3(data: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(data)
    out["schema_version"] = 3
    for bucket in (
        "inspection_logs",
        "recurring",
        "collections",
        "mileage_readings",
        "weather_logs",
        "issue_reports",
        "grind_events",
        "labels",
    ):
        out.setdefault(bucket, [])

    # backfill inspection_logs from legacy notes tagged as care
    if not out["inspection_logs"]:
        for note in out.get("notes", []):
            if note.get("kind") == "care":
                out["inspection_logs"].append({
                    "id": note.get("id"),
                    "vehicle_id": note.get("vehicle_id"),
                    "action": note.get("action", "general"),
                    "logged_at": note.get("created_at", _utc_now()),
                    "details": note.get("body", ""),
                })
    return out


MIGRATORS: dict[int, Callable[[Any], dict[str, Any]]] = {
    0: migrate_v0_to_v1,
    1: migrate_v1_to_v2,
    2: migrate_v2_to_v3,
}


def detect_version(raw: Any) -> int:
    if isinstance(raw, list):
        return 0
    if not isinstance(raw, dict):
        return 0
    ver = raw.get("schema_version")
    if ver is None:
        return 0 if "vehicles" not in raw else 1
    return int(ver)


def migrate_payload(raw: Any, target: int = LATEST_SCHEMA_VERSION) -> dict[str, Any]:
    version = detect_version(raw)
    data: Any = raw
    while version < target:
        migrator = MIGRATORS.get(version)
        if migrator is None:
            raise MigrationError(version, version + 1, "no migrator registered")
        data = migrator(data)
        version = int(data.get("schema_version", version + 1))
    merged = deepcopy(DEFAULT_CELLAR)
    merged.update(data)
    merged["schema_version"] = target
    return merged


def migrate_file(path: str, target: int = LATEST_SCHEMA_VERSION) -> dict[str, Any]:
    import json
    from pathlib import Path

    p = Path(path)
    if not p.exists():
        blank = deepcopy(DEFAULT_CELLAR)
        blank["schema_version"] = target
        return blank
    raw = json.loads(p.read_text(encoding="utf-8"))
    result = migrate_payload(raw, target=target)
    p.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def migration_plan(current: int, target: int = LATEST_SCHEMA_VERSION) -> list[dict]:
    steps = []
    v = current
    while v < target:
        steps.append({
            "from": v,
            "to": v + 1,
            "description": MIGRATION_NOTES.get(v + 1, "unknown step"),
        })
        v += 1
    return steps
