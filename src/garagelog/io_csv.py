"""CSV import/export for vehicles and service logs.

Author: Marwan Helmy — started as a quick spreadsheet escape hatch.
"""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
from typing import Any, Optional

from .errors import ExportError, ImportPipelineError, ValidationError, import_pipeline_error
from .parser import parse_date, parse_interval, parse_amount_ml
from .vehicle import HealthStatus, Vehicle
from .storage import JsonStorage
from .service import ServiceEvent

__author__ = "Marwan Helmy"

PLANT_FIELDS = [
    "id",
    "name",
    "nickname",
    "make_key",
    "bay_id",
    "health",
    "health_score",
    "service_interval_days",
    "service_amount_ml",
    "last_serviced_at",
    "acquired_at",
    "light_override",
    "mileage_override",
    "archived",
    "source",
    "notes",
]

WATERING_FIELDS = [
    "id",
    "vehicle_id",
    "vehicle_name",
    "serviced_at",
    "amount_ml",
    "method",
    "service_quality",
    "runoff",
    "skipped",
    "skip_reason",
    "notes",
]


def _read_csv_text(path: Path) -> str:
    if not path.exists():
        raise ImportPipelineError("csv", "file not found: %s" % path)
    try:
        return path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise ImportPipelineError("csv", str(exc)) from exc


def _parse_bool(raw: Optional[str]) -> bool:
    if not raw:
        return False
    return raw.strip().lower() in ("1", "true", "yes", "y")


def _parse_health(raw: Optional[str]) -> HealthStatus:
    if not raw:
        return HealthStatus.UNKNOWN
    key = raw.strip().lower().replace(" ", "_")
    try:
        return HealthStatus(key)
    except ValueError:
        return HealthStatus.UNKNOWN


def _vehicle_lookup(storage: JsonStorage) -> tuple[dict[str, Vehicle], dict[str, Vehicle]]:
    by_id = {p.id: p for p in storage.list_vehicles(active_only=False)}
    by_name: dict[str, Vehicle] = {}
    for p in by_id.values():
        by_name.setdefault(p.name.lower(), p)
        if p.nickname:
            by_name.setdefault(p.nickname.lower(), p)
    return by_id, by_name


def _resolve_vehicle_id(
    by_id: dict[str, Vehicle],
    by_name: dict[str, Vehicle],
    vehicle_id: Optional[str],
    vehicle_name: Optional[str],
) -> Optional[str]:
    if vehicle_id and vehicle_id in by_id:
        return vehicle_id
    if vehicle_name:
        hit = by_name.get(vehicle_name.strip().lower())
        if hit:
            return hit.id
    return vehicle_id


def export_vehicles_csv(storage: JsonStorage, dest: Path) -> int:
    """Write all vehicles (including archived) to a CSV file."""
    try:
        with dest.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=PLANT_FIELDS)
            writer.writeheader()
            count = 0
            for vehicle in storage.list_vehicles(active_only=False):
                notes = str(vehicle.metadata.get("notes", ""))
                writer.writerow({
                    "id": vehicle.id,
                    "name": vehicle.name,
                    "nickname": vehicle.nickname or "",
                    "make_key": vehicle.make_key or "",
                    "bay_id": vehicle.bay_id or "",
                    "health": vehicle.health.value,
                    "health_score": vehicle.health_score,
                    "service_interval_days": vehicle.service_interval_days,
                    "service_amount_ml": vehicle.service_amount_ml or "",
                    "last_serviced_at": vehicle.last_serviced_at or "",
                    "acquired_at": vehicle.acquired_at or "",
                    "light_override": vehicle.light_override or "",
                    "mileage_override": vehicle.mileage_override or "",
                    "archived": "yes" if vehicle.archived else "no",
                    "source": vehicle.source,
                    "notes": notes.replace("\n", " "),
                })
                count += 1
        return count
    except OSError as exc:
        raise ExportError("csv", str(exc)) from exc


def export_service_csv(storage: JsonStorage, dest: Path) -> int:
    """Write service events with vehicle names for human-readable spreadsheets."""
    vehicle_names = {p.id: p.name for p in storage.list_vehicles(active_only=False)}
    try:
        with dest.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=WATERING_FIELDS)
            writer.writeheader()
            count = 0
            for row in storage.list_service_events():
                writer.writerow({
                    "id": row.get("id", ""),
                    "vehicle_id": row.get("vehicle_id", ""),
                    "vehicle_name": vehicle_names.get(row.get("vehicle_id", ""), ""),
                    "serviced_at": row.get("serviced_at", ""),
                    "amount_ml": row.get("amount_ml") or "",
                    "method": row.get("method", "top_service"),
                    "service_quality": row.get("service_quality", "tap"),
                    "runoff": "yes" if row.get("runoff") else "no",
                    "skipped": "yes" if row.get("skipped") else "no",
                    "skip_reason": row.get("skip_reason", ""),
                    "notes": (row.get("notes") or "").replace("\n", " "),
                })
                count += 1
        return count
    except OSError as exc:
        raise ExportError("csv", str(exc)) from exc


def export_csv_bundle(storage: JsonStorage, dest: Path) -> tuple[int, int]:
    """Export vehicles.csv and service.csv beside dest stem."""
    vehicles_path = dest.with_name(dest.stem + "_vehicles.csv")
    service_path = dest.with_name(dest.stem + "_service.csv")
    return export_vehicles_csv(storage, vehicles_path), export_service_csv(storage, service_path)


def import_vehicles_csv(
    storage: JsonStorage,
    src: Path,
    *,
    update: bool = False,
) -> int:
    """Import vehicles from CSV; skips blank name rows."""
    text = _read_csv_text(src)
    reader = csv.DictReader(StringIO(text))
    if not reader.fieldnames or "name" not in reader.fieldnames:
        raise ImportPipelineError("csv", "missing required column: name")

    existing = {p.id: p for p in storage.list_vehicles(active_only=False)}
    by_name = {p.name.lower(): p for p in existing.values()}
    count = 0

    for line_no, row in enumerate(reader, start=2):
        name = (row.get("name") or "").strip()
        if not name:
            continue
        pid = (row.get("id") or "").strip()
        vehicle: Vehicle | None = None
        if pid and pid in existing:
            vehicle = existing[pid]
        elif update:
            vehicle = by_name.get(name.lower())

        try:
            interval_raw = row.get("service_interval_days")
            interval = parse_interval(str(interval_raw)) if interval_raw else 7
            health = _parse_health(row.get("health"))
            metadata = {}
            notes = (row.get("notes") or "").strip()
            if notes:
                metadata["notes"] = notes

            if vehicle is None:
                vehicle = Vehicle.create(
                    name,
                    id=pid or None,
                    nickname=(row.get("nickname") or "").strip() or None,
                    make_key=(row.get("make_key") or "").strip() or None,
                    bay_id=(row.get("bay_id") or "").strip() or None,
                    health=health,
                    service_interval_days=interval,
                    last_serviced_at=(row.get("last_serviced_at") or "").strip() or None,
                    acquired_at=(row.get("acquired_at") or "").strip() or None,
                    light_override=(row.get("light_override") or "").strip() or None,
                    archived=_parse_bool(row.get("archived")),
                    source="csv",
                    metadata=metadata,
                )
                hs = row.get("health_score")
                if hs and str(hs).isdigit():
                    vehicle.health_score = int(hs)
                amt = row.get("service_amount_ml")
                if amt:
                    vehicle.service_amount_ml = parse_amount_ml(str(amt))
                hum = row.get("mileage_override")
                if hum:
                    vehicle.mileage_override = float(hum)
                created = storage.create_vehicle(vehicle)
                existing[created.id] = created
                by_name[created.name.lower()] = created
            else:
                patch: dict[str, Any] = {
                    "name": name,
                    "nickname": (row.get("nickname") or "").strip() or None,
                    "make_key": (row.get("make_key") or "").strip() or None,
                    "bay_id": (row.get("bay_id") or "").strip() or None,
                    "health": health.value,
                    "service_interval_days": interval,
                    "archived": _parse_bool(row.get("archived")),
                    "source": "csv",
                    "metadata": {**vehicle.metadata, **metadata},
                }
                lw = (row.get("last_serviced_at") or "").strip()
                if lw:
                    patch["last_serviced_at"] = lw
                updated = storage.update_vehicle(vehicle.id, patch)
                existing[updated.id] = updated
            count += 1
        except (ValidationError, ValueError) as exc:
            raise import_pipeline_error("csv", line_no, str(exc)) from exc

    return count


def import_service_csv(storage: JsonStorage, src: Path) -> int:
    """Import service events; resolves vehicle_name when vehicle_id missing."""
    text = _read_csv_text(src)
    reader = csv.DictReader(StringIO(text))
    if not reader.fieldnames:
        raise ImportPipelineError("csv", "empty or headerless file")

    by_id, by_name = _vehicle_lookup(storage)
    count = 0

    for line_no, row in enumerate(reader, start=2):
        vehicle_id = _resolve_vehicle_id(
            by_id,
            by_name,
            (row.get("vehicle_id") or "").strip() or None,
            (row.get("vehicle_name") or "").strip() or None,
        )
        if not vehicle_id:
            raise import_pipeline_error("csv", line_no, "vehicle_id or vehicle_name required")

        try:
            storage.get_vehicle(vehicle_id)
        except Exception:
            raise import_pipeline_error("csv", line_no, "unknown vehicle %s" % vehicle_id)

        serviced_at = (row.get("serviced_at") or "").strip()
        if serviced_at:
            try:
                serviced_at = parse_date(serviced_at).isoformat()
            except ValueError:
                pass  # keep raw ISO if already formatted

        amount_ml = None
        amt_raw = row.get("amount_ml")
        if amt_raw not in (None, ""):
            try:
                amount_ml = parse_amount_ml(str(amt_raw))
            except ValueError:
                raise import_pipeline_error("csv", line_no, "bad amount_ml: %s" % amt_raw)

        event = ServiceEvent.create(
            vehicle_id=vehicle_id,
            id=(row.get("id") or "").strip() or None,
            serviced_at=serviced_at or None,
            amount_ml=amount_ml,
            method=(row.get("method") or "top_service").strip(),
            runoff=_parse_bool(row.get("runoff")),
            skipped=_parse_bool(row.get("skipped")),
            skip_reason=(row.get("skip_reason") or "").strip(),
            notes=(row.get("notes") or "").strip(),
        )
        if row.get("service_quality"):
            event.service_quality = row["service_quality"].strip()  # type: ignore[assignment]
        storage.create_service_event(event.to_dict())
        count += 1

    return count


def validate_csv_headers(path: Path, kind: str = "vehicles") -> list[str]:
    """Return missing required columns for vehicles or service CSV."""
    if not path.exists():
        return ["name"] if kind == "vehicles" else ["vehicle_id"]
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(StringIO(text))
    headers = reader.fieldnames or []
    if kind == "vehicles":
        required = ["name"]
    else:
        required = []  # vehicle_name OR vehicle_id
        if "vehicle_id" not in headers and "vehicle_name" not in headers:
            return ["vehicle_id or vehicle_name"]
        return []
    return [h for h in required if h not in headers]


def sample_rows(path: Path, n: int = 3) -> list[dict[str, str]]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(StringIO(text))
    out: list[dict[str, str]] = []
    for i, row in enumerate(reader):
        if i >= n:
            break
        out.append({k: (v or "") for k, v in row.items()})
    return out
