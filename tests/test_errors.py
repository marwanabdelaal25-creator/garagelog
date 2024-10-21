"""Tests for garagelog.errors."""

import pytest
from garagelog.errors import (
    GaragelogError, StorageError, ValidationError, NotFoundError,
    ImportPipelineError, ExportError, MigrationError, PluginError,
    ConflictError, GaragelogWarning, is_not_found, is_validation,
    format_error, wrap_os_error, raise_if_missing, chain_errors,
    validation_errors_from_dict, storage_read_error, storage_write_error,
    import_pipeline_error,
)
from garagelog.validators import validate_vehicle_name, validate_mileage_pct


class TestGaragelogError:
    def test_base_error_message(self):
        exc = GaragelogError("something broke")
        assert exc.message == "something broke"
        assert exc.code == "BREWLOG_ERROR"

    def test_custom_code(self):
        exc = GaragelogError("x", code="CUSTOM")
        assert exc.code == "CUSTOM"


class TestStorageError:
    def test_without_path(self):
        exc = StorageError("read failed")
        assert exc.path is None
        assert exc.code == "STORAGE_ERROR"

    def test_with_path(self):
        exc = StorageError("read failed", path="/tmp/garage.json")
        assert "/tmp/garage.json" in str(exc)


class TestValidationError:
    def test_with_field(self):
        exc = ValidationError("too long", field="name")
        assert "name:" in str(exc)

    def test_without_field(self):
        exc = ValidationError("bad value")
        assert exc.field is None


class TestNotFoundError:
    def test_entity_and_identifier(self):
        exc = NotFoundError("vehicle", "abc123")
        assert exc.entity == "vehicle"
        assert "abc123" in str(exc)


class TestImportExportErrors:
    def test_import_pipeline_error(self):
        exc = ImportPipelineError("csv", "bad row")
        assert "[csv]" in str(exc)

    def test_export_error(self):
        exc = ExportError("backup.json", "disk full")
        assert "backup.json" in str(exc)

    def test_migration_error(self):
        exc = MigrationError(1, 2, "missing bucket")
        assert exc.from_ver == 1

    def test_conflict_error(self):
        exc = ConflictError("duplicate", key="slug")
        assert exc.key == "slug"

    def test_plugin_error(self):
        exc = PluginError("hook failed")
        assert isinstance(exc, GaragelogError)


class TestHelpers:
    def test_is_not_found(self):
        assert is_not_found(NotFoundError("x", "y"))
        assert not is_not_found(ValueError("nope"))

    def test_is_validation(self):
        assert is_validation(ValidationError("bad"))

    def test_format_error_validation(self):
        exc = ValidationError("bad", field="name")
        assert "VALIDATION_ERROR" in format_error(exc)

    def test_format_error_generic(self):
        exc = StorageError("fail")
        assert "STORAGE_ERROR" in format_error(exc)

    def test_wrap_os_error(self):
        exc = wrap_os_error(OSError("errno 13"), "write")
        assert isinstance(exc, StorageError)

    def test_raise_if_missing_raises(self):
        with pytest.raises(NotFoundError):
            raise_if_missing("vehicle", None, "id1")

    def test_raise_if_missing_ok(self):
        raise_if_missing("vehicle", {"id": "1"}, "id1")

    def test_chain_errors(self):
        errs = [ValidationError("a", field="x"), ValidationError("b", field="y")]
        assert ";" in chain_errors(errs)

    def test_validation_errors_from_dict(self):
        rules = {"name": validate_vehicle_name, "mileage": validate_mileage_pct}
        errs = validation_errors_from_dict({"name": "", "mileage": 150}, rules)
        assert len(errs) >= 1

    def test_storage_read_error(self):
        exc = storage_read_error("/g.json", "parse error")
        assert exc.path == "/g.json"

    def test_storage_write_error(self):
        exc = storage_write_error("/g.json", "disk full")
        assert exc.path == "/g.json"

    def test_import_pipeline_error_helper(self):
        exc = import_pipeline_error("csv", 5, "bad name")
        assert "line 5" in str(exc)

    def test_garagelog_warning(self):
        w = GaragelogWarning("minor issue")
        assert w.code == "WARNING"
