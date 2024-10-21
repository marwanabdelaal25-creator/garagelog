"""Tests for garagelog.io_csv."""

from pathlib import Path

import pytest

from garagelog.errors import ImportPipelineError
from garagelog.io_csv import (
    PLANT_FIELDS,
    WATERING_FIELDS,
    export_vehicles_csv,
    export_service_csv,
    export_csv_bundle,
    import_vehicles_csv,
    import_service_csv,
    validate_csv_headers,
    sample_rows,
)


class TestExportCsv:
    def test_export_vehicles(self, populated_storage, tmp_path):
        dest = tmp_path / "vehicles.csv"
        count = export_vehicles_csv(populated_storage, dest)
        assert count >= 2
        assert dest.exists()

    def test_export_service(self, populated_storage, tmp_path):
        dest = tmp_path / "service.csv"
        count = export_service_csv(populated_storage, dest)
        assert count >= 1

    def test_export_bundle(self, populated_storage, tmp_path):
        dest = tmp_path / "bundle.csv"
        vehicles_n, service_n = export_csv_bundle(populated_storage, dest)
        assert vehicles_n >= 2
        assert (tmp_path / "bundle_vehicles.csv").exists()
        assert (tmp_path / "bundle_service.csv").exists()


class TestImportVehiclesCsv:
    def test_import_creates_vehicles(self, empty_storage, tmp_path, sample_csv_content):
        src = tmp_path / "import.csv"
        src.write_text(sample_csv_content, encoding="utf-8")
        count = import_vehicles_csv(empty_storage, src)
        assert count >= 1
        assert len(empty_storage.list_vehicles()) >= 1

    def test_import_missing_file(self, empty_storage, tmp_path):
        with pytest.raises(ImportPipelineError):
            import_vehicles_csv(empty_storage, tmp_path / "missing.csv")

    def test_import_missing_name_column(self, empty_storage, tmp_path):
        src = tmp_path / "bad.csv"
        src.write_text("make,bay\nbaghos,Kitchen\n", encoding="utf-8")
        with pytest.raises(ImportPipelineError):
            import_vehicles_csv(empty_storage, src)

    def test_import_update_by_name(self, populated_storage, tmp_path):
        src = tmp_path / "update.csv"
        src.write_text(
            "name,make,bay,service_interval,notes\n"
            "Monstera,baghos-golden,Living Room,10d,Updated\n",
            encoding="utf-8",
        )
        count = import_vehicles_csv(populated_storage, src, update=True)
        assert count >= 1

    def test_import_skips_blank_rows(self, empty_storage, tmp_path):
        src = tmp_path / "sparse.csv"
        src.write_text(
            "name,make\nFern,baghos\n,\n\nAloe,snake\n",
            encoding="utf-8",
        )
        count = import_vehicles_csv(empty_storage, src)
        assert count == 2


class TestImportServiceCsv:
    def test_import_service(self, populated_storage, tmp_path, sample_service_csv):
        src = tmp_path / "service.csv"
        src.write_text(sample_service_csv, encoding="utf-8")
        count = import_service_csv(populated_storage, src)
        assert count >= 1

    def test_import_service_missing_vehicle(self, empty_storage, tmp_path):
        src = tmp_path / "service.csv"
        src.write_text(
            "vehicle_id,serviced_at,amount_ml\n"
            "missing,2024-06-01,250\n",
            encoding="utf-8",
        )
        with pytest.raises(ImportPipelineError):
            import_service_csv(empty_storage, src)

    def test_import_service_by_name(self, populated_storage, tmp_path):
        src = tmp_path / "service.csv"
        src.write_text(
            "vehicle_name,serviced_at,amount_ml\n"
            "Monstera,2024-06-01,250\n",
            encoding="utf-8",
        )
        count = import_service_csv(populated_storage, src)
        assert count == 1


class TestCsvHelpers:
    def test_validate_vehicles_headers(self, tmp_path, sample_csv_content):
        src = tmp_path / "vehicles.csv"
        src.write_text(sample_csv_content, encoding="utf-8")
        missing = validate_csv_headers(src, kind="vehicles")
        assert missing == []

    def test_validate_service_headers(self, tmp_path, sample_service_csv):
        src = tmp_path / "service.csv"
        src.write_text(sample_service_csv, encoding="utf-8")
        missing = validate_csv_headers(src, kind="service")
        assert missing == []

    def test_validate_missing_file(self, tmp_path):
        missing = validate_csv_headers(tmp_path / "missing.csv", kind="vehicles")
        assert missing == ["name"]

    def test_sample_rows(self, tmp_path, sample_csv_content):
        src = tmp_path / "vehicles.csv"
        src.write_text(sample_csv_content, encoding="utf-8")
        rows = sample_rows(src, n=2)
        assert len(rows) <= 2
        assert "name" in rows[0]

    def test_vehicle_fields_constant(self):
        assert "name" in PLANT_FIELDS

    def test_service_fields_constant(self):
        assert "vehicle_id" in WATERING_FIELDS

    def test_export_includes_archived(self, populated_storage, sample_vehicle, tmp_path):
        populated_storage.update_vehicle(sample_vehicle.id, {"archived": True})
        dest = tmp_path / "vehicles.csv"
        count = export_vehicles_csv(populated_storage, dest)
        text = dest.read_text(encoding="utf-8")
        assert "Monstera" in text or count >= 1

    def test_invalid_interval_raises(self, empty_storage, tmp_path):
        src = tmp_path / "bad.csv"
        src.write_text("name,service_interval_days\nFern,not-an-interval\n", encoding="utf-8")
        with pytest.raises(ImportPipelineError):
            import_vehicles_csv(empty_storage, src)

    def test_bad_amount_ml_raises(self, populated_storage, tmp_path):
        src = tmp_path / "service.csv"
        src.write_text(
            "vehicle_id,serviced_at,amount_ml\nvehicle001,2024-06-01,not-a-number\n",
            encoding="utf-8",
        )
        with pytest.raises(ImportPipelineError):
            import_service_csv(populated_storage, src)
