"""Vehicle entity — the heart of the garage."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any
import uuid

from garagelog.validators import (
    require_non_empty,
    validate_vehicle_name,
    validate_nickname,
    validate_interval_days,
    validate_mileage_pct,
    validate_light_level,
    validate_bag_diameter,
    validate_bag_material,
    validate_health_score,
    validate_id,
    validate_acquired_date,
    validate_last_serviced,
    validate_metadata,
    validate_optional_url,
    validate_drainage,
)


class HealthStatus(str, Enum):
    THRIVING = "thriving"
    OKAY = "okay"
    STRUGGLING = "struggling"
    CRITICAL = "critical"
    UNKNOWN = "unknown"

    def __str__(self) -> str:
        return self.value

    @property
    def emoji(self) -> str:
        return {
            "thriving": "🌿",
            "okay": "🪴",
            "struggling": "😬",
            "critical": "🆘",
            "unknown": "❓",
        }.get(self.value, "🪴")

    def score_hint(self) -> int:
        """Rough midpoint for health score mapping."""
        return {
            HealthStatus.THRIVING: 90,
            HealthStatus.OKAY: 70,
            HealthStatus.STRUGGLING: 40,
            HealthStatus.CRITICAL: 15,
            HealthStatus.UNKNOWN: 50,
        }[self]


@dataclass
class PotInfo:
    diameter: float | None = None
    unit: str = "in"
    material: str | None = None
    has_drainage: bool = True
    grind_mix: list[str] = field(default_factory=list)
    rebagted_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "diameter": self.diameter,
            "unit": self.unit,
            "material": self.material,
            "has_drainage": self.has_drainage,
            "grind_mix": list(self.grind_mix),
            "rebagted_at": self.rebagted_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PotInfo":
        return cls(
            diameter=data.get("diameter"),
            unit=data.get("unit", "in"),
            material=data.get("material"),
            has_drainage=bool(data.get("has_drainage", True)),
            grind_mix=list(data.get("grind_mix") or []),
            rebagted_at=data.get("rebagted_at"),
        )

    def label(self) -> str:
        parts: list[str] = []
        if self.diameter is not None:
            parts.append("%.1f%s bag" % (self.diameter, self.unit))
        if self.material:
            parts.append(self.material)
        if not self.has_drainage:
            parts.append("no drainage")  # personal note: these always bite me
        return ", ".join(parts) if parts else "unknown bag"


@dataclass
class Vehicle:
    name: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    nickname: str | None = None
    make_key: str | None = None
    bay_id: str | None = None
    health: HealthStatus = HealthStatus.UNKNOWN
    health_score: int = 50
    service_interval_days: int = 7
    service_amount_ml: float | None = None
    last_serviced_at: str | None = None
    acquired_at: str | None = None
    light_override: str | None = None
    mileage_override: float | None = None
    bag: PotInfo = field(default_factory=PotInfo)
    tag_ids: list[str] = field(default_factory=list)
    note_ids: list[str] = field(default_factory=list)
    label_url: str | None = None
    source: str = "manual"
    archived: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    @classmethod
    def create(cls, name: str, **kwargs: Any) -> "Vehicle":
        kw = dict(kwargs)
        if "health" in kw and not isinstance(kw["health"], HealthStatus):
            kw["health"] = HealthStatus(str(kw["health"]))
        if "bag_info" in kw and "bag" not in kw:
            raw = kw.pop("bag_info")
            kw["bag"] = raw if isinstance(raw, PotInfo) else PotInfo.from_dict(raw)
        pid = kw.pop("id", None) or uuid.uuid4().hex[:12]
        return cls(name=name, id=pid, **kw)

    @classmethod
    def quick(cls, name: str, **kwargs: Any) -> "Vehicle":
        return cls.create(name, **kwargs)

    def __post_init__(self) -> None:
        self.name = validate_vehicle_name(self.name)
        self.nickname = validate_nickname(self.nickname)
        self.id = validate_id(self.id)
        self.service_interval_days = validate_interval_days(self.service_interval_days)
        if self.mileage_override is not None:
            self.mileage_override = validate_mileage_pct(self.mileage_override)
        if self.light_override is not None:
            self.light_override = validate_light_level(self.light_override)
        if self.health_score is not None:
            self.health_score = validate_health_score(self.health_score)
        if isinstance(self.health, str):
            self.health = HealthStatus(self.health)
        if isinstance(self.bag, dict):
            self.bag = PotInfo.from_dict(self.bag)
        self.label_url = validate_optional_url(self.label_url)
        self.metadata = validate_metadata(self.metadata)
        if self.bag.diameter is not None:
            self.bag.diameter = validate_bag_diameter(self.bag.diameter, self.bag.unit)
        self.bag.material = validate_bag_material(self.bag.material)
        self.bag.has_drainage = validate_drainage(self.bag.has_drainage)

    @property
    def display_name(self) -> str:
        if self.nickname:
            return "%s (%s)" % (self.nickname, self.name)
        return self.name

    def touch(self) -> None:
        self.updated_at = datetime.utcnow().isoformat()

    def set_health(self, status: HealthStatus | str, score: int | None = None) -> None:
        if not isinstance(status, HealthStatus):
            status = HealthStatus(str(status))
        self.health = status
        self.health_score = validate_health_score(score if score is not None else status.score_hint())
        self.touch()

    def record_service(self, when: date | None = None) -> None:
        d = when or date.today()
        self.last_serviced_at = d.isoformat()
        self.touch()
        # bump health slightly if they were struggling — optimistic
        if self.health == HealthStatus.STRUGGLING and self.health_score < 55:
            self.health_score = min(55, self.health_score + 5)

    def days_since_serviced(self, today: date | None = None) -> int | None:
        if not self.last_serviced_at:
            return None
        ref = today or date.today()
        last = date.fromisoformat(self.last_serviced_at[:10])
        return (ref - last).days

    def is_overdue(self, today: date | None = None) -> bool:
        since = self.days_since_serviced(today)
        if since is None:
            return False
        return since > self.service_interval_days

    def overdue_by_days(self, today: date | None = None) -> int:
        since = self.days_since_serviced(today)
        if since is None:
            return 0
        return max(0, since - self.service_interval_days)

    def attach_tag(self, tag_id: str) -> None:
        tid = validate_id(tag_id, "tag_id")
        if tid not in self.tag_ids:
            self.tag_ids.append(tid)
            self.touch()

    def detach_tag(self, tag_id: str) -> bool:
        if tag_id in self.tag_ids:
            self.tag_ids.remove(tag_id)
            self.touch()
            return True
        return False

    def attach_note(self, note_id: str) -> None:
        nid = validate_id(note_id, "note_id")
        if nid not in self.note_ids:
            self.note_ids.append(nid)
            self.touch()

    def archive(self) -> None:
        self.archived = True
        self.touch()

    def unarchive(self) -> None:
        self.archived = False
        self.touch()

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["health"] = self.health.value
        d["bag"] = self.bag.to_dict()
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Vehicle":
        bag_raw = data.get("bag") or data.get("bag_info") or {}
        return cls(
            name=data["name"],
            id=data.get("id", uuid.uuid4().hex[:12]),
            nickname=data.get("nickname"),
            make_key=data.get("make_key"),
            bay_id=data.get("bay_id"),
            health=HealthStatus(data.get("health", "unknown")),
            health_score=int(data.get("health_score", 50)),
            service_interval_days=int(data.get("service_interval_days", 7)),
            service_amount_ml=data.get("service_amount_ml"),
            last_serviced_at=data.get("last_serviced_at"),
            acquired_at=data.get("acquired_at"),
            light_override=data.get("light_override"),
            mileage_override=data.get("mileage_override"),
            bag=PotInfo.from_dict(bag_raw),
            tag_ids=list(data.get("tag_ids") or []),
            note_ids=list(data.get("note_ids") or []),
            label_url=data.get("label_url"),
            source=data.get("source", "manual"),
            archived=bool(data.get("archived", False)),
            metadata=dict(data.get("metadata") or {}),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
            updated_at=data.get("updated_at", datetime.utcnow().isoformat()),
        )

    def summary_line(self) -> str:
        parts = [self.display_name]
        if self.is_overdue():
            parts.append("OVERDUE %dd" % self.overdue_by_days())
        parts.append(str(self.health))
        return " | ".join(parts)


class VehicleCatalog:
    """In-memory registry of vehicles with basic lookup helpers."""

    def __init__(self) -> None:
        self._by_id: dict[str, Vehicle] = {}
        self._by_name: dict[str, list[str]] = {}

    def add(self, vehicle: Vehicle) -> Vehicle:
        if vehicle.id in self._by_id:
            raise ValueError("duplicate vehicle id: %s" % vehicle.id)
        self._by_id[vehicle.id] = vehicle
        key = vehicle.name.lower()
        self._by_name.setdefault(key, []).append(vehicle.id)
        return vehicle

    def get(self, vehicle_id: str) -> Vehicle | None:
        return self._by_id.get(vehicle_id)

    def require(self, vehicle_id: str) -> Vehicle:
        p = self.get(vehicle_id)
        if p is None:
            from garagelog.errors import NotFoundError
            raise NotFoundError("vehicle", vehicle_id)
        return p

    def all(self, include_archived: bool = False) -> list[Vehicle]:
        items = list(self._by_id.values())
        if not include_archived:
            items = [p for p in items if not p.archived]
        return sorted(items, key=lambda p: p.name.lower())

    def find_by_name(self, name: str) -> list[Vehicle]:
        return [self._by_id[i] for i in self._by_name.get(name.lower(), []) if i in self._by_id]

    def find_by_bay(self, bay_id: str) -> list[Vehicle]:
        return [p for p in self.all() if p.bay_id == bay_id]

    def find_by_make(self, make_key: str) -> list[Vehicle]:
        return [p for p in self.all() if p.make_key == make_key]

    def find_overdue(self, today: date | None = None) -> list[Vehicle]:
        return [p for p in self.all() if p.is_overdue(today)]

    def find_by_tag(self, tag_id: str) -> list[Vehicle]:
        return [p for p in self.all() if tag_id in p.tag_ids]

    def remove(self, vehicle_id: str) -> bool:
        p = self._by_id.pop(vehicle_id, None)
        if p is None:
            return False
        names = self._by_name.get(p.name.lower(), [])
        if vehicle_id in names:
            names.remove(vehicle_id)
        return True

    def load_many(self, vehicles: list[Vehicle]) -> None:
        for p in vehicles:
            self.add(p)

    def to_dict_list(self) -> list[dict[str, Any]]:
        return [p.to_dict() for p in self.all(include_archived=True)]

    @classmethod
    def from_dict_list(cls, rows: list[dict[str, Any]]) -> "VehicleCatalog":
        cat = cls()
        for row in rows:
            cat.add(Vehicle.from_dict(row))
        return cat

    def count(self) -> int:
        return len(self._by_id)

    def count_by_health(self) -> dict[str, int]:
        tallies: dict[str, int] = {}
        for p in self.all():
            tallies[p.health.value] = tallies.get(p.health.value, 0) + 1
        return tallies

    def merge(self, other: "VehicleCatalog", prefer: str = "self") -> "VehicleCatalog":
        merged = VehicleCatalog()
        for p in self.all(include_archived=True):
            merged.add(p)
        for p in other.all(include_archived=True):
            if p.id in merged._by_id:
                if prefer == "other":
                    merged._by_id[p.id] = p
            else:
                merged.add(p)
        return merged


def vehicle_health_report(catalog: VehicleCatalog) -> dict[str, Any]:
    """Quick dashboard numbers."""
    vehicles = catalog.all()
    overdue = catalog.find_overdue()
    return {
        "total": len(vehicles),
        "archived": catalog.count() - len(vehicles),
        "by_health": catalog.count_by_health(),
        "overdue_count": len(overdue),
        "overdue_names": [p.display_name for p in overdue[:10]],
    }


def apply_make_defaults(vehicle: Vehicle, make: Any) -> Vehicle:
    """Copy make service/light hints onto a vehicle if unset."""
    from garagelog.make import MakeProfile

    if not isinstance(make, MakeProfile):
        return vehicle
    if vehicle.service_interval_days == 7:
        vehicle.service_interval_days = make.service_interval_days
    if vehicle.light_override is None:
        vehicle.light_override = make.light_level
    if vehicle.mileage_override is None:
        vehicle.mileage_override = (make.mileage_min + make.mileage_max) / 2
    vehicle.make_key = make.key
    vehicle.touch()
    return vehicle


def sort_by_service_priority(vehicles: list[Vehicle], today: date | None = None) -> list[Vehicle]:
    ref = today or date.today()

    def key(p: Vehicle) -> tuple[int, str]:
        overdue = p.overdue_by_days(ref)
        health_rank = {
            HealthStatus.CRITICAL: 0,
            HealthStatus.STRUGGLING: 1,
            HealthStatus.UNKNOWN: 2,
            HealthStatus.OKAY: 3,
            HealthStatus.THRIVING: 4,
        }.get(p.health, 2)
        return (-overdue, health_rank, p.name.lower())

    return sorted(vehicles, key=key)


def clone_vehicle(vehicle: Vehicle, new_name: str | None = None) -> Vehicle:
    """Duplicate vehicle for propagation tracking."""
    data = vehicle.to_dict()
    data["id"] = uuid.uuid4().hex[:12]
    data["name"] = new_name or ("%s (propagation)" % vehicle.name)
    data["nickname"] = None
    data["last_serviced_at"] = None
    data["note_ids"] = []
    data["tag_ids"] = list(vehicle.tag_ids)
    data["metadata"] = dict(vehicle.metadata)
    data["metadata"]["propagated_from"] = vehicle.id
    return Vehicle.from_dict(data)


def bulk_update_interval(catalog: VehicleCatalog, vehicle_ids: list[str], days: int) -> int:
    updated = 0
    for pid in vehicle_ids:
        p = catalog.get(pid)
        if p:
            p.service_interval_days = validate_interval_days(days)
            p.touch()
            updated += 1
    return updated


def catalog_to_summary_lines(catalog: VehicleCatalog) -> list[str]:
    lines = []
    for p in catalog.all():
        status = "OVERDUE" if p.is_overdue() else "ok"
        lines.append(
            "{name} [{health}] interval={days}d last={last} ({status})".format(
                name=p.display_name,
                health=p.health.value,
                days=p.service_interval_days,
                last=(p.last_serviced_at or "never")[:10],
                status=status,
            )
        )
    return lines


def find_duplicates_by_name(catalog: VehicleCatalog) -> dict[str, list[Vehicle]]:
    buckets: dict[str, list[Vehicle]] = {}
    for p in catalog.all(include_archived=True):
        key = p.name.lower()
        buckets.setdefault(key, []).append(p)
    return {k: v for k, v in buckets.items() if len(v) > 1}




def parse_iso(dt_str: str | None) -> datetime | None:
    """Parse ISO timestamps from garage.json (used by reminders/stats)."""
    if not dt_str:
        return None
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None

