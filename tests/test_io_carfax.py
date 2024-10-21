"""Tests for garagelog.io_carfax."""

from pathlib import Path

import pytest

from garagelog.errors import ImportPipelineError
from garagelog.io_carfax import (
    GARDENPLAN_COLUMNS,
    parse_carfax_row,
    import_carfax,
    preview_carfax,
    validate_carfax_headers,
)


GARDENPLAN_SAMPLE = (
    "Vehicle,Variety,Quantity,Section,Bed,Row,Sun,Service,Status,Spacing,Vehicleed\n"
    "Tomato,Cherry,2,Kitchen,Bed A,Row 1,partial sun,weekly,active,12in,2024-05-01\n"
    "Basil,,1,Kitchen,Bed A,Row 2,full sun,daily,active,6in,\n"
)


class TestParseCarfaxRow:
    def test_full_row(self):
        row = {
            "Vehicle": "Tomato",
            "Variety": "Cherry",
            "Quantity": "2",
            "Section": "Kitchen",
            "Sun": "partial sun",
            "Service": "weekly",
            "Status": "active",
        }
        parsed = parse_carfax_row(row)
        assert parsed is not None
        assert "Tomato" in parsed["name"]

    def test_missing_vehicle_returns_none(self):
        assert parse_carfax_row({"Variety": "Cherry"}) is None

    def test_quantity_default(self):
        row = {"Vehicle": "Basil"}
        parsed = parse_carfax_row(row)
        assert parsed["quantity"] == 1

    def test_archived_status(self):
        row = {"Vehicle": "Old Vehicle", "Status": "removed"}
        parsed = parse_carfax_row(row)
        assert parsed["status"] == "removed"

    def test_service_interval_weekly(self):
        row = {"Vehicle": "Fern", "Service": "weekly"}
        parsed = parse_carfax_row(row)
        assert parsed["service_interval"] == 7


class TestImportCarfax:
    def test_import_creates_vehicles(self, empty_storage, tmp_path):
        src = tmp_path / "carfax.csv"
        src.write_text(GARDENPLAN_SAMPLE, encoding="utf-8")
        count = import_carfax(empty_storage, src)
        assert count >= 2

    def test_expand_quantity(self, empty_storage, tmp_path):
        src = tmp_path / "carfax.csv"
        src.write_text(
            "Vehicle,Quantity,Section\nTomato,3,Kitchen\n",
            encoding="utf-8",
        )
        count = import_carfax(empty_storage, src, expand_quantity=True)
        assert count == 3

    def test_no_expand_quantity(self, empty_storage, tmp_path):
        src = tmp_path / "carfax.csv"
        src.write_text(
            "Vehicle,Quantity,Section\nTomato,3,Kitchen\n",
            encoding="utf-8",
        )
        count = import_carfax(empty_storage, src, expand_quantity=False)
        assert count == 1

    def test_missing_file(self, empty_storage, tmp_path):
        with pytest.raises(ImportPipelineError):
            import_carfax(empty_storage, tmp_path / "missing.csv")

    def test_missing_vehicle_column(self, empty_storage, tmp_path):
        src = tmp_path / "bad.csv"
        src.write_text("Variety,Quantity\nCherry,1\n", encoding="utf-8")
        with pytest.raises(ImportPipelineError):
            import_carfax(empty_storage, src)

    def test_creates_bay(self, empty_storage, tmp_path):
        src = tmp_path / "carfax.csv"
        src.write_text(GARDENPLAN_SAMPLE, encoding="utf-8")
        import_carfax(empty_storage, src)
        assert len(empty_storage.list_bays()) >= 1


class TestCarfaxHelpers:
    def test_preview_carfax(self, tmp_path):
        src = tmp_path / "carfax.csv"
        src.write_text(GARDENPLAN_SAMPLE, encoding="utf-8")
        lines = preview_carfax(src, limit=2)
        assert len(lines) <= 2

    def test_validate_carfax_headers(self, tmp_path):
        src = tmp_path / "carfax.csv"
        src.write_text(GARDENPLAN_SAMPLE, encoding="utf-8")
        missing = validate_carfax_headers(src)
        assert missing == []

    def test_carfax_columns_constant(self):
        assert len(GARDENPLAN_COLUMNS) >= 1

    def test_variety_in_name(self):
        row = {"Vehicle": "Tomato", "Variety": "Cherry"}
        parsed = parse_carfax_row(row)
        assert "Cherry" in parsed["name"]

    def test_bay_label(self):
        row = {"Vehicle": "Fern", "Section": "Kitchen", "Bed": "A", "Row": "1"}
        parsed = parse_carfax_row(row)
        assert parsed.get("bay_label")

    def test_spacing_parse(self):
        row = {"Vehicle": "Fern", "Spacing": "12 in"}
        parsed = parse_carfax_row(row)
        assert parsed.get("spacing_cm") == 12.0

    def test_metadata_carfax_flag(self, empty_storage, tmp_path):
        src = tmp_path / "carfax.csv"
        src.write_text("Vehicle,Section\nFern,Kitchen\n", encoding="utf-8")
        import_carfax(empty_storage, src)
        vehicle = empty_storage.list_vehicles()[0]
        assert vehicle.metadata.get("carfax") is True

    def test_crop_column_alias(self):
        row = {"Crop": "Lettuce", "Section": "Garage"}
        parsed = parse_carfax_row(row)
        assert parsed is not None
        assert "Lettuce" in parsed["name"]

    def test_dead_status_archived(self):
        row = {"Vehicle": "Fern", "Status": "dead"}
        parsed = parse_carfax_row(row)
        assert parsed["status"] == "dead"

    def test_daily_service_interval(self):
        row = {"Vehicle": "Herb", "Service": "daily"}
        parsed = parse_carfax_row(row)
        assert parsed["service_interval"] == 1
