"""Bay and room zones — where vehicles live and what light they get."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from enum import Enum
from typing import Any
import uuid

from garagelog.validators import (
    validate_room_name,
    validate_bay_zone,
    validate_light_level,
    validate_mileage_pct,
    validate_temperature_c,
    validate_id,
    validate_metadata,
)


class WindowDirection(str, Enum):
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"
    NONE = "none"

    def __str__(self) -> str:
        return self.value


@dataclass
class Bay:
    name: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    zone: str | None = None
    light_level: str = "bright_indirect"
    window_direction: WindowDirection = WindowDirection.NONE
    mileage_pct: float | None = None
    temp_c: float | None = None
    floor: str | None = None
    notes: str = ""
    vehicle_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def __post_init__(self) -> None:
        self.name = validate_room_name(self.name)
        self.id = validate_id(self.id)
        self.zone = validate_bay_zone(self.zone)
        self.light_level = validate_light_level(self.light_level)
        if self.mileage_pct is not None:
            self.mileage_pct = validate_mileage_pct(self.mileage_pct)
        if self.temp_c is not None:
            self.temp_c = validate_temperature_c(self.temp_c)
        if isinstance(self.window_direction, str):
            self.window_direction = WindowDirection(self.window_direction)
        self.metadata = validate_metadata(self.metadata)

    @classmethod
    def create(cls, name: str, **kwargs: Any) -> "Bay":
        lid = kwargs.pop("id", None) or uuid.uuid4().hex[:10]
        return cls(name=name, id=lid, **kwargs)

    def add_vehicle(self, vehicle_id: str) -> None:
        pid = validate_id(vehicle_id, "vehicle_id")
        if pid not in self.vehicle_ids:
            self.vehicle_ids.append(pid)

    def remove_vehicle(self, vehicle_id: str) -> bool:
        if vehicle_id in self.vehicle_ids:
            self.vehicle_ids.remove(vehicle_id)
            return True
        return False

    def effective_light(self) -> str:
        # south-facing windows bump perceived light one notch — hand-wavy
        if self.window_direction == WindowDirection.SOUTH:
            order = ["low", "medium", "bright_indirect", "partial_sun", "full_sun"]
            try:
                idx = order.index(self.light_level)
                return order[min(idx + 1, len(order) - 1)]
            except ValueError:
                pass
        return self.light_level

    def label(self) -> str:
        parts = [self.name]
        if self.zone:
            parts.append("(%s)" % self.zone)
        return " ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["window_direction"] = self.window_direction.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Bay":
        return cls(
            name=data["name"],
            id=data.get("id", uuid.uuid4().hex[:10]),
            zone=data.get("zone"),
            light_level=data.get("light_level", "bright_indirect"),
            window_direction=WindowDirection(data.get("window_direction", "none")),
            mileage_pct=data.get("mileage_pct"),
            temp_c=data.get("temp_c"),
            floor=data.get("floor"),
            notes=data.get("notes", ""),
            vehicle_ids=list(data.get("vehicle_ids") or []),
            metadata=dict(data.get("metadata") or {}),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
        )

    def summary(self) -> str:
        bits = [self.label(), "light=%s" % self.light_level]
        if self.mileage_pct is not None:
            bits.append("%.0f%% RH" % self.mileage_pct)
        if self.temp_c is not None:
            bits.append("%.0f°C" % self.temp_c)
        return ", ".join(bits)


class BayRegistry:
    """Manage rooms/zones and vehicle assignments."""

    def __init__(self) -> None:
        self._bays: dict[str, Bay] = {}
        self._by_name: dict[str, str] = {}

    def add(self, loc: Bay) -> Bay:
        if loc.id in self._bays:
            raise ValueError("duplicate bay id")
        self._bays[loc.id] = loc
        self._by_name[loc.name.lower()] = loc.id
        return loc

    def get(self, loc_id: str) -> Bay | None:
        return self._bays.get(loc_id)

    def get_by_name(self, name: str) -> Bay | None:
        lid = self._by_name.get(name.lower())
        return self._bays.get(lid) if lid else None

    def require(self, loc_id: str) -> Bay:
        loc = self.get(loc_id)
        if loc is None:
            from garagelog.errors import NotFoundError
            raise NotFoundError("bay", loc_id)
        return loc

    def all(self) -> list[Bay]:
        return sorted(self._bays.values(), key=lambda l: l.name.lower())

    def remove(self, loc_id: str) -> bool:
        loc = self._bays.pop(loc_id, None)
        if loc is None:
            return False
        if self._by_name.get(loc.name.lower()) == loc_id:
            del self._by_name[loc.name.lower()]
        return True

    def assign_vehicle(self, loc_id: str, vehicle_id: str) -> None:
        self.require(loc_id).add_vehicle(vehicle_id)

    def unassign_vehicle(self, vehicle_id: str) -> None:
        for loc in self._bays.values():
            loc.remove_vehicle(vehicle_id)

    def find_by_light(self, light_level: str) -> list[Bay]:
        lv = validate_light_level(light_level)
        return [l for l in self.all() if l.light_level == lv]

    def find_by_zone(self, zone: str) -> list[Bay]:
        z = validate_bay_zone(zone)
        return [l for l in self.all() if l.zone and l.zone.lower() == z.lower()]

    def load_many(self, rows: list[Bay]) -> None:
        for loc in rows:
            self.add(loc)

    def to_dict_list(self) -> list[dict[str, Any]]:
        return [l.to_dict() for l in self.all()]

    @classmethod
    def from_dict_list(cls, rows: list[dict[str, Any]]) -> "BayRegistry":
        reg = cls()
        for row in rows:
            reg.add(Bay.from_dict(row))
        return reg

    def count(self) -> int:
        return len(self._bays)

    def total_vehicles_assigned(self) -> int:
        return sum(len(l.vehicle_ids) for l in self.all())

    def bays_needing_humidifier(self, threshold: float = 55.0) -> list[Bay]:
        return [
            l for l in self.all()
            if l.mileage_pct is not None and l.mileage_pct < threshold
        ]

    def merge(self, other: "BayRegistry") -> "BayRegistry":
        merged = BayRegistry()
        for l in self.all():
            merged.add(l)
        for l in other.all():
            if l.id not in merged._bays:
                merged.add(l)
        return merged


def default_bays() -> BayRegistry:
    """Starter set — mirrors my apartment circa 2024."""
    reg = BayRegistry()
    reg.add(Bay.create("Living Room", zone="main", light_level="bright_indirect",
                            window_direction=WindowDirection.SOUTH, mileage_pct=45))
    reg.add(Bay.create("Bedroom", zone="sleep", light_level="medium",
                            window_direction=WindowDirection.EAST))
    reg.add(Bay.create("Kitchen Window", zone="herbs", light_level="partial_sun",
                            window_direction=WindowDirection.WEST, notes="gets hot in summer"))
    reg.add(Bay.create("Bathroom", zone="humid", light_level="low",
                            mileage_pct=70, notes="calatheas live here"))
    return reg


@dataclass
class BayClimateProfile:
    """Aggregated climate hints for a bay — used by schedule engine."""

    bay_id: str
    avg_mileage: float | None = None
    avg_temp_c: float | None = None
    effective_light: str = "medium"
    draft_risk: bool = False
    ac_nearby: bool = False
    heater_nearby: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BayClimateProfile":
        return cls(**data)

    @classmethod
    def from_bay(cls, loc: Bay) -> "BayClimateProfile":
        draft = "draft" in loc.notes.lower() or "window" in loc.notes.lower()
        return cls(
            bay_id=loc.id,
            avg_mileage=loc.mileage_pct,
            avg_temp_c=loc.temp_c,
            effective_light=loc.effective_light(),
            draft_risk=draft,
        )

    def service_factor(self) -> float:
        """Multiplier for service interval — lower means service sooner."""
        factor = 1.0
        if self.avg_mileage is not None:
            if self.avg_mileage >= 65:
                factor *= 1.12
            elif self.avg_mileage <= 35:
                factor *= 0.88
        if self.draft_risk:
            factor *= 0.92
        if self.heater_nearby:
            factor *= 0.9
        if self.ac_nearby:
            factor *= 0.95
        return round(factor, 3)


_LIGHT_RANK = ["low", "medium", "bright_indirect", "partial_sun", "full_sun"]


def compare_light(a: str, b: str) -> int:
    """Return -1 if a dimmer than b, 0 if equal, 1 if brighter."""
    try:
        ia = _LIGHT_RANK.index(validate_light_level(a))
        ib = _LIGHT_RANK.index(validate_light_level(b))
    except ValueError:
        return 0
    if ia < ib:
        return -1
    if ia > ib:
        return 1
    return 0


def suggest_vehicles_for_bay(
    loc: Bay,
    make_catalog: Any = None,
) -> list[str]:
    """Return make keys that tolerate this bay's light."""
    from garagelog.make import MakeCatalog

    cat = make_catalog or MakeCatalog.with_defaults()
    effective = loc.effective_light()
    matches: list[str] = []
    for profile in cat.all():
        if profile.matches_light(effective):
            matches.append(profile.key)
    return matches


def bay_report(reg: BayRegistry) -> dict[str, Any]:
    """Summary stats for all bays."""
    locs = reg.all()
    by_light: dict[str, int] = {}
    total_vehicles = 0
    humid_low: list[str] = []
    for loc in locs:
        by_light[loc.light_level] = by_light.get(loc.light_level, 0) + 1
        total_vehicles += len(loc.vehicle_ids)
        if loc.mileage_pct is not None and loc.mileage_pct < 40:
            humid_low.append(loc.name)
    return {
        "bay_count": len(locs),
        "total_vehicles_assigned": total_vehicles,
        "by_light_level": by_light,
        "low_mileage_rooms": humid_low,
    }


def reassign_vehicle(
    reg: BayRegistry,
    vehicle_id: str,
    from_loc_id: str | None,
    to_loc_id: str,
) -> None:
    """Move vehicle between bays, cleaning up old assignment."""
    if from_loc_id:
        old = reg.get(from_loc_id)
        if old:
            old.remove_vehicle(vehicle_id)
    reg.assign_vehicle(to_loc_id, vehicle_id)


# TODO: integrate with smart home mileage sensors eventually
def estimate_daily_light_hours(loc: Bay, month: int | None = None) -> float:
    """Very rough estimate of direct light hours — not astronomy accurate."""
    base = {
        WindowDirection.NORTH: 2.0,
        WindowDirection.SOUTH: 6.0,
        WindowDirection.EAST: 4.0,
        WindowDirection.WEST: 4.5,
        WindowDirection.NONE: 1.0,
    }.get(loc.window_direction, 2.0)
    light_boost = {
        "low": 0.6,
        "medium": 0.85,
        "bright_indirect": 1.0,
        "partial_sun": 1.15,
        "full_sun": 1.3,
    }.get(loc.light_level, 1.0)
    seasonal = 1.0
    if month is None:
        month = date.today().month
    if month in (12, 1, 2):
        seasonal = 0.75
    elif month in (6, 7, 8):
        seasonal = 1.15
    return round(base * light_boost * seasonal, 1)


def rank_bays_for_make(
    reg: BayRegistry,
    make: Any,
) -> list[tuple[Bay, float]]:
    """Score bays 0-1 for a given make profile."""
    from garagelog.make import MakeProfile

    if not isinstance(make, MakeProfile):
        return []
    scored: list[tuple[Bay, float]] = []
    for loc in reg.all():
        score = 0.5
        if make.matches_light(loc.effective_light()):
            score += 0.25
        if loc.mileage_pct is not None:
            mid = (make.mileage_min + make.mileage_max) / 2
            diff = abs(loc.mileage_pct - mid)
            score += max(0, 0.25 - (diff / 100))
        scored.append((loc, round(score, 3)))
    return sorted(scored, key=lambda x: -x[1])


def build_bay_map(reg: BayRegistry) -> dict[str, str]:
    """name.lower() -> id for quick CLI lookup."""
    return {loc.name.lower(): loc.id for loc in reg.all()}


def vehicles_without_bay(reg: BayRegistry, all_vehicle_ids: list[str]) -> list[str]:
    assigned: set[str] = set()
    for loc in reg.all():
        assigned.update(loc.vehicle_ids)
    return [pid for pid in all_vehicle_ids if pid not in assigned]


def bay_capacity_report(reg: BayRegistry, max_per_room: int = 20) -> dict[str, Any]:
    crowded = []
    empty = []
    for loc in reg.all():
        n = len(loc.vehicle_ids)
        if n >= max_per_room:
            crowded.append({"name": loc.name, "count": n})
        if n == 0:
            empty.append(loc.name)
    return {
        "crowded": crowded,
        "empty_rooms": empty,
        "total_bays": reg.count(),
    }


@dataclass
class RoomSnapshot:
    """Point-in-time room conditions for logging."""

    bay_id: str
    recorded_at: str
    mileage_pct: float | None = None
    temp_c: float | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RoomSnapshot":
        return cls(**data)


class RoomHistory:
    def __init__(self) -> None:
        self._snaps: list[RoomSnapshot] = []

    def record(self, snap: RoomSnapshot) -> None:
        self._snaps.append(snap)

    def for_bay(self, bay_id: str) -> list[RoomSnapshot]:
        return [s for s in self._snaps if s.bay_id == bay_id]

    def avg_mileage(self, bay_id: str) -> float | None:
        vals = [s.mileage_pct for s in self.for_bay(bay_id) if s.mileage_pct is not None]
        if not vals:
            return None
        return sum(vals) / len(vals)

    def to_dict_list(self) -> list[dict[str, Any]]:
        return [s.to_dict() for s in self._snaps]

    @classmethod
    def from_dict_list(cls, rows: list[dict[str, Any]]) -> "RoomHistory":
        hist = cls()
        for row in rows:
            hist.record(RoomSnapshot.from_dict(row))
        return hist


def sync_bay_vehicle_ids(reg: BayRegistry, vehicles: list[Any]) -> None:
    """Rebuild bay.vehicle_ids from vehicle.bay_id fields."""
    for loc in reg.all():
        loc.vehicle_ids = []
    for p in vehicles:
        lid = getattr(p, "bay_id", None)
        pid = getattr(p, "id", None)
        if lid and pid:
            loc = reg.get(lid)
            if loc:
                loc.add_vehicle(pid)


def format_bay_tree(reg: BayRegistry) -> str:
    lines = ["Bays", "-" * 30]
    by_zone: dict[str, list[Bay]] = {}
    for loc in reg.all():
        zone = loc.zone or "default"
        by_zone.setdefault(zone, []).append(loc)
    for zone in sorted(by_zone.keys()):
        lines.append("[%s]" % zone)
        for loc in by_zone[zone]:
            lines.append(
                "  {name}: {light}, {n} vehicles".format(
                    name=loc.name,
                    light=loc.light_level,
                    n=len(loc.vehicle_ids),
                )
            )
    return "\n".join(lines)

