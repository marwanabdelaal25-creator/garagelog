"""JSON Lines import/export for garage events.

Author: Marwan Helmy
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .errors import ExportError, ImportPipelineError, import_pipeline_error
from .vehicle import Vehicle
from .storage import JsonStorage
from .service import ServiceEvent

__author__ = "Marwan Helmy"

EVENT_TYPES = ("service", "care", "vehicle", "note")


def _iter_lines(path: Path) -> Iterable[str]:
    try:
        with path.open(encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if ln:
                    yield ln
    except OSError as exc:
        raise ImportPipelineError("jsonl", str(exc)) from exc


def _load_line(line: str, line_no: int) -> dict[str, Any]:
    try:
        data = json.loads(line)
    except json.JSONDecodeError as exc:
        raise import_pipeline_error("jsonl", line_no, "invalid JSON: %s" % exc) from exc
    if not isinstance(data, dict):
        raise import_pipeline_error("jsonl", line_no, "each line must be a JSON object")
    return data


def export_service_jsonl(storage: JsonStorage, dest: Path) -> int:
    events = storage.list_service_events()
    try:
        with dest.open("w", encoding="utf-8") as fh:
            for row in events:
                payload = {"_type": "service", **row}
                fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return len(events)
    except OSError as exc:
        raise ExportError("jsonl", str(exc)) from exc


def export_care_jsonl(storage: JsonStorage, dest: Path) -> int:
    logs = storage.list_inspection_logs()
    try:
        with dest.open("w", encoding="utf-8") as fh:
            for row in logs:
                payload = {"_type": "care", **row}
                fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return len(logs)
    except OSError as exc:
        raise ExportError("jsonl", str(exc)) from exc


def export_events_jsonl(storage: JsonStorage, dest: Path) -> int:
    """One file with service + care events (and optional vehicle snapshots)."""
    n = 0
    try:
        with dest.open("w", encoding="utf-8") as fh:
            for row in storage.list_service_events():
                fh.write(json.dumps({"_type": "service", **row}, ensure_ascii=False) + "\n")
                n += 1
            for row in storage.list_inspection_logs():
                fh.write(json.dumps({"_type": "care", **row}, ensure_ascii=False) + "\n")
                n += 1
    except OSError as exc:
        raise ExportError("jsonl", str(exc)) from exc
    return n


def export_full_jsonl(storage: JsonStorage, dest: Path) -> int:
    """Export vehicles + all event streams for backup-lite migrations."""
    n = 0
    try:
        with dest.open("w", encoding="utf-8") as fh:
            for vehicle in storage.list_vehicles(active_only=False):
                fh.write(json.dumps({"_type": "vehicle", **vehicle.to_dict()}, ensure_ascii=False) + "\n")
                n += 1
            for row in storage.list_service_events():
                fh.write(json.dumps({"_type": "service", **row}, ensure_ascii=False) + "\n")
                n += 1
            for row in storage.list_inspection_logs():
                fh.write(json.dumps({"_type": "care", **row}, ensure_ascii=False) + "\n")
                n += 1
            for note in storage.list_notes():
                fh.write(json.dumps({"_type": "note", **note}, ensure_ascii=False) + "\n")
                n += 1
    except OSError as exc:
        raise ExportError("jsonl", str(exc)) from exc
    return n


def import_service_jsonl(storage: JsonStorage, src: Path) -> int:
    if not src.exists():
        raise ImportPipelineError("jsonl", "missing %s" % src)
    n = 0
    for line_no, line in enumerate(_iter_lines(src), start=1):
        data = _load_line(line, line_no)
        kind = data.pop("_type", "service")
        if kind != "service":
            continue
        event = ServiceEvent.from_dict(data)
        storage.create_service_event(event.to_dict())
        n += 1
    return n


def import_care_jsonl(storage: JsonStorage, src: Path) -> int:
    if not src.exists():
        raise ImportPipelineError("jsonl", "missing %s" % src)
    n = 0
    for line_no, line in enumerate(_iter_lines(src), start=1):
        data = _load_line(line, line_no)
        kind = data.pop("_type", "care")
        if kind != "care":
            continue
        # inspection_logs in storage use flat dicts; CareEvent maps event_type -> action-ish
        if "event_type" in data and "action" not in data:
            data["action"] = data["event_type"]
        if "occurred_at" in data and "logged_at" not in data:
            data["logged_at"] = data["occurred_at"]
        storage.create_inspection_log(data)
        n += 1
    return n


def import_mixed_jsonl(storage: JsonStorage, src: Path) -> dict[str, int]:
    """Import a mixed JSONL export; unknown _type lines are skipped."""
    if not src.exists():
        raise ImportPipelineError("jsonl", "missing %s" % src)
    counts = {k: 0 for k in EVENT_TYPES}
    counts["skipped"] = 0

    for line_no, line in enumerate(_iter_lines(src), start=1):
        data = _load_line(line, line_no)
        kind = data.pop("_type", "service")

        if kind == "service":
            storage.create_service_event(ServiceEvent.from_dict(data).to_dict())
            counts["service"] += 1
        elif kind == "care":
            if "event_type" in data and "action" not in data:
                data["action"] = data["event_type"]
            if "occurred_at" in data and "logged_at" not in data:
                data["logged_at"] = data["occurred_at"]
            storage.create_inspection_log(data)
            counts["care"] += 1
        elif kind == "vehicle":
            vehicle = Vehicle.from_dict(data)
            try:
                storage.get_vehicle(vehicle.id)
                storage.update_vehicle(vehicle.id, vehicle.to_dict())
            except Exception:
                storage.create_vehicle(vehicle)
            counts["vehicle"] += 1
        elif kind == "note":
            storage.create_note(data)
            counts["note"] += 1
        else:
            counts["skipped"] += 1

    return counts


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for _ in _iter_lines(path))


def preview(path: Path, limit: int = 5) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line_no, line in enumerate(_iter_lines(path), start=1):
        if len(out) >= limit:
            break
        data = _load_line(line, line_no)
        out.append({"_type": data.get("_type", "?"), "keys": sorted(data.keys())[:8]})
    return out
