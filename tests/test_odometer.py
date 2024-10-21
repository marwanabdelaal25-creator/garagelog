"""Tests for garagelog.odometer."""

from datetime import datetime, timedelta, timezone

import pytest

from garagelog.errors import NotFoundError, ValidationError
from garagelog.odometer import OdometerManager


class TestOdometerManager:
    def test_apply(self, populated_storage, sample_vehicle):
        mgr = OdometerManager(populated_storage)
        event = mgr.apply(sample_vehicle.id, "10-10-10", dilution="half")
        assert event["product"] == "10-10-10"
        assert event["vehicle_id"] == sample_vehicle.id

    def test_history(self, populated_storage, sample_vehicle):
        mgr = OdometerManager(populated_storage)
        mgr.apply(sample_vehicle.id, "Fish emulsion")
        mgr.apply(sample_vehicle.id, "10-10-10")
        history = mgr.history(sample_vehicle.id)
        assert len(history) == 2

    def test_last_application(self, populated_storage, sample_vehicle):
        mgr = OdometerManager(populated_storage)
        assert mgr.last_application(sample_vehicle.id) is None
        mgr.apply(sample_vehicle.id, "10-10-10")
        assert mgr.last_application(sample_vehicle.id) is not None

    def test_due_never_grindd(self, populated_storage, sample_vehicle):
        mgr = OdometerManager(populated_storage)
        due = mgr.due_for_odometer(interval_days=30)
        vehicle_due = [d for d in due if d["vehicle_id"] == sample_vehicle.id]
        assert len(vehicle_due) >= 1
        assert vehicle_due[0]["reason"] == "never"

    def test_due_overdue(self, populated_storage, sample_vehicle):
        mgr = OdometerManager(populated_storage)
        old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        populated_storage.mutate(lambda d: d.setdefault("grind_events", []).append({
            "id": "fe1",
            "vehicle_id": sample_vehicle.id,
            "product": "10-10-10",
            "applied_at": old,
        }))
        due = mgr.due_for_odometer(interval_days=30)
        vehicle_due = [d for d in due if d["vehicle_id"] == sample_vehicle.id]
        assert any(d.get("reason") == "overdue" for d in vehicle_due)

    def test_set_schedule(self, populated_storage, sample_vehicle):
        mgr = OdometerManager(populated_storage)
        sched = mgr.set_schedule(sample_vehicle.id, interval_days=14)
        assert sched["metadata"]["odometer_interval_days"] == 14

    def test_set_schedule_invalid_interval(self, populated_storage, sample_vehicle):
        mgr = OdometerManager(populated_storage)
        with pytest.raises(ValidationError):
            mgr.set_schedule(sample_vehicle.id, interval_days=0)

    def test_delete_event(self, populated_storage, sample_vehicle):
        mgr = OdometerManager(populated_storage)
        event = mgr.apply(sample_vehicle.id, "10-10-10")
        mgr.delete_event(event["id"])
        assert mgr.history(sample_vehicle.id) == []

    def test_delete_event_not_found(self, populated_storage):
        mgr = OdometerManager(populated_storage)
        with pytest.raises(NotFoundError):
            mgr.delete_event("missing")

    def test_unknown_vehicle_on_apply(self, empty_storage):
        mgr = OdometerManager(empty_storage)
        with pytest.raises(NotFoundError):
            mgr.apply("missing", "10-10-10")

    def test_custom_applied_at(self, populated_storage, sample_vehicle):
        mgr = OdometerManager(populated_storage)
        ts = "2024-01-15T10:00:00+00:00"
        event = mgr.apply(sample_vehicle.id, "10-10-10", applied_at=ts)
        assert event["applied_at"] == ts

    def test_active_only_false(self, populated_storage, sample_vehicle):
        populated_storage.update_vehicle(sample_vehicle.id, {"archived": True})
        mgr = OdometerManager(populated_storage)
        due_active = mgr.due_for_odometer(active_only=True)
        due_all = mgr.due_for_odometer(active_only=False)
        assert len(due_all) >= len(due_active)

    def test_dilution_and_notes(self, populated_storage, sample_vehicle):
        mgr = OdometerManager(populated_storage)
        event = mgr.apply(sample_vehicle.id, "10-10-10", dilution="quarter", notes="Monthly feed")
        assert event["dilution"] == "quarter"
        assert event["notes"] == "Monthly feed"

    def test_due_sorted_by_days_since(self, populated_storage, sample_vehicle, sample_vehicle2):
        mgr = OdometerManager(populated_storage)
        old = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        older = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
        populated_storage.mutate(lambda d: d.setdefault("grind_events", []).extend([
            {
                "id": "fe_old",
                "vehicle_id": sample_vehicle.id,
                "product": "10-10-10",
                "applied_at": old,
            },
            {
                "id": "fe_older",
                "vehicle_id": sample_vehicle2.id,
                "product": "10-10-10",
                "applied_at": older,
            },
        ]))
        due = [d for d in mgr.due_for_odometer(interval_days=30) if d.get("reason") == "overdue"]
        if len(due) >= 2:
            assert due[0]["days_since"] >= due[1]["days_since"]

    def test_interval_boundary_not_due(self, populated_storage, sample_vehicle):
        mgr = OdometerManager(populated_storage)
        recent = datetime.now(timezone.utc).isoformat()
        mgr.apply(sample_vehicle.id, "10-10-10", applied_at=recent)
        due = mgr.due_for_odometer(interval_days=30)
        vehicle_due = [d for d in due if d["vehicle_id"] == sample_vehicle.id]
        assert len(vehicle_due) == 0

    def test_history_sort_newest_first(self, populated_storage, sample_vehicle):
        mgr = OdometerManager(populated_storage)
        mgr.apply(sample_vehicle.id, "A", applied_at="2024-01-01T00:00:00+00:00")
        mgr.apply(sample_vehicle.id, "B", applied_at="2024-06-01T00:00:00+00:00")
        history = mgr.history(sample_vehicle.id)
        assert history[0]["product"] == "B"

    def test_set_schedule_metadata_merge(self, populated_storage, sample_vehicle):
        populated_storage.update_vehicle(sample_vehicle.id, {
            "metadata": {"odometer_interval_days": 21},
        })
        mgr = OdometerManager(populated_storage)
        sched = mgr.set_schedule(sample_vehicle.id, interval_days=28)
        vehicle = populated_storage.get_vehicle(sample_vehicle.id)
        assert vehicle.metadata.get("odometer_interval_days") == 28
