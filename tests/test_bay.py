"""Tests for garagelog.bay."""

import pytest

from garagelog.errors import NotFoundError
from garagelog.bay import (
    WindowDirection,
    Bay,
    BayRegistry,
    BayClimateProfile,
    default_bays,
    compare_light,
    suggest_vehicles_for_bay,
    bay_report,
    reassign_vehicle,
    estimate_daily_light_hours,
    rank_bays_for_make,
    build_bay_map,
    vehicles_without_bay,
    bay_capacity_report,
    RoomSnapshot,
    RoomHistory,
    sync_bay_vehicle_ids,
    format_bay_tree,
)
from garagelog.make import MakeCatalog


class TestWindowDirection:
    def test_str(self):
        assert str(WindowDirection.SOUTH) == "south"


class TestBay:
    def test_create(self, sample_bay):
        assert sample_bay.name == "Living Room"

    def test_add_remove_vehicle(self, sample_bay):
        sample_bay.add_vehicle("vehicle001")
        assert "vehicle001" in sample_bay.vehicle_ids
        assert sample_bay.remove_vehicle("vehicle001") is True

    def test_effective_light_south(self):
        loc = Bay.create(
            "Bright Room",
            light_level="medium",
            window_direction=WindowDirection.SOUTH,
        )
        assert compare_light(loc.effective_light(), "medium") >= 0

    def test_label(self, sample_bay):
        assert "Living Room" in sample_bay.label()

    def test_to_dict_from_dict(self, sample_bay):
        restored = Bay.from_dict(sample_bay.to_dict())
        assert restored.name == sample_bay.name

    def test_summary(self, sample_bay):
        summary = sample_bay.summary()
        assert "Living Room" in summary


class TestBayRegistry:
    def test_add_and_get(self, bay_registry, sample_bay):
        assert bay_registry.get(sample_bay.id) is not None

    def test_duplicate_id_raises(self, sample_bay):
        reg = BayRegistry()
        reg.add(sample_bay)
        with pytest.raises(ValueError):
            reg.add(sample_bay)

    def test_get_by_name(self, bay_registry, sample_bay):
        assert bay_registry.get_by_name("Living Room") is not None

    def test_require_raises(self):
        reg = BayRegistry()
        with pytest.raises(NotFoundError):
            reg.require("missing")

    def test_remove(self, bay_registry, sample_bay):
        assert bay_registry.remove(sample_bay.id) is True

    def test_assign_unassign_vehicle(self, bay_registry, sample_bay):
        bay_registry.assign_vehicle(sample_bay.id, "vehicle001")
        assert "vehicle001" in bay_registry.get(sample_bay.id).vehicle_ids
        bay_registry.unassign_vehicle("vehicle001")
        assert "vehicle001" not in bay_registry.get(sample_bay.id).vehicle_ids

    def test_find_by_light(self, bay_registry):
        found = bay_registry.find_by_light("bright_indirect")
        assert len(found) >= 1

    def test_find_by_zone(self, bay_registry, sample_bay):
        found = bay_registry.find_by_zone("main")
        assert sample_bay in found

    def test_total_vehicles_assigned(self, bay_registry, sample_bay):
        sample_bay.add_vehicle("p1")
        bay_registry._bays[sample_bay.id] = sample_bay
        assert bay_registry.total_vehicles_assigned() >= 1

    def test_bays_needing_humidifier(self, bay_registry):
        low = bay_registry.bays_needing_humidifier(threshold=50)
        assert isinstance(low, list)

    def test_merge(self, bay_registry, sample_bay):
        other = BayRegistry()
        other.add(Bay.create("Kitchen", id="loc002"))
        merged = bay_registry.merge(other)
        assert merged.count() == 2


class TestClimateProfile:
    def test_from_bay(self, sample_bay):
        profile = BayClimateProfile.from_bay(sample_bay)
        assert profile.bay_id == sample_bay.id

    def test_service_factor_high_mileage(self):
        profile = BayClimateProfile(
            bay_id="loc1",
            avg_mileage=70.0,
        )
        assert profile.service_factor() > 1.0

    def test_service_factor_draft(self, sample_bay):
        sample_bay.notes = "drafty window"
        profile = BayClimateProfile.from_bay(sample_bay)
        assert profile.draft_risk is True


class TestBayHelpers:
    def test_default_bays(self):
        reg = default_bays()
        assert reg.count() >= 4

    def test_compare_light(self):
        assert compare_light("low", "full_sun") == -1
        assert compare_light("full_sun", "low") == 1
        assert compare_light("medium", "medium") == 0

    def test_suggest_vehicles_for_bay(self, sample_bay):
        keys = suggest_vehicles_for_bay(sample_bay)
        assert isinstance(keys, list)

    def test_bay_report(self, bay_registry):
        report = bay_report(bay_registry)
        assert "bay_count" in report

    def test_reassign_vehicle(self, bay_registry, sample_bay):
        kitchen = Bay.create("Kitchen", id="loc_k")
        bay_registry.add(kitchen)
        reassign_vehicle(bay_registry, "vehicle001", sample_bay.id, kitchen.id)
        assert "vehicle001" in kitchen.vehicle_ids

    def test_estimate_daily_light_hours(self, sample_bay):
        hours = estimate_daily_light_hours(sample_bay, month=7)
        assert hours > 0

    def test_rank_bays_for_make(self, bay_registry, sample_make):
        ranked = rank_bays_for_make(bay_registry, sample_make)
        assert len(ranked) >= 1

    def test_build_bay_map(self, bay_registry):
        mapping = build_bay_map(bay_registry)
        assert "living room" in mapping

    def test_vehicles_without_bay(self, bay_registry):
        missing = vehicles_without_bay(bay_registry, ["vehicle001", "vehicle999"])
        assert "vehicle999" in missing

    def test_bay_capacity_report(self, bay_registry, sample_bay):
        sample_bay.vehicle_ids = ["p1", "p2"]
        report = bay_capacity_report(bay_registry, max_per_room=1)
        assert len(report["crowded"]) >= 1

    def test_room_history(self):
        hist = RoomHistory()
        snap = RoomSnapshot(bay_id="loc1", recorded_at="2024-06-01", mileage_pct=50)
        hist.record(snap)
        assert len(hist.for_bay("loc1")) == 1
        assert hist.avg_mileage("loc1") == 50.0

    def test_sync_bay_vehicle_ids(self, bay_registry, sample_vehicle):
        sync_bay_vehicle_ids(bay_registry, [sample_vehicle])
        loc = bay_registry.get(sample_vehicle.bay_id)
        assert sample_vehicle.id in loc.vehicle_ids

    def test_format_bay_tree(self, bay_registry):
        text = format_bay_tree(bay_registry)
        assert "Living Room" in text
