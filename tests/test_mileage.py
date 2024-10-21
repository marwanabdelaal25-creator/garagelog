"""Tests for garagelog.mileage."""

import pytest

from garagelog.errors import NotFoundError, ValidationError
from garagelog.mileage import MileageLogger


class TestMileageLogger:
    def test_log_reading(self, populated_storage, sample_bay):
        logger = MileageLogger(populated_storage)
        row = logger.log(sample_bay.id, 55.0, notes="Morning reading")
        assert row["percent"] == 55.0
        assert row["bay_id"] == sample_bay.id

    def test_percent_out_of_range_low(self, populated_storage, sample_bay):
        logger = MileageLogger(populated_storage)
        with pytest.raises(ValidationError):
            logger.log(sample_bay.id, -1)

    def test_percent_out_of_range_high(self, populated_storage, sample_bay):
        logger = MileageLogger(populated_storage)
        with pytest.raises(ValidationError):
            logger.log(sample_bay.id, 101)

    def test_unknown_bay(self, empty_storage):
        logger = MileageLogger(empty_storage)
        with pytest.raises(NotFoundError):
            logger.log("missing", 50.0)

    def test_list_for_bay(self, populated_storage, sample_bay):
        logger = MileageLogger(populated_storage)
        logger.log(sample_bay.id, 45.0)
        logger.log(sample_bay.id, 50.0)
        rows = logger.list_for_bay(sample_bay.id)
        assert len(rows) == 2
        assert rows[0]["recorded_at"] >= rows[1]["recorded_at"]

    def test_list_with_limit(self, populated_storage, sample_bay):
        logger = MileageLogger(populated_storage)
        for pct in (40, 45, 50):
            logger.log(sample_bay.id, pct)
        rows = logger.list_for_bay(sample_bay.id, limit=2)
        assert len(rows) == 2

    def test_latest(self, populated_storage, sample_bay):
        logger = MileageLogger(populated_storage)
        assert logger.latest(sample_bay.id) is None
        logger.log(sample_bay.id, 48.0)
        latest = logger.latest(sample_bay.id)
        assert latest["percent"] == 48.0

    def test_average(self, populated_storage, sample_bay):
        logger = MileageLogger(populated_storage)
        logger.log(sample_bay.id, 40.0)
        logger.log(sample_bay.id, 60.0)
        assert logger.average(sample_bay.id) == 50.0

    def test_average_no_data(self, populated_storage, sample_bay):
        logger = MileageLogger(populated_storage)
        assert logger.average(sample_bay.id) is None

    def test_summary_by_bay(self, populated_storage, sample_bay):
        logger = MileageLogger(populated_storage)
        logger.log(sample_bay.id, 45.0)
        summary = logger.summary_by_bay()
        assert sample_bay.id in summary
        assert summary[sample_bay.id]["bay_name"] == sample_bay.name

    def test_delete(self, populated_storage, sample_bay):
        logger = MileageLogger(populated_storage)
        row = logger.log(sample_bay.id, 55.0)
        logger.delete(row["id"])
        assert logger.latest(sample_bay.id) is None

    def test_delete_missing_raises(self, populated_storage):
        logger = MileageLogger(populated_storage)
        with pytest.raises(NotFoundError):
            logger.delete("missing")

    def test_source_stored(self, populated_storage, sample_bay):
        logger = MileageLogger(populated_storage)
        row = logger.log(sample_bay.id, 50.0, source="sensor")
        assert row["source"] == "sensor"

    def test_persist_survives_reload(self, populated_storage, sample_bay, tmp_garage_path):
        logger = MileageLogger(populated_storage)
        logger.log(sample_bay.id, 42.0)
        reloaded = MileageLogger(populated_storage.__class__(tmp_garage_path))
        assert reloaded.latest(sample_bay.id) is not None

    def test_bucket_constant(self):
        assert MileageLogger.BUCKET == "mileage_readings"

    def test_rounded_percent(self, populated_storage, sample_bay):
        logger = MileageLogger(populated_storage)
        row = logger.log(sample_bay.id, 55.55)
        assert row["percent"] == 55.5

    def test_multiple_bays_isolated(self, populated_storage, sample_bay):
        loc2 = populated_storage.create_bay({"id": "loc2", "name": "Kitchen"})
        logger = MileageLogger(populated_storage)
        logger.log(sample_bay.id, 45.0)
        logger.log(loc2.id, 60.0)
        assert len(logger.list_for_bay(sample_bay.id)) == 1

    def test_summary_null_latest_for_empty(self, populated_storage, sample_bay):
        logger = MileageLogger(populated_storage)
        summary = logger.summary_by_bay()
        assert summary[sample_bay.id]["latest_percent"] is None
