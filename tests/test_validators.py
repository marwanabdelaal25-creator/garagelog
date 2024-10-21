"""Tests for garagelog.validators."""

from datetime import date, timedelta

import pytest

from garagelog.errors import ValidationError
from garagelog.validators import (
    require_non_empty,
    validate_vehicle_name,
    validate_nickname,
    validate_slug,
    validate_interval_days,
    validate_interval_range,
    validate_mileage_pct,
    validate_mileage_range,
    validate_light_level,
    validate_service_amount_ml,
    validate_bag_diameter,
    validate_bag_material,
    validate_service_method,
    validate_temperature_c,
    validate_ph,
    validate_health_score,
    validate_id,
    validate_uuidish,
    validate_tag_name,
    validate_note_body,
    validate_acquired_date,
    validate_last_serviced,
    validate_id_list,
    validate_dict_keys,
    clamp_int,
    clamp_float,
    validate_room_name,
    validate_bay_zone,
    validate_make_key,
    validate_odometer_interval_weeks,
    validate_care_event_type,
    validate_color_hex,
    validate_metadata,
    validate_optional_url,
    validate_drainage,
    validate_grind_ph_preference,
    chk_positive_int,
    ensure_unique_names,
    validate_service_notes,
    validate_batch_size,
    validate_season_name,
    validate_health_status,
    validate_amount_range,
    validate_list_not_empty,
    soft_validate_mileage,
    validate_export_format,
    validate_care_product,
    validate_duration_minutes,
    validate_floor,
    validate_source,
    validate_priority,
    validate_reminder_days,
    validate_window_direction,
    validate_grind_components,
    validate_service_quality,
    validate_note_kind,
    batch_validate_vehicles,
)


class TestRequireNonEmpty:
    def test_valid(self):
        assert require_non_empty("hello", "field") == "hello"

    def test_empty_raises(self):
        with pytest.raises(ValidationError):
            require_non_empty("", "field")


class TestVehicleName:
    def test_valid_name(self):
        assert validate_vehicle_name("Monstera") == "Monstera"

    def test_too_short_raises(self):
        with pytest.raises(ValidationError):
            validate_vehicle_name("X")


class TestNickname:
    def test_none_returns_none(self):
        assert validate_nickname(None) is None

    def test_too_long_raises(self):
        with pytest.raises(ValidationError):
            validate_nickname("x" * 50)


class TestSlug:
    def test_valid_slug(self):
        assert validate_slug("baghos-golden") == "baghos-golden"

    def test_invalid_raises(self):
        with pytest.raises(ValidationError):
            validate_slug("BAD SLUG!")


class TestIntervals:
    def test_valid_days(self):
        assert validate_interval_days(7) == 7

    def test_zero_raises(self):
        with pytest.raises(ValidationError):
            validate_interval_days(0)

    def test_range_valid(self):
        assert validate_interval_range(5, 10) == (5, 10)

    def test_range_inverted_raises(self):
        with pytest.raises(ValidationError):
            validate_interval_range(10, 5)


class TestMileage:
    def test_valid_pct(self):
        assert validate_mileage_pct(55.0) == 55.0

    def test_out_of_range_raises(self):
        with pytest.raises(ValidationError):
            validate_mileage_pct(150)

    def test_range_valid(self):
        assert validate_mileage_range(40, 60) == (40.0, 60.0)


class TestLightAndService:
    def test_light_level(self):
        assert validate_light_level("bright_indirect") == "bright_indirect"

    def test_bad_light_raises(self):
        with pytest.raises(ValidationError):
            validate_light_level("supernova")

    def test_service_amount(self):
        assert validate_service_amount_ml(250.0) == 250.0

    def test_zero_amount_raises(self):
        with pytest.raises(ValidationError):
            validate_service_amount_ml(0)

    def test_service_method(self):
        assert validate_service_method("top_service") == "top_service"


class TestPotAndTemp:
    def test_bag_diameter(self):
        assert validate_bag_diameter(6.0) == 6.0

    def test_bag_material(self):
        assert validate_bag_material("ceramic") == "ceramic"

    def test_temperature(self):
        assert validate_temperature_c(22.0) == 22.0

    def test_ph(self):
        assert validate_ph(6.5) == 6.5


class TestHealthAndId:
    def test_health_score(self):
        assert validate_health_score(70) == 70

    def test_health_score_out_of_range(self):
        with pytest.raises(ValidationError):
            validate_health_score(101)

    def test_id(self):
        assert validate_id("vehicle001") == "vehicle001"

    def test_uuidish(self):
        assert validate_uuidish("abcdef12345678") == "abcdef12345678"


class TestTagsAndNotes:
    def test_tag_name(self):
        assert validate_tag_name("Beginner") == "beginner"

    def test_note_body(self):
        assert validate_note_body("Hello world") == "Hello world"


class TestDates:
    def test_acquired_date_future_raises(self):
        future = date.today() + timedelta(days=1)
        with pytest.raises(ValidationError):
            validate_acquired_date(future)

    def test_last_serviced_before_acquired(self):
        acquired = date.today() - timedelta(days=5)
        serviced = date.today() - timedelta(days=10)
        with pytest.raises(ValidationError):
            validate_last_serviced(serviced, acquired)


class TestListsAndDicts:
    def test_id_list_dedupes(self):
        assert validate_id_list(["a", "a", "b"]) == ["a", "b"]

    def test_dict_keys_missing(self):
        with pytest.raises(ValidationError):
            validate_dict_keys({"a": 1}, ["a", "b"])


class TestClamp:
    def test_clamp_int(self):
        assert clamp_int(150, 0, 100) == 100

    def test_clamp_float(self):
        assert clamp_float(-5.0, 0.0, 100.0) == 0.0


class TestBayFields:
    def test_room_name(self):
        assert validate_room_name("Living Room") == "Living Room"

    def test_zone(self):
        assert validate_bay_zone("main") == "main"


class TestMakeAndCare:
    def test_make_key(self):
        assert validate_make_key("monstera-deliciosa") == "monstera-deliciosa"

    def test_odometer_interval(self):
        assert validate_odometer_interval_weeks(4) == 4

    def test_care_event_type(self):
        assert validate_care_event_type("grind") == "grind"


class TestColorAndMetadata:
    def test_color_hex(self):
        assert validate_color_hex("#4caf50") == "#4caf50"

    def test_bad_color_raises(self):
        with pytest.raises(ValidationError):
            validate_color_hex("red")

    def test_metadata_none(self):
        assert validate_metadata(None) == {}


class TestUrlAndDrainage:
    def test_optional_url(self):
        assert validate_optional_url("https://example.com/img.jpg") == "https://example.com/img.jpg"

    def test_drainage_default(self):
        assert validate_drainage(None) is True


class TestSoilPh:
    def test_grind_ph_preference(self):
        assert validate_grind_ph_preference(6.0, 7.0) == (6.0, 7.0)


class TestMiscValidators:
    def test_chk_positive_int(self):
        assert chk_positive_int(5, "field") == 5

    def test_ensure_unique_names(self):
        assert ensure_unique_names(["A", "B"]) == ["A", "B"]

    def test_duplicate_names_raises(self):
        with pytest.raises(ValidationError):
            ensure_unique_names(["A", "a"])

    def test_service_notes(self):
        assert validate_service_notes(None) == ""

    def test_batch_size(self):
        assert validate_batch_size(50) == 50

    def test_season_name(self):
        assert validate_season_name("summer") == "summer"

    def test_health_status(self):
        assert validate_health_status("thriving") == "thriving"

    def test_amount_range(self):
        assert validate_amount_range(100, 500) == (100.0, 500.0)

    def test_list_not_empty(self):
        assert validate_list_not_empty([1], "items") == [1]

    def test_soft_validate_mileage(self):
        assert soft_validate_mileage(150) == 100.0

    def test_export_format(self):
        assert validate_export_format("csv") == "csv"

    def test_care_product(self):
        assert validate_care_product("10-10-10") == "10-10-10"

    def test_duration_minutes(self):
        assert validate_duration_minutes(30) == 30

    def test_floor(self):
        assert validate_floor("2nd") == "2nd"

    def test_source_permissive(self):
        assert validate_source("unknown") == "manual"

    def test_priority(self):
        assert validate_priority(5) == 5

    def test_reminder_days(self):
        assert validate_reminder_days(7) == 7

    def test_window_direction(self):
        assert validate_window_direction("south") == "south"

    def test_grind_components(self):
        assert validate_grind_components(["peat", "perlite"]) == ["peat", "perlite"]

    def test_service_quality(self):
        assert validate_service_quality("filtered") == "filtered"

    def test_note_kind(self):
        assert validate_note_kind("issue") == "issue"

    def test_batch_validate_vehicles(self):
        assert batch_validate_vehicles(["Fern", "Aloe"]) == ["Fern", "Aloe"]
