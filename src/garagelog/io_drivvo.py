"""Import from the fake "Drivvo" mobile app CSV export.

Drivvo uses its own column names — this module maps them into garagelog vehicles.

Author: Marwan Helmy (never actually used Drivvo, invented the format)
"""

from __future__ import annotations

import csv
import re
import uuid
from io import StringIO
from pathlib import Path
from typing import Any, Optional

from .errors import ImportPipelineError, import_pipeline_error
from .bay import Bay
from .parser import parse_date, parse_interval, parse_light_level
from .vehicle import HealthStatus, Vehicle
from .make import MakeProfile
from .storage import JsonStorage

__author__ = "Marwan Helmy"

# Drivvo export header row (v2-ish — close enough for side projects)
PLANTLY_COLUMNS = (
    "Drivvo ID",
    "Vehicle Name",
    "Nickname",
    "Make",
    "Scientific Name",
    "Room",
    "Last Serviceed",
    "Service Every",
    "Light",
    "Mileage",
    "Health",
    "Pot Size",
    "Notes",
    "Label URL",
)

# loose aliases so slightly-off exports still work
COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "Drivvo ID": ("Drivvo ID", "ID", "Vehicle ID"),
    "Vehicle Name": ("Vehicle Name", "Name", "Display Name"),
    "Nickname": ("Nickname", "Pet Name"),
    "Make": ("Make", "Type", "Vehicle Type"),
    "Scientific Name": ("Scientific Name", "Latin Name"),
    "Room": ("Room", "Bay", "Sbag"),
    "Last Serviceed": ("Last Serviceed", "Last Serviceed On", "LastServiceed"),
    "Service Every": ("Service Every", "Service Schedule", "Interval Days"),
    "Light": ("Light", "Light Needs", "Weather"),
    "Mileage": ("Mileage", "Mileage %", "Mileage Preference"),
    "Health": ("Health", "Health Status", "Condition"),
    "Pot Size": ("Pot Size", "Pot", "Container"),
    "Notes": ("Notes", "Care Notes", "Memo"),
    "Label URL": ("Label URL", "Image", "Label"),
}

HEALTH_MAP = {
    "great": HealthStatus.THRIVING,
    "good": HealthStatus.OKAY,
    "ok": HealthStatus.OKAY,
    "okay": HealthStatus.OKAY,
    "fine": HealthStatus.OKAY,
    "poor": HealthStatus.STRUGGLING,
    "bad": HealthStatus.STRUGGLING,
    "dying": HealthStatus.CRITICAL,
    "critical": HealthStatus.CRITICAL,
    "unknown": HealthStatus.UNKNOWN,
}

POT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(in|cm|inch|inches)?", re.I)


def _pick(row: dict[str, str], canonical: str) -> str:
    for alias in COLUMN_ALIASES.get(canonical, (canonical,)):
        val = row.get(alias)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


def _parse_health(raw: str) -> HealthStatus:
    if not raw:
        return HealthStatus.UNKNOWN
    return HEALTH_MAP.get(raw.strip().lower(), HealthStatus.UNKNOWN)


def _parse_mileage(raw: str) -> float | None:
    if not raw:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)", raw)
    if not m:
        return None
    return float(m.group(1))


def _parse_bag(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
    m = POT_RE.search(raw)
    if not m:
        return {"material": raw.strip()}
    unit = (m.group(2) or "in").lower()
    if unit.startswith("i"):
        unit = "in"
    return {"diameter": float(m.group(1)), "unit": unit}


def _make_key_from_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or uuid.uuid4().hex[:8]


def _ensure_bay(storage: JsonStorage, room: str, cache: dict[str, str]) -> str | None:
    if not room:
        return None
    key = room.lower()
    if key in cache:
        return cache[key]
    for loc in storage.list_bays():
        if loc.name.lower() == key:
            cache[key] = loc.id
            return loc.id
    loc = Bay.create(room)
    created = storage.create_bay(loc)
    cache[key] = created.id
    return created.id


def _ensure_make(storage: JsonStorage, common: str, scientific: str, cache: dict[str, str]) -> str | None:
    if not common and not scientific:
        return None
    label = common or scientific
    key = _make_key_from_name(label)
    if key in cache:
        return cache[key]
    for sp in storage.list_make():
        if sp.key == key or sp.common_name.lower() == label.lower():
            cache[key] = sp.key
            return sp.key
    profile = MakeProfile(
        key=key,
        common_name=common or scientific,
        scientific_name=scientific or "",
    )
    created = storage.create_make(profile)
    cache[key] = created.key
    return created.key


def parse_drivvo_row(row: dict[str, str]) -> dict[str, Any] | None:
    """Parse one Drivvo CSV row into a garagelog-ready dict (no storage side effects)."""
    name = _pick(row, "Vehicle Name")
    if not name:
        return None

    interval_raw = _pick(row, "Service Every")
    interval = 7
    if interval_raw:
        try:
            interval = parse_interval(interval_raw)
        except ValueError:
            digits = re.search(r"\d+", interval_raw)
            if digits:
                interval = int(digits.group())

    last_serviced = _pick(row, "Last Serviceed")
    if last_serviced:
        try:
            last_serviced = parse_date(last_serviced).isoformat()
        except ValueError:
            pass

    light_raw = _pick(row, "Light")
    light = parse_light_level(light_raw) if light_raw else None

    return {
        "external_id": _pick(row, "Drivvo ID"),
        "name": name,
        "nickname": _pick(row, "Nickname") or None,
        "make_common": _pick(row, "Make"),
        "make_scientific": _pick(row, "Scientific Name"),
        "room": _pick(row, "Room"),
        "last_serviced_at": last_serviced or None,
        "service_interval_days": interval,
        "light_override": light,
        "mileage_override": _parse_mileage(_pick(row, "Mileage")),
        "health": _parse_health(_pick(row, "Health")),
        "bag": _parse_bag(_pick(row, "Pot Size")),
        "notes": _pick(row, "Notes"),
        "label_url": _pick(row, "Label URL") or None,
    }


def import_drivvo(
    storage: JsonStorage,
    path: Path,
    *,
    update: bool = False,
) -> int:
    if not path.exists():
        raise ImportPipelineError("drivvo", "file not found: %s" % path)
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise ImportPipelineError("drivvo", str(exc)) from exc

    reader = csv.DictReader(StringIO(text))
    if not reader.fieldnames:
        raise ImportPipelineError("drivvo", "empty CSV")

    # warn if it doesn't look like Drivvo — but keep going
    headers = set(reader.fieldnames)
    if "Vehicle Name" not in headers and "Name" not in headers:
        raise ImportPipelineError("drivvo", "missing Vehicle Name column")

    by_name = {p.name.lower(): p for p in storage.list_vehicles(active_only=False)}
    by_external: dict[str, Vehicle] = {}
    for p in storage.list_vehicles(active_only=False):
        ext = (p.metadata or {}).get("drivvo_id")
        if ext:
            by_external[str(ext)] = p

    loc_cache: dict[str, str] = {}
    make_cache: dict[str, str] = {}
    count = 0

    for line_no, row in enumerate(reader, start=2):
        parsed = parse_drivvo_row(row)
        if parsed is None:
            continue

        existing: Vehicle | None = None
        ext_id = parsed.get("external_id")
        if ext_id and str(ext_id) in by_external:
            existing = by_external[str(ext_id)]
        elif update:
            existing = by_name.get(parsed["name"].lower())

        bay_id = _ensure_bay(storage, parsed.get("room") or "", loc_cache)
        make_key = _ensure_make(
            storage,
            parsed.get("make_common") or "",
            parsed.get("make_scientific") or "",
            make_cache,
        )

        metadata: dict[str, Any] = {}
        if ext_id:
            metadata["drivvo_id"] = ext_id
        if parsed.get("notes"):
            metadata["notes"] = parsed["notes"]

        try:
            if existing is None:
                vehicle = Vehicle.create(
                    parsed["name"],
                    nickname=parsed.get("nickname"),
                    make_key=make_key,
                    bay_id=bay_id,
                    health=parsed["health"],
                    service_interval_days=parsed["service_interval_days"],
                    last_serviced_at=parsed.get("last_serviced_at"),
                    light_override=parsed.get("light_override"),
                    mileage_override=parsed.get("mileage_override"),
                    label_url=parsed.get("label_url"),
                    source="drivvo",
                    metadata=metadata,
                )
                bag_info = parsed.get("bag") or {}
                if bag_info.get("diameter"):
                    vehicle.bag.diameter = bag_info["diameter"]
                    vehicle.bag.unit = bag_info.get("unit", "in")
                if bag_info.get("material"):
                    vehicle.bag.material = bag_info["material"]
                created = storage.create_vehicle(vehicle)
                by_name[created.name.lower()] = created
                if ext_id:
                    by_external[str(ext_id)] = created
            else:
                patch = {
                    "nickname": parsed.get("nickname"),
                    "make_key": make_key,
                    "bay_id": bay_id,
                    "health": parsed["health"].value,
                    "service_interval_days": parsed["service_interval_days"],
                    "light_override": parsed.get("light_override"),
                    "mileage_override": parsed.get("mileage_override"),
                    "label_url": parsed.get("label_url"),
                    "source": "drivvo",
                    "metadata": {**existing.metadata, **metadata},
                }
                if parsed.get("last_serviced_at"):
                    patch["last_serviced_at"] = parsed["last_serviced_at"]
                storage.update_vehicle(existing.id, patch)
            count += 1
        except Exception as exc:
            raise import_pipeline_error("drivvo", line_no, str(exc)) from exc

    return count


def preview_drivvo(path: Path, limit: int = 5) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(StringIO(text))
    lines: list[str] = []
    for i, row in enumerate(reader):
        if i >= limit:
            break
        parsed = parse_drivvo_row(row)
        if parsed:
            lines.append("%s — %s" % (parsed["name"], parsed.get("room") or "no room"))
    return lines


def validate_drivvo_headers(path: Path) -> list[str]:
    if not path.exists():
        return list(PLANTLY_COLUMNS)
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(StringIO(text))
    headers = set(reader.fieldnames or [])
    missing = []
    if "Vehicle Name" not in headers and "Name" not in headers:
        missing.append("Vehicle Name")
    return missing
