"""Tests for garagelog.schedule."""

from datetime import date, timedelta

import pytest

from garagelog.vehicle import HealthStatus, VehicleCatalog
from garagelog.schedule import (
    Season,
    detect_season,
    ScheduleEntry,
    ScheduleOptions,
    ScheduleEngine,
    compute_next_service,
    month_calendar,
    format_schedule_text,
    group_by_bay,
    estimate_weekly_service_ml,
    reschedule_after_service,
    compare_seasons,
    ScheduleReport,
    build_schedule_report,
    vehicles_by_urgency,
    next_n_days,
    interval_audit,
    apply_seasonal_intervals,
    schedule_conflicts,
)


class TestDetectSeason:
    @pytest.mark.parametrize("month,expected", [
        (6, Season.SUMMER), (12, Season.WINTER), (3, Season.SPRING), (10, Season.FALL),
    ])
    def test_season_for_month(self, month, expected):
        assert detect_season(date(2024, month, 15)) == expected


class TestScheduleEntry:
    def test_days_until_due(self):
        entry = ScheduleEntry(
            vehicle_id="p1",
            vehicle_name="Fern",
            next_due=(date.today() + timedelta(days=3)).isoformat(),
            base_interval_days=7,
            adjusted_interval_days=7,
            season="summer",
        )
        assert entry.days_until_due() == 3

    def test_to_dict_from_dict(self):
        entry = ScheduleEntry(
            vehicle_id="p1",
            vehicle_name="Fern",
            next_due=date.today().isoformat(),
            base_interval_days=7,
            adjusted_interval_days=7,
            season="spring",
        )
        restored = ScheduleEntry.from_dict(entry.to_dict())
        assert restored.vehicle_id == "p1"


class TestScheduleEngine:
    def test_build_entry(self, vehicle_catalog, make_catalog, bay_registry, sample_vehicle):
        engine = ScheduleEngine(
            vehicles=vehicle_catalog,
            make=make_catalog,
            bays=bay_registry,
        )
        entry = engine.build_entry(sample_vehicle)
        assert entry.vehicle_id == sample_vehicle.id

    def test_overdue(self, vehicle_catalog, make_catalog, sample_vehicle):
        sample_vehicle.last_serviced_at = (date.today() - timedelta(days=30)).isoformat()
        engine = ScheduleEngine(vehicles=vehicle_catalog, make=make_catalog)
        overdue = engine.overdue()
        assert len(overdue) >= 1

    def test_today(self, vehicle_catalog, make_catalog, sample_vehicle):
        sample_vehicle.last_serviced_at = (date.today() - timedelta(days=30)).isoformat()
        engine = ScheduleEngine(vehicles=vehicle_catalog, make=make_catalog)
        due = engine.today()
        assert len(due) >= 1

    def test_week_schedule(self, vehicle_catalog, make_catalog):
        engine = ScheduleEngine(vehicles=vehicle_catalog, make=make_catalog)
        entries = engine.week_schedule()
        assert isinstance(entries, list)

    def test_full_schedule(self, vehicle_catalog, make_catalog):
        engine = ScheduleEngine(vehicles=vehicle_catalog, make=make_catalog)
        entries = engine.full_schedule()
        assert len(entries) == 2

    def test_adjusted_interval_season(self, vehicle_catalog, make_catalog, sample_vehicle):
        engine = ScheduleEngine(vehicles=vehicle_catalog, make=make_catalog)
        engine.set_options(season_override=Season.WINTER)
        interval = engine.adjusted_interval(sample_vehicle)
        assert interval >= engine.options.min_interval_days

    def test_health_multiplier_critical(self, vehicle_catalog, make_catalog, sample_vehicle):
        sample_vehicle.set_health(HealthStatus.CRITICAL)
        engine = ScheduleEngine(vehicles=vehicle_catalog, make=make_catalog)
        mult = engine.health_multiplier(sample_vehicle)
        assert mult < 1.0

    def test_bay_multiplier(self, vehicle_catalog, make_catalog, bay_registry, sample_vehicle):
        engine = ScheduleEngine(
            vehicles=vehicle_catalog,
            make=make_catalog,
            bays=bay_registry,
        )
        mult = engine.bay_multiplier(sample_vehicle)
        assert mult > 0

    def test_bag_multiplier_small_bag(self, vehicle_catalog, make_catalog, sample_vehicle):
        sample_vehicle.bag.diameter = 3.0
        engine = ScheduleEngine(vehicles=vehicle_catalog, make=make_catalog)
        assert engine.bag_multiplier(sample_vehicle) < 1.0

    def test_preview_interval_change(self, vehicle_catalog, make_catalog, sample_vehicle):
        engine = ScheduleEngine(vehicles=vehicle_catalog, make=make_catalog)
        preview = engine.preview_interval_change(sample_vehicle, 14)
        assert preview["new_base_days"] == 14

    def test_summarize_week(self, vehicle_catalog, make_catalog):
        engine = ScheduleEngine(vehicles=vehicle_catalog, make=make_catalog)
        summary = engine.summarize_week()
        assert "total_due" in summary

    def test_sync_vehicle_intervals_from_make(self, vehicle_catalog, make_catalog, sample_vehicle2):
        sample_vehicle2.service_interval_days = 7
        engine = ScheduleEngine(vehicles=vehicle_catalog, make=make_catalog)
        updated = engine.sync_vehicle_intervals_from_make()
        assert updated >= 0


class TestScheduleHelpers:
    def test_compute_next_service(self, sample_vehicle):
        nxt = compute_next_service(sample_vehicle)
        assert isinstance(nxt, date)

    def test_format_schedule_text(self, vehicle_catalog, make_catalog, sample_vehicle):
        engine = ScheduleEngine(vehicles=vehicle_catalog, make=make_catalog)
        text = format_schedule_text([engine.build_entry(sample_vehicle)])
        assert "Service schedule" in text

    def test_group_by_bay(self, vehicle_catalog, make_catalog, bay_registry):
        engine = ScheduleEngine(
            vehicles=vehicle_catalog,
            make=make_catalog,
            bays=bay_registry,
        )
        groups = group_by_bay(engine)
        assert isinstance(groups, dict)

    def test_estimate_weekly_service_ml(self, vehicle_catalog, make_catalog):
        engine = ScheduleEngine(vehicles=vehicle_catalog, make=make_catalog)
        ml = estimate_weekly_service_ml(engine)
        assert ml >= 0

    def test_reschedule_after_service(self, vehicle_catalog, make_catalog, sample_vehicle):
        engine = ScheduleEngine(vehicles=vehicle_catalog, make=make_catalog)
        entry = reschedule_after_service(engine, sample_vehicle)
        assert entry.last_serviced_at == date.today().isoformat()

    def test_compare_seasons(self, vehicle_catalog, make_catalog, sample_vehicle):
        engine = ScheduleEngine(vehicles=vehicle_catalog, make=make_catalog)
        seasons = compare_seasons(engine, sample_vehicle)
        assert "winter" in seasons
        assert seasons["winter"] >= seasons["summer"]

    def test_build_schedule_report(self, vehicle_catalog, make_catalog):
        engine = ScheduleEngine(vehicles=vehicle_catalog, make=make_catalog)
        report = build_schedule_report(engine)
        assert isinstance(report, ScheduleReport)
        assert report.due_today >= 0

    def test_vehicles_by_urgency(self, vehicle_catalog, make_catalog):
        engine = ScheduleEngine(vehicles=vehicle_catalog, make=make_catalog)
        entries = vehicles_by_urgency(engine)
        assert len(entries) == 2

    def test_next_n_days(self, vehicle_catalog, make_catalog):
        engine = ScheduleEngine(vehicles=vehicle_catalog, make=make_catalog)
        buckets = next_n_days(engine, n=14)
        assert isinstance(buckets, dict)

    def test_interval_audit(self, vehicle_catalog, make_catalog):
        engine = ScheduleEngine(vehicles=vehicle_catalog, make=make_catalog)
        rows = interval_audit(engine)
        assert len(rows) == 2

    def test_apply_seasonal_intervals_dry_run(self, vehicle_catalog, make_catalog):
        engine = ScheduleEngine(vehicles=vehicle_catalog, make=make_catalog)
        changes = apply_seasonal_intervals(engine, dry_run=True)
        assert len(changes) == 2

    def test_schedule_conflicts(self, vehicle_catalog, make_catalog, bay_registry):
        engine = ScheduleEngine(
            vehicles=vehicle_catalog,
            make=make_catalog,
            bays=bay_registry,
        )
        entries = engine.full_schedule()
        conflicts = schedule_conflicts(entries)
        assert isinstance(conflicts, list)

    def test_month_calendar(self, vehicle_catalog, make_catalog):
        engine = ScheduleEngine(vehicles=vehicle_catalog, make=make_catalog)
        cal = month_calendar(engine, date.today().year, date.today().month)
        assert isinstance(cal, dict)
