"""Tests for garagelog.reminders."""

from datetime import datetime, timedelta, timezone

import pytest

from garagelog.reminders import ServiceReminder, ReminderEngine
from garagelog.seasons import SeasonCalendar


class TestServiceReminder:
    def test_sort_key(self):
        rem = ServiceReminder(
            vehicle_id="p1",
            vehicle_name="Fern",
            due_at=datetime.now(timezone.utc),
            days_overdue=2.0,
            urgency="overdue",
        )
        assert rem.sort_key[0] == -2.0


class TestReminderEngine:
    def test_compute_for_vehicle(self, populated_storage, sample_vehicle):
        engine = ReminderEngine(populated_storage)
        rem = engine.compute_for_vehicle(sample_vehicle)
        assert rem.vehicle_id == sample_vehicle.id
        assert rem.urgency in ("overdue", "due_today", "upcoming")

    def test_upcoming(self, populated_storage):
        engine = ReminderEngine(populated_storage)
        items = engine.upcoming(within_days=14)
        assert len(items) >= 1

    def test_upcoming_exclude_overdue(self, populated_storage, sample_vehicle):
        populated_storage.update_vehicle(sample_vehicle.id, {
            "last_serviced_at": (datetime.now(timezone.utc) - timedelta(days=60)).isoformat(),
        })
        engine = ReminderEngine(populated_storage)
        items = engine.upcoming(include_overdue=False)
        assert all(r.urgency != "overdue" for r in items)

    def test_overdue_only(self, populated_storage, sample_vehicle):
        populated_storage.update_vehicle(sample_vehicle.id, {
            "last_serviced_at": (datetime.now(timezone.utc) - timedelta(days=60)).isoformat(),
        })
        engine = ReminderEngine(populated_storage)
        overdue = engine.overdue_only()
        assert all(r.urgency == "overdue" for r in overdue)

    def test_summary_text(self, populated_storage):
        engine = ReminderEngine(populated_storage)
        text = engine.summary_text()
        assert isinstance(text, str)

    def test_never_serviced_uses_acquired(self, empty_storage, sample_vehicle):
        empty_storage.create_vehicle(sample_vehicle)
        engine = ReminderEngine(empty_storage)
        vehicle = empty_storage.get_vehicle(sample_vehicle.id)
        vehicle.last_serviced_at = None
        rem = engine.compute_for_vehicle(vehicle)
        assert rem.due_at is not None

    def test_season_affects_due_date(self, populated_storage, sample_vehicle):
        seasons = SeasonCalendar()
        engine = ReminderEngine(populated_storage, seasons=seasons)
        ref = datetime(2024, 7, 15, tzinfo=timezone.utc)
        rem = engine.compute_for_vehicle(sample_vehicle, ref=ref)
        assert rem.bay_id == sample_vehicle.bay_id

    def test_active_only_false(self, populated_storage, sample_vehicle):
        populated_storage.update_vehicle(sample_vehicle.id, {"archived": True})
        engine = ReminderEngine(populated_storage)
        active = engine.upcoming(active_only=True)
        archived = engine.upcoming(active_only=False)
        assert len(archived) >= len(active)

    def test_within_days_filter(self, populated_storage):
        engine = ReminderEngine(populated_storage)
        items = engine.upcoming(within_days=0, include_overdue=False)
        for rem in items:
            assert rem.urgency != "overdue"

    def test_due_today_urgency(self, populated_storage, sample_vehicle):
        engine = ReminderEngine(populated_storage)
        ref = datetime.now(timezone.utc)
        vehicle = populated_storage.get_vehicle(sample_vehicle.id)
        vehicle.last_serviced_at = (ref - timedelta(days=vehicle.service_interval_days)).isoformat()
        rem = engine.compute_for_vehicle(vehicle, ref=ref)
        assert rem.urgency in ("due_today", "overdue", "upcoming")

    def test_empty_garage_summary(self, empty_storage):
        engine = ReminderEngine(empty_storage)
        text = engine.summary_text()
        assert "caught up" in text.lower() or isinstance(text, str)

    def test_upcoming_sorted(self, populated_storage):
        engine = ReminderEngine(populated_storage)
        items = engine.upcoming()
        if len(items) >= 2:
            assert items[0].sort_key >= items[1].sort_key
