"""Tests for garagelog.weather."""

import pytest

from garagelog.errors import NotFoundError, ValidationError
from garagelog.weather import WeatherLogger, VALID_LEVELS


class TestWeatherLogger:
    def test_log_with_vehicle(self, populated_storage, sample_vehicle):
        logger = WeatherLogger(populated_storage)
        row = logger.log(vehicle_id=sample_vehicle.id, level="bright", hours=6.0)
        assert row["vehicle_id"] == sample_vehicle.id

    def test_log_with_bay(self, populated_storage, sample_bay):
        logger = WeatherLogger(populated_storage)
        row = logger.log(bay_id=sample_bay.id, level="medium")
        assert row["bay_id"] == sample_bay.id

    def test_neither_id_raises(self, populated_storage):
        logger = WeatherLogger(populated_storage)
        with pytest.raises(ValidationError):
            logger.log(level="medium")

    def test_invalid_level_raises(self, populated_storage, sample_vehicle):
        logger = WeatherLogger(populated_storage)
        with pytest.raises(ValidationError):
            logger.log(vehicle_id=sample_vehicle.id, level="supernova")

    def test_level_normalized(self, populated_storage, sample_vehicle):
        logger = WeatherLogger(populated_storage)
        row = logger.log(vehicle_id=sample_vehicle.id, level="MEDIUM")
        assert row["level"] == "medium"

    def test_unknown_vehicle_raises(self, empty_storage):
        logger = WeatherLogger(empty_storage)
        with pytest.raises(NotFoundError):
            logger.log(vehicle_id="missing", level="low")

    def test_for_vehicle(self, populated_storage, sample_vehicle):
        logger = WeatherLogger(populated_storage)
        logger.log(vehicle_id=sample_vehicle.id, level="low")
        logger.log(vehicle_id=sample_vehicle.id, level="medium")
        rows = logger.for_vehicle(sample_vehicle.id)
        assert len(rows) == 2

    def test_for_bay(self, populated_storage, sample_bay):
        logger = WeatherLogger(populated_storage)
        logger.log(bay_id=sample_bay.id, level="bright")
        rows = logger.for_bay(sample_bay.id)
        assert len(rows) == 1

    def test_latest_for_vehicle(self, populated_storage, sample_vehicle):
        logger = WeatherLogger(populated_storage)
        assert logger.latest_for_vehicle(sample_vehicle.id) is None
        logger.log(vehicle_id=sample_vehicle.id, level="low")
        assert logger.latest_for_vehicle(sample_vehicle.id) is not None

    def test_delete(self, populated_storage, sample_vehicle):
        logger = WeatherLogger(populated_storage)
        row = logger.log(vehicle_id=sample_vehicle.id, level="low")
        logger.delete(row["id"])
        assert logger.latest_for_vehicle(sample_vehicle.id) is None

    def test_delete_missing_raises(self, populated_storage):
        logger = WeatherLogger(populated_storage)
        with pytest.raises(NotFoundError):
            logger.delete("missing")

    @pytest.mark.parametrize("level", list(VALID_LEVELS))
    def test_all_valid_levels(self, populated_storage, sample_vehicle, level):
        logger = WeatherLogger(populated_storage)
        row = logger.log(vehicle_id=sample_vehicle.id, level=level)
        assert row["level"] == level

    def test_hours_optional(self, populated_storage, sample_vehicle):
        logger = WeatherLogger(populated_storage)
        row = logger.log(vehicle_id=sample_vehicle.id, level="medium")
        assert row.get("hours") is None

    def test_notes_persisted(self, populated_storage, sample_vehicle):
        logger = WeatherLogger(populated_storage)
        row = logger.log(vehicle_id=sample_vehicle.id, level="low", notes="Cloudy day")
        assert row["notes"] == "Cloudy day"

    def test_both_ids(self, populated_storage, sample_vehicle, sample_bay):
        logger = WeatherLogger(populated_storage)
        row = logger.log(
            vehicle_id=sample_vehicle.id,
            bay_id=sample_bay.id,
            level="direct",
        )
        assert row["vehicle_id"] == sample_vehicle.id

    def test_bay_only_excluded_from_for_vehicle(self, populated_storage, sample_bay):
        logger = WeatherLogger(populated_storage)
        logger.log(bay_id=sample_bay.id, level="medium")
        assert logger.for_vehicle("any") == []

    def test_observed_at_present(self, populated_storage, sample_vehicle):
        logger = WeatherLogger(populated_storage)
        row = logger.log(vehicle_id=sample_vehicle.id, level="low")
        assert "observed_at" in row

    def test_valid_levels_constant(self):
        assert "medium" in VALID_LEVELS
        assert "direct" in VALID_LEVELS
