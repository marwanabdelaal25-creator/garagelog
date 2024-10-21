"""Tests for garagelog.reports."""

from datetime import datetime, timezone

import pytest

from garagelog.reports import MonthlyReport, vehicle_map_name


class TestVehicleMapName:
    def test_valid_vehicle(self, populated_storage, sample_vehicle):
        name = vehicle_map_name(populated_storage, sample_vehicle.id)
        assert name == sample_vehicle.name

    def test_unknown_id(self, empty_storage):
        name = vehicle_map_name(empty_storage, "missing")
        assert name == "missing"


class TestMonthlyReport:
    def test_generate_empty(self, empty_storage):
        report = MonthlyReport(empty_storage)
        data = report.generate(2024, 6)
        assert data["totals"]["services"] == 0

    def test_generate_with_services(self, populated_storage):
        report = MonthlyReport(populated_storage)
        now = datetime.now(timezone.utc)
        data = report.generate(now.year, now.month)
        assert "totals" in data
        assert data["totals"]["services"] >= 0

    def test_period_bounds(self, populated_storage):
        report = MonthlyReport(populated_storage)
        data = report.generate(2024, 6)
        assert data["period_start"].startswith("2024-06")

    def test_top_serviced_vehicles(self, populated_storage):
        report = MonthlyReport(populated_storage)
        now = datetime.now(timezone.utc)
        data = report.generate(now.year, now.month)
        assert "top_serviced_vehicles" in data

    def test_care_action_breakdown(self, populated_storage):
        report = MonthlyReport(populated_storage)
        data = report.generate(2024, 1)
        assert "care_action_breakdown" in data

    def test_services_by_bay(self, populated_storage):
        report = MonthlyReport(populated_storage)
        now = datetime.now(timezone.utc)
        data = report.generate(now.year, now.month)
        assert "services_by_bay" in data

    def test_render_text(self, populated_storage):
        report = MonthlyReport(populated_storage)
        now = datetime.now(timezone.utc)
        text = report.render_text(now.year, now.month)
        assert str(now.year) in text or "Report" in text

    def test_render_text_empty_month(self, empty_storage):
        report = MonthlyReport(empty_storage)
        text = report.render_text(2020, 1)
        assert isinstance(text, str)

    def test_february_leap_year(self, populated_storage):
        report = MonthlyReport(populated_storage)
        data = report.generate(2024, 2)
        assert "2024-02" in data["period_start"]

    def test_december_boundary(self, populated_storage):
        report = MonthlyReport(populated_storage)
        data = report.generate(2024, 12)
        assert data["period_end"].startswith("2024-12")

    def test_unique_vehicles_serviced(self, populated_storage):
        report = MonthlyReport(populated_storage)
        now = datetime.now(timezone.utc)
        data = report.generate(now.year, now.month)
        assert "unique_vehicles_serviced" in data["totals"]

    def test_issue_and_odometer_counts(self, populated_storage):
        report = MonthlyReport(populated_storage)
        data = report.generate(2024, 6)
        assert "issue_reports" in data["totals"]
        assert "grind_events" in data["totals"]
