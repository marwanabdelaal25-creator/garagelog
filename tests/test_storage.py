"""Tests for garagelog.storage."""

import json

import pytest

from garagelog.errors import NotFoundError, StorageError, ValidationError
from garagelog.bay import Bay
from garagelog.vehicle import Vehicle, HealthStatus
from garagelog.make import MakeProfile
from garagelog.storage import JsonStorage, DEFAULT_CELLAR, SCHEMA_VERSION


class TestJsonStorageInit:
    def test_creates_empty_garage(self, tmp_garage_path):
        storage = JsonStorage(tmp_garage_path)
        assert tmp_garage_path.exists()

    def test_loads_existing(self, populated_storage, tmp_garage_path):
        storage2 = JsonStorage(tmp_garage_path)
        assert len(storage2.list_vehicles()) >= 2


class TestVehicles:
    def test_create_and_list(self, empty_storage, sample_vehicle):
        created = empty_storage.create_vehicle(sample_vehicle)
        assert created.name == sample_vehicle.name

    def test_get_vehicle(self, populated_storage, sample_vehicle):
        vehicle = populated_storage.get_vehicle(sample_vehicle.id)
        assert vehicle.id == sample_vehicle.id

    def test_get_vehicle_not_found(self, empty_storage):
        with pytest.raises(NotFoundError):
            empty_storage.get_vehicle("missing")

    def test_update_vehicle(self, populated_storage, sample_vehicle):
        updated = populated_storage.update_vehicle(sample_vehicle.id, {"nickname": "NewNick"})
        assert updated.nickname == "NewNick"

    def test_delete_vehicle(self, populated_storage, sample_vehicle):
        populated_storage.delete_vehicle(sample_vehicle.id)
        with pytest.raises(NotFoundError):
            populated_storage.get_vehicle(sample_vehicle.id)

    def test_list_vehicles_active_only(self, populated_storage, sample_vehicle):
        populated_storage.update_vehicle(sample_vehicle.id, {"archived": True})
        active = populated_storage.list_vehicles(active_only=True)
        assert all(not p.archived for p in active)

    def test_duplicate_vehicle_raises(self, populated_storage, sample_vehicle):
        with pytest.raises(ValidationError):
            populated_storage.create_vehicle(sample_vehicle.to_dict())


class TestMake:
    def test_create_make(self, empty_storage, sample_make):
        created = empty_storage.create_make(sample_make)
        assert created.key == sample_make.key

    def test_get_make(self, populated_storage, sample_make):
        sp = populated_storage.get_make(sample_make.key)
        assert sp.common_name == sample_make.common_name

    def test_delete_make(self, populated_storage, sample_make):
        populated_storage.delete_make(sample_make.key)
        with pytest.raises(NotFoundError):
            populated_storage.get_make(sample_make.key)


class TestBays:
    def test_create_bay(self, empty_storage, sample_bay):
        created = empty_storage.create_bay(sample_bay)
        assert created.name == sample_bay.name

    def test_get_bay(self, populated_storage, sample_bay):
        loc = populated_storage.get_bay(sample_bay.id)
        assert loc.id == sample_bay.id

    def test_update_bay(self, populated_storage, sample_bay):
        updated = populated_storage.update_bay(sample_bay.id, {"notes": "Updated"})
        assert updated.notes == "Updated"


class TestService:
    def test_create_service_event(self, populated_storage, sample_vehicle):
        event = populated_storage.create_service_event({
            "id": "we_new",
            "vehicle_id": sample_vehicle.id,
            "amount_ml": 300,
        })
        assert event["vehicle_id"] == sample_vehicle.id

    def test_list_service_events_filtered(self, populated_storage, sample_vehicle):
        events = populated_storage.list_service_events(vehicle_id=sample_vehicle.id)
        assert len(events) >= 1

    def test_delete_service_event(self, populated_storage):
        events = populated_storage.list_service_events()
        eid = events[0]["id"]
        populated_storage.delete_service_event(eid)
        with pytest.raises(NotFoundError):
            populated_storage.get_service_event(eid)


class TestTagsAndNotes:
    def test_create_tag(self, empty_storage):
        tag = empty_storage.create_tag({"id": "tag_new", "name": "test"})
        assert tag["name"] == "test"

    def test_create_note(self, populated_storage, sample_vehicle):
        note = populated_storage.create_note({
            "id": "note_new",
            "vehicle_id": sample_vehicle.id,
            "body": "Test note",
        })
        assert note["body"] == "Test note"

    def test_list_notes_filtered(self, populated_storage, sample_vehicle):
        notes = populated_storage.list_notes(vehicle_id=sample_vehicle.id)
        assert len(notes) >= 1


class TestAuditAndPlugins:
    def test_append_audit(self, empty_storage):
        entry = empty_storage.append_audit({"action": "create", "entity": "vehicle"})
        assert "timestamp" in entry

    def test_upsert_plugin(self, empty_storage):
        plugin = empty_storage.upsert_plugin({"id": "p1", "name": "Test Plugin"})
        assert plugin["name"] == "Test Plugin"
        updated = empty_storage.upsert_plugin({"id": "p1", "name": "Updated"})
        assert updated["name"] == "Updated"


class TestRecurringAndCollections:
    def test_create_recurring(self, empty_storage):
        task = empty_storage.create_recurring({"id": "r1", "title": "Weekly mist"})
        assert task["title"] == "Weekly mist"

    def test_create_collection(self, empty_storage):
        coll = empty_storage.create_collection({"id": "c1", "name": "Favorites"})
        assert coll["name"] == "Favorites"


class TestStorageCore:
    def test_snapshot(self, populated_storage):
        snap = populated_storage.snapshot()
        assert "vehicles" in snap

    def test_replace_all(self, empty_storage, sample_vehicle):
        empty_storage.replace_all({
            **DEFAULT_CELLAR,
            "vehicles": [sample_vehicle.to_dict()],
        })
        assert len(empty_storage.list_vehicles()) == 1

    def test_mutate(self, empty_storage):
        def add_tag(data):
            data["tags"].append({"id": "t1", "name": "test"})
        empty_storage.mutate(add_tag)
        assert len(empty_storage.list_tags()) == 1

    def test_load_corrupt_json(self, tmp_garage_path):
        tmp_garage_path.write_text("{not json", encoding="utf-8")
        with pytest.raises(StorageError):
            JsonStorage(tmp_garage_path)

    def test_schema_version_in_default(self):
        assert DEFAULT_CELLAR["schema_version"] == SCHEMA_VERSION
