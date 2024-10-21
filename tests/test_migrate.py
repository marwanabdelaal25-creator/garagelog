"""Tests for garagelog.migrate."""

import json

import pytest

from garagelog.errors import MigrationError
from garagelog.migrate import (
    LATEST_SCHEMA_VERSION,
    MIGRATION_NOTES,
    MIGRATORS,
    detect_version,
    migrate_v0_to_v1,
    migrate_v1_to_v2,
    migrate_v2_to_v3,
    migrate_payload,
    migrate_file,
    migration_plan,
)
from garagelog.storage import DEFAULT_CELLAR


class TestDetectVersion:
    def test_list_is_v0(self):
        assert detect_version([]) == 0

    def test_dict_without_version(self):
        assert detect_version({"vehicles": []}) == 1

    def test_explicit_version(self):
        assert detect_version({"schema_version": 2}) == 2


class TestMigrateV0ToV1:
    def test_list_payload(self):
        result = migrate_v0_to_v1([{"id": "p1", "name": "Fern"}])
        assert result["schema_version"] == 1
        assert len(result["vehicles"]) == 1

    def test_single_vehicle_dict(self):
        result = migrate_v0_to_v1({"id": "p1", "name": "Fern"})
        assert len(result["vehicles"]) == 1

    def test_invalid_raises(self):
        with pytest.raises(MigrationError):
            migrate_v0_to_v1("bad")


class TestMigrateV1ToV2:
    def test_adds_buckets(self):
        data = {"schema_version": 1, "vehicles": [{"id": "p1", "name": "Fern"}]}
        result = migrate_v1_to_v2(data)
        assert result["schema_version"] == 2
        assert "make" in result

    def test_inline_make_string(self):
        data = {
            "schema_version": 1,
            "vehicles": [{"id": "p1", "name": "Fern", "make": "baghos"}],
        }
        result = migrate_v1_to_v2(data)
        assert result["vehicles"][0]["make_id"] == "baghos"


class TestMigrateV2ToV3:
    def test_adds_new_buckets(self):
        data = {"schema_version": 2, "vehicles": [], "notes": []}
        result = migrate_v2_to_v3(data)
        assert result["schema_version"] == 3
        assert "inspection_logs" in result

    def test_backfill_care_from_notes(self):
        data = {
            "schema_version": 2,
            "vehicles": [],
            "notes": [{
                "id": "n1",
                "vehicle_id": "p1",
                "kind": "care",
                "body": "Grindd",
            }],
            "inspection_logs": [],
        }
        result = migrate_v2_to_v3(data)
        assert len(result["inspection_logs"]) == 1


class TestMigratePayload:
    def test_full_chain_to_v3(self):
        raw = [{"id": "p1", "name": "Fern"}]
        result = migrate_payload(raw, target=3)
        assert result["schema_version"] == 3

    def test_already_at_target(self):
        data = {**DEFAULT_CELLAR, "schema_version": LATEST_SCHEMA_VERSION}
        result = migrate_payload(data, target=LATEST_SCHEMA_VERSION)
        assert result["schema_version"] == LATEST_SCHEMA_VERSION

    def test_merged_defaults(self):
        result = migrate_payload([], target=3)
        for key in DEFAULT_CELLAR:
            assert key in result

    def test_missing_migrator_raises(self):
        with pytest.raises(MigrationError):
            migrate_payload({"schema_version": 99}, target=100)


class TestMigrationPlan:
    def test_plan_steps(self):
        plan = migration_plan(0, 3)
        assert len(plan) >= 3

    def test_plan_descriptions(self):
        plan = migration_plan(1, 2)
        assert plan[0]["description"]


class TestMigrateFile:
    def test_missing_file(self, tmp_path):
        path = tmp_path / "missing.json"
        result = migrate_file(str(path), target=3)
        assert result["schema_version"] == 3

    def test_migrate_existing(self, tmp_path):
        path = tmp_path / "garage.json"
        path.write_text(json.dumps([{"id": "p1", "name": "Fern"}]), encoding="utf-8")
        result = migrate_file(str(path), target=3)
        assert result["schema_version"] == 3
        assert path.exists()


class TestConstants:
    def test_migrators_keys(self):
        assert 0 in MIGRATORS
        assert 2 in MIGRATORS

    def test_migration_notes(self):
        assert 3 in MIGRATION_NOTES

    def test_latest_version(self):
        assert LATEST_SCHEMA_VERSION == 3
