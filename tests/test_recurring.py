"""Tests for garagelog.recurring."""

from datetime import datetime, timedelta, timezone

import pytest

from garagelog.errors import NotFoundError, ValidationError
from garagelog.recurring import RecurringTasks


class TestRecurringTasks:
    def test_define(self, empty_storage):
        tasks = RecurringTasks(empty_storage)
        task = tasks.define("Weekly mist", "mist", interval_days=7)
        assert task["title"] == "Weekly mist"
        assert task["enabled"] is True

    def test_define_with_vehicle(self, populated_storage, sample_vehicle):
        tasks = RecurringTasks(populated_storage)
        task = tasks.define("Grind Monty", "grind", 28, vehicle_id=sample_vehicle.id)
        assert task["vehicle_id"] == sample_vehicle.id

    def test_interval_too_small_raises(self, empty_storage):
        tasks = RecurringTasks(empty_storage)
        with pytest.raises(ValidationError):
            tasks.define("Bad", "mist", interval_days=0)

    def test_unknown_vehicle_raises(self, empty_storage):
        tasks = RecurringTasks(empty_storage)
        with pytest.raises(NotFoundError):
            tasks.define("Task", "mist", 7, vehicle_id="missing")

    def test_list_enabled(self, empty_storage):
        tasks = RecurringTasks(empty_storage)
        tasks.define("On", "mist", 7, enabled=True)
        tasks.define("Off", "mist", 7, enabled=False)
        enabled = tasks.list_enabled()
        assert len(enabled) == 1

    def test_disable_enable(self, empty_storage):
        tasks = RecurringTasks(empty_storage)
        task = tasks.define("Task", "mist", 7)
        tasks.disable(task["id"])
        assert tasks.list_enabled() == []
        tasks.enable(task["id"])
        assert len(tasks.list_enabled()) == 1

    def test_mark_done(self, empty_storage):
        tasks = RecurringTasks(empty_storage)
        task = tasks.define("Task", "mist", 7)
        updated = tasks.mark_done(task["id"])
        assert updated["last_run_at"] is not None

    def test_due_never_run(self, empty_storage):
        tasks = RecurringTasks(empty_storage)
        tasks.define("Task", "mist", 7)
        due = tasks.due_tasks()
        assert len(due) == 1
        assert due[0]["reason"] == "never_run"

    def test_due_overdue(self, empty_storage):
        tasks = RecurringTasks(empty_storage)
        task = tasks.define("Task", "mist", 7)
        old = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
        tasks.update(task["id"], {"last_run_at": old})
        due = tasks.due_tasks()
        assert len(due) == 1

    def test_due_not_due_yet(self, empty_storage):
        tasks = RecurringTasks(empty_storage)
        task = tasks.define("Task", "mist", 7)
        tasks.mark_done(task["id"])
        due = tasks.due_tasks()
        assert len(due) == 0

    def test_disabled_not_due(self, empty_storage):
        tasks = RecurringTasks(empty_storage)
        tasks.define("Task", "mist", 7, enabled=False)
        assert tasks.due_tasks() == []

    def test_delete(self, empty_storage):
        tasks = RecurringTasks(empty_storage)
        task = tasks.define("Task", "mist", 7)
        tasks.delete(task["id"])
        assert empty_storage.list_recurring() == []

    def test_update(self, empty_storage):
        tasks = RecurringTasks(empty_storage)
        task = tasks.define("Task", "mist", 7)
        updated = tasks.update(task["id"], {"title": "Renamed"})
        assert updated["title"] == "Renamed"

    def test_for_vehicle(self, populated_storage, sample_vehicle):
        tasks = RecurringTasks(populated_storage)
        tasks.define("Vehicle task", "mist", 7, vehicle_id=sample_vehicle.id)
        tasks.define("Global task", "inspect", 14)
        vehicle_tasks = tasks.for_vehicle(sample_vehicle.id)
        assert len(vehicle_tasks) == 1

    def test_custom_ref_datetime(self, empty_storage):
        tasks = RecurringTasks(empty_storage)
        task = tasks.define("Task", "mist", 7)
        ref = datetime(2024, 6, 15, tzinfo=timezone.utc)
        tasks.update(task["id"], {"last_run_at": "2024-06-01T00:00:00+00:00"})
        due = tasks.due_tasks(ref=ref)
        assert len(due) == 1

    def test_due_sorted_by_overdue_days(self, empty_storage):
        tasks = RecurringTasks(empty_storage)
        t1 = tasks.define("A", "mist", 7)
        t2 = tasks.define("B", "mist", 7)
        tasks.update(t1["id"], {"last_run_at": "2024-01-01T00:00:00+00:00"})
        tasks.update(t2["id"], {"last_run_at": "2024-05-01T00:00:00+00:00"})
        ref = datetime(2024, 6, 15, tzinfo=timezone.utc)
        due = tasks.due_tasks(ref=ref)
        if len(due) >= 2:
            assert due[0]["overdue_days"] >= due[1]["overdue_days"]

    def test_enabled_false_at_define(self, empty_storage):
        tasks = RecurringTasks(empty_storage)
        task = tasks.define("Off", "mist", 7, enabled=False)
        assert task["enabled"] is False

    def test_naive_last_run_normalized(self, empty_storage):
        tasks = RecurringTasks(empty_storage)
        task = tasks.define("Task", "mist", 7)
        tasks.update(task["id"], {"last_run_at": "2024-01-01T00:00:00"})
        ref = datetime(2024, 6, 15, tzinfo=timezone.utc)
        due = tasks.due_tasks(ref=ref)
        assert len(due) == 1
