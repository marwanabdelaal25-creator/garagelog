"""Service events — track when and how much you serviced."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any
import uuid

from garagelog.validators import (
    validate_id,
    validate_service_amount_ml,
    validate_service_method,
    validate_note_body,
)


class ServiceQuality(str, Enum):
    TAP = "tap"
    FILTERED = "filtered"
    DISTILLED = "distilled"
    RAIN = "rain"
    OTHER = "other"

    def __str__(self) -> str:
        return self.value


@dataclass
class ServiceEvent:
    vehicle_id: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:14])
    serviced_at: str = field(default_factory=lambda: date.today().isoformat())
    amount_ml: float | None = None
    method: str = "top_service"
    service_quality: ServiceQuality = ServiceQuality.TAP
    runoff: bool = False
    notes: str = ""
    skipped: bool = False
    skip_reason: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def __post_init__(self) -> None:
        self.vehicle_id = validate_id(self.vehicle_id, "vehicle_id")
        self.id = validate_id(self.id)
        if self.amount_ml is not None:
            self.amount_ml = validate_service_amount_ml(self.amount_ml)
        self.method = validate_service_method(self.method)
        if isinstance(self.service_quality, str):
            self.service_quality = ServiceQuality(self.service_quality)

    @classmethod
    def create(cls, vehicle_id: str, **kwargs: Any) -> "ServiceEvent":
        eid = kwargs.pop("id", None) or uuid.uuid4().hex[:14]
        return cls(vehicle_id=vehicle_id, id=eid, **kwargs)

    @classmethod
    def skip(cls, vehicle_id: str, reason: str = "") -> "ServiceEvent":
        return cls(vehicle_id=vehicle_id, skipped=True, skip_reason=reason.strip())

    @property
    def serviced_date(self) -> date:
        return date.fromisoformat(self.serviced_at[:10])

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["service_quality"] = self.service_quality.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ServiceEvent":
        return cls(
            vehicle_id=data["vehicle_id"],
            id=data.get("id", uuid.uuid4().hex[:14]),
            serviced_at=data.get("serviced_at", date.today().isoformat()),
            amount_ml=data.get("amount_ml"),
            method=data.get("method", "top_service"),
            service_quality=ServiceQuality(data.get("service_quality", "tap")),
            runoff=bool(data.get("runoff", False)),
            notes=data.get("notes", ""),
            skipped=bool(data.get("skipped", False)),
            skip_reason=data.get("skip_reason", ""),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
        )

    def summary(self) -> str:
        if self.skipped:
            return "skipped: %s" % (self.skip_reason or "no reason")
        amt = "%.0fml" % self.amount_ml if self.amount_ml else "unknown amount"
        return "%s on %s via %s" % (amt, self.serviced_at[:10], self.method)


class ServiceLog:
    """Append-only log of service events with query helpers."""

    def __init__(self) -> None:
        self._events: dict[str, ServiceEvent] = {}
        self._by_vehicle: dict[str, list[str]] = {}

    def record(self, event: ServiceEvent) -> ServiceEvent:
        if event.id in self._events:
            raise ValueError("duplicate event id")
        self._events[event.id] = event
        self._by_vehicle.setdefault(event.vehicle_id, []).append(event.id)
        return event

    def log_service(
        self,
        vehicle_id: str,
        amount_ml: float | None = None,
        when: date | None = None,
        **kwargs: Any,
    ) -> ServiceEvent:
        ev = ServiceEvent.create(
            vehicle_id=vehicle_id,
            serviced_at=(when or date.today()).isoformat(),
            amount_ml=amount_ml,
            **kwargs,
        )
        return self.record(ev)

    def get(self, event_id: str) -> ServiceEvent | None:
        return self._events.get(event_id)

    def for_vehicle(self, vehicle_id: str) -> list[ServiceEvent]:
        ids = self._by_vehicle.get(vehicle_id, [])
        events = [self._events[i] for i in ids if i in self._events]
        return sorted(events, key=lambda e: e.serviced_at, reverse=True)

    def last_for_vehicle(self, vehicle_id: str) -> ServiceEvent | None:
        events = self.for_vehicle(vehicle_id)
        for ev in events:
            if not ev.skipped:
                return ev
        return None

    def all(self) -> list[ServiceEvent]:
        return sorted(self._events.values(), key=lambda e: e.serviced_at, reverse=True)

    def between(self, start: date, end: date) -> list[ServiceEvent]:
        out: list[ServiceEvent] = []
        for ev in self._events.values():
            d = ev.serviced_date
            if start <= d <= end:
                out.append(ev)
        return sorted(out, key=lambda e: e.serviced_at)

    def total_ml_for_vehicle(self, vehicle_id: str, days: int = 30) -> float:
        cutoff = date.today().toordinal() - days
        total = 0.0
        for ev in self.for_vehicle(vehicle_id):
            if ev.skipped or ev.amount_ml is None:
                continue
            if ev.serviced_date.toordinal() >= cutoff:
                total += ev.amount_ml
        return total

    def average_interval_days(self, vehicle_id: str) -> float | None:
        dates = [ev.serviced_date for ev in self.for_vehicle(vehicle_id) if not ev.skipped]
        if len(dates) < 2:
            return None
        dates.sort()
        gaps = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
        return sum(gaps) / len(gaps)

    def load_many(self, events: list[ServiceEvent]) -> None:
        for ev in events:
            self.record(ev)

    def to_dict_list(self) -> list[dict[str, Any]]:
        return [e.to_dict() for e in self.all()]

    @classmethod
    def from_dict_list(cls, rows: list[dict[str, Any]]) -> "ServiceLog":
        log = cls()
        for row in rows:
            log.record(ServiceEvent.from_dict(row))
        return log

    def count(self) -> int:
        return len(self._events)

    def count_for_vehicle(self, vehicle_id: str) -> int:
        return len(self._by_vehicle.get(vehicle_id, []))

    def remove_for_vehicle(self, vehicle_id: str) -> int:
        ids = list(self._by_vehicle.pop(vehicle_id, []))
        for eid in ids:
            self._events.pop(eid, None)
        return len(ids)

    def streak_days(self, vehicle_id: str) -> int:
        """Days since last missed expected service — naive impl."""
        last = self.last_for_vehicle(vehicle_id)
        if last is None:
            return 0
        return (date.today() - last.serviced_date).days


@dataclass
class ServiceBatch:
    """Group service session — several vehicles at once."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    serviced_at: str = field(default_factory=lambda: date.today().isoformat())
    event_ids: list[str] = field(default_factory=list)
    notes: str = ""
    total_ml: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ServiceBatch":
        return cls(
            id=data.get("id", uuid.uuid4().hex[:10]),
            serviced_at=data.get("serviced_at", date.today().isoformat()),
            event_ids=list(data.get("event_ids") or []),
            notes=data.get("notes", ""),
            total_ml=float(data.get("total_ml", 0)),
        )


def log_batch_service(
    log: ServiceLog,
    vehicle_amounts: dict[str, float],
    when: date | None = None,
    method: str = "top_service",
    notes: str = "",
) -> ServiceBatch:
    """Service multiple vehicles in one session."""
    batch = ServiceBatch(serviced_at=(when or date.today()).isoformat(), notes=notes)
    total = 0.0
    for vehicle_id, amount_ml in vehicle_amounts.items():
        ev = log.log_service(vehicle_id, amount_ml=amount_ml, when=when, method=method)
        batch.event_ids.append(ev.id)
        total += amount_ml
    batch.total_ml = total
    return batch


def weekly_service_stats(log: ServiceLog, weeks: int = 4) -> dict[str, Any]:
    """Aggregate service volume over recent weeks."""
    end = date.today()
    start = end - timedelta(days=weeks * 7)
    events = log.between(start, end)
    active = [e for e in events if not e.skipped]
    by_week: dict[str, float] = {}
    for ev in active:
        if ev.amount_ml is None:
            continue
        wk = ev.serviced_date.isocalendar()[1]
        key = "%d-W%02d" % (ev.serviced_date.year, wk)
        by_week[key] = by_week.get(key, 0) + ev.amount_ml
    return {
        "weeks": weeks,
        "event_count": len(active),
        "skipped_count": len(events) - len(active),
        "total_ml": sum(e.amount_ml or 0 for e in active),
        "by_week_ml": by_week,
    }


def vehicles_serviced_on(log: ServiceLog, day: date) -> list[str]:
    ids: list[str] = []
    for ev in log.between(day, day):
        if not ev.skipped and ev.vehicle_id not in ids:
            ids.append(ev.vehicle_id)
    return ids


def export_service_csv_rows(log: ServiceLog) -> list[list[str]]:
    """Simple CSV rows for export — header included."""
    rows = [["id", "vehicle_id", "serviced_at", "amount_ml", "method", "skipped", "notes"]]
    for ev in log.all():
        rows.append([
            ev.id,
            ev.vehicle_id,
            ev.serviced_at,
            str(ev.amount_ml or ""),
            ev.method,
            "yes" if ev.skipped else "no",
            ev.notes.replace("\n", " "),
        ])
    return rows


def detect_service_drift(
    log: ServiceLog,
    vehicle_id: str,
    expected_interval: int,
) -> dict[str, Any]:
    """Compare actual average interval vs expected — handy for tuning."""
    avg = log.average_interval_days(vehicle_id)
    if avg is None:
        return {"vehicle_id": vehicle_id, "drift": None, "message": "not enough data"}
    drift = avg - expected_interval
    msg = "on track"
    if drift > 2:
        msg = "service less often than scheduled"
    elif drift < -2:
        msg = "service more often than scheduled"
    return {
        "vehicle_id": vehicle_id,
        "expected_days": expected_interval,
        "actual_avg_days": round(avg, 1),
        "drift_days": round(drift, 1),
        "message": msg,
    }


def service_history_summary(log: ServiceLog, vehicle_id: str) -> dict[str, Any]:
    events = log.for_vehicle(vehicle_id)
    if not events:
        return {"vehicle_id": vehicle_id, "count": 0}
    amounts = [e.amount_ml for e in events if e.amount_ml and not e.skipped]
    return {
        "vehicle_id": vehicle_id,
        "count": len(events),
        "skipped": sum(1 for e in events if e.skipped),
        "avg_amount_ml": (sum(amounts) / len(amounts)) if amounts else None,
        "last": events[0].serviced_at if events else None,
        "avg_interval_days": log.average_interval_days(vehicle_id),
    }


def compare_vehicles_service_use(log: ServiceLog, vehicle_ids: list[str], days: int = 30) -> list[dict[str, Any]]:
    rows = []
    for pid in vehicle_ids:
        total = log.total_ml_for_vehicle(pid, days=days)
        rows.append({"vehicle_id": pid, "total_ml": total, "days": days})
    return sorted(rows, key=lambda r: -r["total_ml"])


def missed_services_estimate(
    log: ServiceLog,
    vehicle_id: str,
    expected_interval: int,
    since: date | None = None,
) -> int:
    """Rough count of missed cycles based on gap since last service."""
    last = log.last_for_vehicle(vehicle_id)
    if last is None:
        return 0
    ref = since or date.today()
    gap = (ref - last.serviced_date).days
    if gap <= expected_interval:
        return 0
    return gap // expected_interval


def filter_events_by_method(log: ServiceLog, method: str) -> list[ServiceEvent]:
    m = validate_service_method(method)
    return [e for e in log.all() if e.method == m and not e.skipped]


class ServiceAnalytics:
    """Aggregate stats across the service log — for reports/stats modules."""

    def __init__(self, log: ServiceLog) -> None:
        self.log = log

    def total_events(self) -> int:
        return self.log.count()

    def total_volume_ml(self, days: int | None = None) -> float:
        if days is None:
            return sum(e.amount_ml or 0 for e in self.log.all() if not e.skipped)
        return sum(
            self.log.total_ml_for_vehicle(pid, days=days)
            for pid in self._vehicle_ids()
        )

    def _vehicle_ids(self) -> set[str]:
        return set(self.log._by_vehicle.keys())

    def busiest_day_of_week(self) -> str | None:
        names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        counts = [0] * 7
        for ev in self.log.all():
            if ev.skipped:
                continue
            counts[ev.serviced_date.weekday()] += 1
        if not any(counts):
            return None
        return names[counts.index(max(counts))]

    def avg_amount_by_vehicle(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for pid in self._vehicle_ids():
            amounts = [
                e.amount_ml for e in self.log.for_vehicle(pid)
                if e.amount_ml and not e.skipped
            ]
            if amounts:
                out[pid] = sum(amounts) / len(amounts)
        return out

    def skip_rate(self) -> float:
        events = self.log.all()
        if not events:
            return 0.0
        skipped = sum(1 for e in events if e.skipped)
        return skipped / len(events)

    def method_breakdown(self) -> dict[str, int]:
        tallies: dict[str, int] = {}
        for ev in self.log.all():
            if ev.skipped:
                continue
            tallies[ev.method] = tallies.get(ev.method, 0) + 1
        return tallies

    def report(self) -> dict[str, Any]:
        return {
            "total_events": self.total_events(),
            "total_volume_ml": self.total_volume_ml(),
            "busiest_day": self.busiest_day_of_week(),
            "skip_rate": round(self.skip_rate(), 3),
            "methods": self.method_breakdown(),
            "vehicles_tracked": len(self._vehicle_ids()),
        }


def merge_service_logs(a: ServiceLog, b: ServiceLog) -> ServiceLog:
    merged = ServiceLog()
    for ev in a.all():
        merged.record(ev)
    for ev in b.all():
        if ev.id not in merged._events:
            merged.record(ev)
    return merged



