"""Tests for garagelog.service."""

from datetime import date, timedelta

import pytest

from garagelog.service import (
    ServiceQuality,
    ServiceEvent,
    ServiceLog,
    ServiceBatch,
    log_batch_service,
    weekly_service_stats,
    vehicles_serviced_on,
    export_service_csv_rows,
    detect_service_drift,
    service_history_summary,
    compare_vehicles_service_use,
    missed_services_estimate,
    filter_events_by_method,
    ServiceAnalytics,
    merge_service_logs,
)


class TestServiceEvent:
    def test_create(self, sample_vehicle):
        ev = ServiceEvent.create(sample_vehicle.id, amount_ml=250.0)
        assert ev.vehicle_id == sample_vehicle.id

    def test_skip(self, sample_vehicle):
        ev = ServiceEvent.skip(sample_vehicle.id, reason="travel")
        assert ev.skipped is True

    def test_serviced_date(self, sample_vehicle):
        ev = ServiceEvent.create(
            sample_vehicle.id,
            serviced_at="2024-06-01",
        )
        assert ev.serviced_date == date(2024, 6, 1)

    def test_to_dict_from_dict(self, sample_vehicle):
        ev = ServiceEvent.create(sample_vehicle.id, amount_ml=200.0)
        restored = ServiceEvent.from_dict(ev.to_dict())
        assert restored.amount_ml == 200.0

    def test_summary(self, sample_vehicle):
        ev = ServiceEvent.create(sample_vehicle.id, amount_ml=250.0)
        assert "250ml" in ev.summary()

    def test_skip_summary(self, sample_vehicle):
        ev = ServiceEvent.skip(sample_vehicle.id, reason="vacation")
        assert "skipped" in ev.summary()


class TestServiceLog:
    def test_record_and_get(self, service_log, sample_service_events):
        assert service_log.count() == 3

    def test_duplicate_raises(self, service_log, sample_service_events):
        with pytest.raises(ValueError):
            service_log.record(sample_service_events[0])

    def test_log_service(self, sample_vehicle):
        log = ServiceLog()
        ev = log.log_service(sample_vehicle.id, amount_ml=300.0)
        assert ev.amount_ml == 300.0

    def test_for_vehicle(self, service_log, sample_vehicle):
        events = service_log.for_vehicle(sample_vehicle.id)
        assert len(events) == 2

    def test_last_for_vehicle(self, service_log, sample_vehicle):
        last = service_log.last_for_vehicle(sample_vehicle.id)
        assert last is not None
        assert not last.skipped

    def test_between(self, service_log):
        start = date.today() - timedelta(days=30)
        end = date.today()
        events = service_log.between(start, end)
        assert len(events) >= 1

    def test_total_ml_for_vehicle(self, service_log, sample_vehicle):
        total = service_log.total_ml_for_vehicle(sample_vehicle.id, days=30)
        assert total == 450.0

    def test_average_interval_days(self, service_log, sample_vehicle):
        avg = service_log.average_interval_days(sample_vehicle.id)
        assert avg == 7.0

    def test_count_for_vehicle(self, service_log, sample_vehicle):
        assert service_log.count_for_vehicle(sample_vehicle.id) == 2

    def test_remove_for_vehicle(self, service_log, sample_vehicle):
        removed = service_log.remove_for_vehicle(sample_vehicle.id)
        assert removed == 2

    def test_streak_days(self, service_log, sample_vehicle):
        assert service_log.streak_days(sample_vehicle.id) == 3

    def test_from_dict_list(self, sample_service_events):
        log = ServiceLog.from_dict_list([e.to_dict() for e in sample_service_events])
        assert log.count() == 3


class TestBatchService:
    def test_log_batch_service(self, sample_vehicle, sample_vehicle2):
        log = ServiceLog()
        batch = log_batch_service(
            log,
            {sample_vehicle.id: 250.0, sample_vehicle2.id: 150.0},
        )
        assert batch.total_ml == 400.0
        assert len(batch.event_ids) == 2


class TestServiceHelpers:
    def test_weekly_service_stats(self, service_log):
        stats = weekly_service_stats(service_log, weeks=4)
        assert "total_ml" in stats

    def test_vehicles_serviced_on(self, service_log):
        today = date.today()
        ids = vehicles_serviced_on(service_log, today - timedelta(days=3))
        assert isinstance(ids, list)

    def test_export_service_csv_rows(self, service_log):
        rows = export_service_csv_rows(service_log)
        assert rows[0][0] == "id"
        assert len(rows) > 1

    def test_detect_service_drift(self, service_log, sample_vehicle):
        result = detect_service_drift(service_log, sample_vehicle.id, 7)
        assert result["vehicle_id"] == sample_vehicle.id

    def test_detect_drift_not_enough_data(self, sample_vehicle):
        log = ServiceLog()
        log.log_service(sample_vehicle.id, amount_ml=100.0)
        result = detect_service_drift(log, sample_vehicle.id, 7)
        assert result["drift"] is None

    def test_service_history_summary(self, service_log, sample_vehicle):
        summary = service_history_summary(service_log, sample_vehicle.id)
        assert summary["count"] == 2

    def test_compare_vehicles_service_use(self, service_log, sample_vehicle, sample_vehicle2):
        rows = compare_vehicles_service_use(
            service_log, [sample_vehicle.id, sample_vehicle2.id]
        )
        assert len(rows) == 2

    def test_missed_services_estimate(self, service_log, sample_vehicle):
        count = missed_services_estimate(service_log, sample_vehicle.id, 7)
        assert count >= 0

    def test_filter_events_by_method(self, service_log):
        events = filter_events_by_method(service_log, "top_service")
        assert all(e.method == "top_service" for e in events)

    def test_merge_service_logs(self, service_log, sample_vehicle):
        other = ServiceLog()
        other.log_service(sample_vehicle.id, amount_ml=100.0)
        merged = merge_service_logs(service_log, other)
        assert merged.count() > service_log.count()


class TestServiceAnalytics:
    def test_report(self, service_log):
        analytics = ServiceAnalytics(service_log)
        report = analytics.report()
        assert report["total_events"] == 3
        assert "busiest_day" in report

    def test_total_volume_ml(self, service_log):
        analytics = ServiceAnalytics(service_log)
        assert analytics.total_volume_ml() > 0

    def test_skip_rate(self, service_log):
        analytics = ServiceAnalytics(service_log)
        assert analytics.skip_rate() == 0.0

    def test_method_breakdown(self, service_log):
        analytics = ServiceAnalytics(service_log)
        breakdown = analytics.method_breakdown()
        assert "top_service" in breakdown

    def test_avg_amount_by_vehicle(self, service_log, sample_vehicle):
        analytics = ServiceAnalytics(service_log)
        avgs = analytics.avg_amount_by_vehicle()
        assert sample_vehicle.id in avgs
