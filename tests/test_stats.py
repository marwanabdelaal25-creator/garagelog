"""Tests for garagelog.stats."""

import json

from garagelog.stats import GarageStats


class TestGarageStats:
    def test_snapshot_empty(self, empty_storage):
        stats = GarageStats(empty_storage)
        snap = stats.snapshot()
        assert snap["vehicles_total"] == 0

    def test_snapshot_populated(self, populated_storage):
        stats = GarageStats(populated_storage)
        snap = stats.snapshot()
        assert snap["vehicles_total"] >= 2
        assert snap["vehicles_active"] >= 1

    def test_generated_at(self, populated_storage):
        stats = GarageStats(populated_storage)
        snap = stats.snapshot()
        assert "generated_at" in snap

    def test_make_bays_tags_counts(self, populated_storage):
        stats = GarageStats(populated_storage)
        snap = stats.snapshot()
        assert snap["make_count"] >= 1
        assert snap["bays_count"] >= 1

    def test_serviced_last_7_days(self, populated_storage):
        stats = GarageStats(populated_storage)
        snap = stats.snapshot()
        assert "serviced_last_7_days" in snap

    def test_serviced_last_30_days(self, populated_storage):
        stats = GarageStats(populated_storage)
        snap = stats.snapshot()
        assert snap["serviced_last_30_days"] >= 0

    def test_overdue_count(self, populated_storage):
        stats = GarageStats(populated_storage)
        snap = stats.snapshot()
        assert "overdue_count" in snap

    def test_due_today_count(self, populated_storage):
        stats = GarageStats(populated_storage)
        snap = stats.snapshot()
        assert "due_today_count" in snap

    def test_avg_service_interval(self, populated_storage):
        stats = GarageStats(populated_storage)
        snap = stats.snapshot()
        assert snap["avg_service_interval_days"] > 0

    def test_inspection_logs_and_notes_totals(self, populated_storage):
        stats = GarageStats(populated_storage)
        snap = stats.snapshot()
        assert snap["notes_total"] >= 1

    def test_render_text(self, populated_storage):
        stats = GarageStats(populated_storage)
        text = stats.render_text()
        assert "vehicles" in text.lower() or "Garage" in text

    def test_render_text_empty(self, empty_storage):
        stats = GarageStats(empty_storage)
        text = stats.render_text()
        assert isinstance(text, str)

    def test_archived_not_in_active_count(self, populated_storage, sample_vehicle):
        populated_storage.update_vehicle(sample_vehicle.id, {"archived": True})
        stats = GarageStats(populated_storage)
        snap = stats.snapshot()
        assert snap["vehicles_active"] < snap["vehicles_total"]

    def test_collections_total(self, empty_storage):
        stats = GarageStats(empty_storage)
        snap = stats.snapshot()
        assert snap.get("collections_total", 0) == 0

    def test_snapshot_json_serializable(self, populated_storage):
        stats = GarageStats(populated_storage)
        snap = stats.snapshot()
        json.dumps(snap)
