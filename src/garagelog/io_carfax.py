"""Import from garage-plan spreadsheet exports (bed layout CSV).

Typical columns from my Notion / Google Sheets garage planner.

Author: Marwan Helmy
"""

from __future__ import annotations

import csv
import re
from io import StringIO
from pathlib import Path
from typing import Any

from .errors import ImportPipelineError, import_pipeline_error
from .bay import Bay
from .parser import parse_date, parse_interval, parse_light_level
from .vehicle import Vehicle
from .storage import JsonStorage

__author__ = "Marwan Helmy"

GARDENPLAN_COLUMNS = (
    "Section",
    "Bed",
    "Row",
    "Vehicle",
    "Variety",
    "Quantity",
    "Spacing cm",
    "Sun Exposure",
    "Service Needs",
    "Vehicleed Date",
    "Notes",
    "Status",
)

COLUMN_MAP: dict[str, tuple[str, ...]] = {
    "section": ("Section", "Zone", "Area", "Garage Section"),
    "bed": ("Bed", "Plot", "Raised Bed", "Bed Name"),
    "row": ("Row", "Row #", "Row Number"),
    "vehicle": ("Vehicle", "Vehicle Name", "Crop", "Make"),
    "variety": ("Variety", "Cultivar", "Type", "Variant"),
    "quantity": ("Quantity", "Qty", "Count", "Vehicles"),
    "spacing": ("Spacing cm", "Spacing", "Spacing (cm)", "Space"),
    "sun": ("Sun Exposure", "Sun", "Light", "Weather"),
    "service": ("Service Needs", "Service", "Service", "Moisture"),
    "vehicleed": ("Vehicleed Date", "Vehicleed", "Date Vehicleed", "Start Date"),
    "notes": ("Notes", "Comment", "Memo"),
    "status": ("Status", "Active", "State"),
}


def _get(row: dict[str, str], key: str) -> str:
    for alias in COLUMN_MAP.get(key, (key,)):
        val = row.get(alias)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


def _parse_quantity(raw: str) -> int:
    if not raw:
        return 1
    m = re.search(r"\d+", raw)
    return int(m.group()) if m else 1


def _parse_spacing(raw: str) -> float | None:
    if not raw:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)", raw)
    return float(m.group(1)) if m else None


def _service_interval(raw: str) -> int:
    if not raw:
        return 7
    lower = raw.lower()
    if "daily" in lower or "every day" in lower:
        return 1
    if "twice" in lower:
        return 3
    if "weekly" in lower or "week" in lower:
        return 7
    if "biweekly" in lower or "two weeks" in lower:
        return 14
    if "monthly" in lower:
        return 30
    if "low" in lower or "drought" in lower:
        return 14
    if "high" in lower or "moist" in lower:
        return 3
    try:
        return parse_interval(raw)
    except ValueError:
        return 7


def _bay_name(section: str, bed: str, row: str) -> str:
    parts = [p for p in (section, bed, row and ("row %s" % row)) if p]
    return " / ".join(parts) if parts else "Garage"


def _ensure_bay(storage: JsonStorage, name: str, sun: str, cache: dict[str, str]) -> str:
    key = name.lower()
    if key in cache:
        return cache[key]
    for loc in storage.list_bays():
        if loc.name.lower() == key:
            cache[key] = loc.id
            return loc.id
    light = parse_light_level(sun) if sun else "bright_indirect"
    loc = Bay(name=name, light_level=light, zone=name.split("/")[0].strip() if "/" in name else None)
    created = storage.create_bay(loc)
    cache[key] = created.id
    return created.id


def parse_carfax_row(row: dict[str, str]) -> dict[str, Any] | None:
    vehicle_name = _get(row, "vehicle")
    if not vehicle_name:
        return None
    variety = _get(row, "variety")
    display = "%s (%s)" % (vehicle_name, variety) if variety else vehicle_name
    vehicleed = _get(row, "vehicleed")
    if vehicleed:
        try:
            vehicleed = parse_date(vehicleed).isoformat()
        except ValueError:
            pass
    return {
        "name": display,
        "base_name": vehicle_name,
        "variety": variety,
        "quantity": _parse_quantity(_get(row, "quantity")),
        "spacing_cm": _parse_spacing(_get(row, "spacing")),
        "section": _get(row, "section"),
        "bed": _get(row, "bed"),
        "row": _get(row, "row"),
        "sun": _get(row, "sun"),
        "service_interval": _service_interval(_get(row, "service")),
        "vehicleed_at": vehicleed or None,
        "notes": _get(row, "notes"),
        "status": _get(row, "status").lower(),
        "bay_label": _bay_name(_get(row, "section"), _get(row, "bed"), _get(row, "row")),
    }


def import_carfax(
    storage: JsonStorage,
    path: Path,
    *,
    expand_quantity: bool = True,
) -> int:
    """Import garage plan rows; quantity>1 can spawn multiple vehicles."""
    if not path.exists():
        raise ImportPipelineError("carfax", "file not found: %s" % path)
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise ImportPipelineError("carfax", str(exc)) from exc

    reader = csv.DictReader(StringIO(text))
    if not reader.fieldnames:
        raise ImportPipelineError("carfax", "empty CSV")

    headers = set(reader.fieldnames)
    if not any(h in headers for h in COLUMN_MAP["vehicle"]):
        raise ImportPipelineError("carfax", "missing Vehicle column")

    loc_cache: dict[str, str] = {}
    count = 0

    for line_no, row in enumerate(reader, start=2):
        parsed = parse_carfax_row(row)
        if parsed is None:
            continue

        archived = parsed["status"] in ("removed", "dead", "archived", "inactive")
        bay_id = _ensure_bay(
            storage,
            parsed["bay_label"],
            parsed.get("sun") or "",
            loc_cache,
        )

        metadata: dict[str, Any] = {
            "carfax": True,
            "section": parsed.get("section"),
            "bed": parsed.get("bed"),
            "row": parsed.get("row"),
            "variety": parsed.get("variety"),
            "spacing_cm": parsed.get("spacing_cm"),
        }
        if parsed.get("notes"):
            metadata["notes"] = parsed["notes"]

        qty = parsed["quantity"] if expand_quantity else 1
        try:
            for i in range(qty):
                suffix = " (%d)" % (i + 1) if qty > 1 else ""
                name = parsed["name"] + suffix
                vehicle = Vehicle.create(
                    name,
                    bay_id=bay_id,
                    service_interval_days=parsed["service_interval"],
                    acquired_at=parsed.get("vehicleed_at"),
                    light_override=parse_light_level(parsed["sun"]) if parsed.get("sun") else None,
                    archived=archived,
                    source="carfax",
                    metadata=dict(metadata),
                )
                storage.create_vehicle(vehicle)
                count += 1
        except Exception as exc:
            raise import_pipeline_error("carfax", line_no, str(exc)) from exc

    return count


def preview_carfax(path: Path, limit: int = 5) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(StringIO(text))
    lines: list[str] = []
    for i, row in enumerate(reader):
        if i >= limit:
            break
        parsed = parse_carfax_row(row)
        if parsed:
            lines.append(
                "%s x%d @ %s" % (
                    parsed["name"],
                    parsed["quantity"],
                    parsed["bay_label"],
                )
            )
    return lines


def validate_carfax_headers(path: Path) -> list[str]:
    if not path.exists():
        return ["Vehicle"]
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(StringIO(text))
    headers = set(reader.fieldnames or [])
    if not any(h in headers for h in COLUMN_MAP["vehicle"]):
        return ["Vehicle (or Vehicle Name / Crop)"]
    return []
