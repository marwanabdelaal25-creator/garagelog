"""Tests for garagelog.vehicle."""

from datetime import date, timedelta

import pytest

from garagelog.errors import NotFoundError
from garagelog.vehicle import (
    HealthStatus,
    PotInfo,
    Vehicle,
    VehicleCatalog,
    vehicle_health_report,
    apply_make_defaults,
    sort_by_service_priority,
    clone_vehicle,
    bulk_update_interval,
    catalog_to_summary_lines,
    find_duplicates_by_name,
    parse_iso,
)
from garagelog.make import MakeProfile


class TestHealthStatus:
    def test_emoji(self):
        assert HealthStatus.THRIVING.emoji == "🌿"

    def test_score_hint(self):
        assert HealthStatus.CRITICAL.score_hint() == 15


class TestPotInfo:
    def test_to_dict_roundtrip(self):
        bag = PotInfo(diameter=6.0, unit="in", material="ceramic")
        restored = PotInfo.from_dict(bag.to_dict())
        assert restored.diameter == 6.0

    def test_label(self):
        bag = PotInfo(diameter=6.0, unit="in", material="ceramic")
        assert "6.0in" in bag.label()

    def test_label_no_drainage(self):
        bag = PotInfo(diameter=6.0, has_drainage=False)
        assert "no drainage" in bag.label()


class TestVehicle:
    def test_create(self, sample_vehicle):
        assert sample_vehicle.name == "Monstera"
        assert sample_vehicle.id == "vehicle001"

    def test_display_name_with_nickname(self, sample_vehicle):
        assert "Monty" in sample_vehicle.display_name

    def test_set_health(self, sample_vehicle):
        sample_vehicle.set_health(HealthStatus.THRIVING, 90)
        assert sample_vehicle.health == HealthStatus.THRIVING
        assert sample_vehicle.health_score == 90

    def test_record_service(self, sample_vehicle):
        when = date.today()
        sample_vehicle.record_service(when)
        assert sample_vehicle.last_serviced_at == when.isoformat()

    def test_days_since_serviced(self, sample_vehicle):
        assert sample_vehicle.days_since_serviced() == 3

    def test_is_overdue(self, sample_vehicle):
        sample_vehicle.last_serviced_at = (date.today() - timedelta(days=20)).isoformat()
        assert sample_vehicle.is_overdue() is True

    def test_overdue_by_days(self, sample_vehicle):
        sample_vehicle.last_serviced_at = (date.today() - timedelta(days=20)).isoformat()
        assert sample_vehicle.overdue_by_days() == 13

    def test_attach_detach_tag(self, sample_vehicle):
        sample_vehicle.attach_tag("tag001")
        assert "tag001" in sample_vehicle.tag_ids
        assert sample_vehicle.detach_tag("tag001") is True

    def test_detach_missing_tag(self, sample_vehicle):
        assert sample_vehicle.detach_tag("missing") is False

    def test_archive_unarchive(self, sample_vehicle):
        sample_vehicle.archive()
        assert sample_vehicle.archived is True
        sample_vehicle.unarchive()
        assert sample_vehicle.archived is False

    def test_to_dict_from_dict(self, sample_vehicle):
        restored = Vehicle.from_dict(sample_vehicle.to_dict())
        assert restored.name == sample_vehicle.name

    def test_summary_line(self, sample_vehicle):
        line = sample_vehicle.summary_line()
        assert "Monstera" in line or "Monty" in line


class TestVehicleCatalog:
    def test_add_and_get(self, vehicle_catalog, sample_vehicle):
        assert vehicle_catalog.get(sample_vehicle.id) is not None

    def test_duplicate_id_raises(self, sample_vehicle):
        cat = VehicleCatalog()
        cat.add(sample_vehicle)
        with pytest.raises(ValueError):
            cat.add(sample_vehicle)

    def test_require_raises(self):
        cat = VehicleCatalog()
        with pytest.raises(NotFoundError):
            cat.require("missing")

    def test_all_excludes_archived(self, vehicle_catalog, sample_vehicle):
        sample_vehicle.archive()
        assert sample_vehicle not in vehicle_catalog.all()

    def test_find_by_name(self, vehicle_catalog, sample_vehicle):
        assert sample_vehicle in vehicle_catalog.find_by_name("Monstera")

    def test_find_by_bay(self, vehicle_catalog, sample_vehicle, sample_bay):
        found = vehicle_catalog.find_by_bay(sample_bay.id)
        assert len(found) >= 1

    def test_find_by_make(self, vehicle_catalog, sample_vehicle):
        found = vehicle_catalog.find_by_make("baghos-golden")
        assert sample_vehicle in found

    def test_find_overdue(self, vehicle_catalog, sample_vehicle):
        sample_vehicle.last_serviced_at = (date.today() - timedelta(days=30)).isoformat()
        assert sample_vehicle in vehicle_catalog.find_overdue()

    def test_find_by_tag(self, vehicle_catalog, sample_vehicle):
        sample_vehicle.attach_tag("tag001")
        assert sample_vehicle in vehicle_catalog.find_by_tag("tag001")

    def test_remove(self, vehicle_catalog, sample_vehicle):
        assert vehicle_catalog.remove(sample_vehicle.id) is True
        assert vehicle_catalog.get(sample_vehicle.id) is None

    def test_count_by_health(self, vehicle_catalog):
        counts = vehicle_catalog.count_by_health()
        assert isinstance(counts, dict)

    def test_merge(self, vehicle_catalog, sample_vehicle2):
        other = VehicleCatalog()
        other.add(sample_vehicle2)
        merged = vehicle_catalog.merge(other)
        assert merged.count() == 2


class TestVehicleHelpers:
    def test_vehicle_health_report(self, vehicle_catalog):
        report = vehicle_health_report(vehicle_catalog)
        assert "total" in report
        assert "overdue_count" in report

    def test_apply_make_defaults(self, sample_vehicle, sample_make):
        sample_vehicle.service_interval_days = 7
        apply_make_defaults(sample_vehicle, sample_make)
        assert sample_vehicle.make_key == sample_make.key

    def test_sort_by_service_priority(self, sample_vehicle, sample_vehicle2):
        sample_vehicle.last_serviced_at = (date.today() - timedelta(days=30)).isoformat()
        sorted_vehicles = sort_by_service_priority([sample_vehicle2, sample_vehicle])
        assert sorted_vehicles[0].id == sample_vehicle.id

    def test_clone_vehicle(self, sample_vehicle):
        clone = clone_vehicle(sample_vehicle, "Monstera Jr")
        assert clone.id != sample_vehicle.id
        assert clone.name == "Monstera Jr"
        assert clone.metadata.get("propagated_from") == sample_vehicle.id

    def test_bulk_update_interval(self, vehicle_catalog, sample_vehicle):
        updated = bulk_update_interval(vehicle_catalog, [sample_vehicle.id], 10)
        assert updated == 1
        assert vehicle_catalog.get(sample_vehicle.id).service_interval_days == 10

    def test_catalog_to_summary_lines(self, vehicle_catalog):
        lines = catalog_to_summary_lines(vehicle_catalog)
        assert len(lines) >= 1

    def test_find_duplicates_by_name(self, sample_vehicle):
        cat = VehicleCatalog()
        cat.add(sample_vehicle)
        dup = Vehicle.create("Monstera", id="dup001")
        cat.add(dup)
        dupes = find_duplicates_by_name(cat)
        assert "monstera" in dupes

    def test_parse_iso(self):
        assert parse_iso("2024-06-01T12:00:00") is not None

    def test_parse_iso_none(self):
        assert parse_iso(None) is None

    def test_record_service_bumps_struggling_health(self):
        vehicle = Vehicle.create("Fern", health=HealthStatus.STRUGGLING, health_score=40)
        vehicle.record_service()
        assert vehicle.health_score >= 40
