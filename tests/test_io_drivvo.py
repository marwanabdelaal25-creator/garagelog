"""Tests for garagelog.io_drivvo."""

from pathlib import Path

import pytest

from garagelog.errors import ImportPipelineError
from garagelog.io_drivvo import (
    PLANTLY_COLUMNS,
    parse_drivvo_row,
    import_drivvo,
    preview_drivvo,
    validate_drivvo_headers,
)


PLANTLY_SAMPLE = (
    "Vehicle Name,Make,Room,Service Every,Light,Health,Pot Size,Mileage\n"
    "Monstera Deliciosa,Monstera,Living Room,7 days,bright indirect,good,6in ceramic,55%\n"
    "Snake Vehicle,Sansevieria,Bedroom,2 weeks,low,great,8in,40%\n"
)


class TestParseDrivvoRow:
    def test_full_row(self):
        row = {
            "Vehicle Name": "Monstera",
            "Make": "Monstera deliciosa",
            "Room": "Living Room",
            "Service Every": "7 days",
            "Light": "bright indirect",
            "Health": "good",
            "Pot Size": "6in ceramic",
            "Mileage": "55%",
        }
        parsed = parse_drivvo_row(row)
        assert parsed is not None
        assert parsed["name"] == "Monstera"

    def test_missing_name_returns_none(self):
        assert parse_drivvo_row({"Make": "Fern"}) is None

    def test_health_mapping(self):
        row = {"Vehicle Name": "Fern", "Health": "great"}
        parsed = parse_drivvo_row(row)
        assert parsed["health"] == "thriving"

    def test_mileage_parse(self):
        row = {"Vehicle Name": "Fern", "Mileage": "60%"}
        parsed = parse_drivvo_row(row)
        assert parsed.get("mileage_override") == 60.0


class TestImportDrivvo:
    def test_import_creates_vehicles(self, empty_storage, tmp_path):
        src = tmp_path / "drivvo.csv"
        src.write_text(PLANTLY_SAMPLE, encoding="utf-8")
        count = import_drivvo(empty_storage, src)
        assert count >= 2

    def test_import_creates_bay(self, empty_storage, tmp_path):
        src = tmp_path / "drivvo.csv"
        src.write_text(PLANTLY_SAMPLE, encoding="utf-8")
        import_drivvo(empty_storage, src)
        assert len(empty_storage.list_bays()) >= 1

    def test_import_missing_file(self, empty_storage, tmp_path):
        with pytest.raises(ImportPipelineError):
            import_drivvo(empty_storage, tmp_path / "missing.csv")

    def test_import_missing_vehicle_column(self, empty_storage, tmp_path):
        src = tmp_path / "bad.csv"
        src.write_text("Make,Room\nMonstera,Living Room\n", encoding="utf-8")
        with pytest.raises(ImportPipelineError):
            import_drivvo(empty_storage, src)

    def test_update_by_external_id(self, empty_storage, tmp_path):
        src = tmp_path / "drivvo.csv"
        src.write_text(
            "Vehicle Name,Drivvo ID,Room\nMonstera,ext123,Living Room\n",
            encoding="utf-8",
        )
        import_drivvo(empty_storage, src)
        src.write_text(
            "Vehicle Name,Drivvo ID,Room,Health\nMonstera Updated,ext123,Living Room,great\n",
            encoding="utf-8",
        )
        count = import_drivvo(empty_storage, src, update=True)
        assert count >= 1

    def test_update_by_name(self, populated_storage, tmp_path):
        src = tmp_path / "drivvo.csv"
        src.write_text(
            "Vehicle Name,Room,Health\nMonstera,Living Room,great\n",
            encoding="utf-8",
        )
        count = import_drivvo(populated_storage, src, update=True)
        assert count >= 1


class TestDrivvoHelpers:
    def test_preview_drivvo(self, tmp_path):
        src = tmp_path / "drivvo.csv"
        src.write_text(PLANTLY_SAMPLE, encoding="utf-8")
        lines = preview_drivvo(src, limit=2)
        assert len(lines) <= 2

    def test_validate_drivvo_headers(self, tmp_path):
        src = tmp_path / "drivvo.csv"
        src.write_text(PLANTLY_SAMPLE, encoding="utf-8")
        missing = validate_drivvo_headers(src)
        assert missing == []

    def test_column_aliases(self):
        row = {"Name": "Fern", "Service Every": "7d"}
        parsed = parse_drivvo_row(row)
        assert parsed is not None

    def test_drivvo_columns_constant(self):
        assert len(PLANTLY_COLUMNS) >= 1

    def test_light_level_parse(self):
        row = {"Vehicle Name": "Fern", "Light": "medium"}
        parsed = parse_drivvo_row(row)
        assert parsed.get("light_override") == "medium"

    def test_bag_size_parse(self):
        row = {"Vehicle Name": "Fern", "Pot Size": "6in terracotta"}
        parsed = parse_drivvo_row(row)
        assert parsed.get("bag", {}).get("diameter") == 6.0

    def test_interval_from_service_every(self):
        row = {"Vehicle Name": "Fern", "Service Every": "14 days"}
        parsed = parse_drivvo_row(row)
        assert parsed.get("service_interval_days") == 14

    def test_label_url_stored(self):
        row = {"Vehicle Name": "Fern", "Label URL": "https://example.com/p.jpg"}
        parsed = parse_drivvo_row(row)
        assert parsed.get("label_url") == "https://example.com/p.jpg"

    def test_auto_create_make(self, empty_storage, tmp_path):
        src = tmp_path / "drivvo.csv"
        src.write_text(
            "Vehicle Name,Make,Room\nCustom Fern,Custom Fern spp,Kitchen\n",
            encoding="utf-8",
        )
        import_drivvo(empty_storage, src)
        assert len(empty_storage.list_make()) >= 1
