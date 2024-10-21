"""Tests for garagelog.collections."""

import pytest

from garagelog.errors import NotFoundError, ValidationError
from garagelog.collections import CollectionManager


class TestCollectionManager:
    def test_create(self, populated_storage, sample_vehicle):
        mgr = CollectionManager(populated_storage)
        coll = mgr.create("Kitchen Herbs", vehicle_ids=[sample_vehicle.id])
        assert coll["name"] == "Kitchen Herbs"
        assert sample_vehicle.id in coll["vehicle_ids"]

    def test_create_empty_name_raises(self, empty_storage):
        mgr = CollectionManager(empty_storage)
        with pytest.raises(ValidationError):
            mgr.create("  ")

    def test_create_invalid_vehicle_raises(self, empty_storage):
        mgr = CollectionManager(empty_storage)
        with pytest.raises(NotFoundError):
            mgr.create("Bad", vehicle_ids=["missing"])

    def test_list_all(self, populated_storage, sample_vehicle):
        mgr = CollectionManager(populated_storage)
        mgr.create("Group A", vehicle_ids=[sample_vehicle.id])
        assert len(mgr.list_all()) == 1

    def test_get(self, populated_storage, sample_vehicle):
        mgr = CollectionManager(populated_storage)
        coll = mgr.create("Favorites")
        found = mgr.get(coll["id"])
        assert found["name"] == "Favorites"

    def test_get_not_found(self, empty_storage):
        mgr = CollectionManager(empty_storage)
        with pytest.raises(NotFoundError):
            mgr.get("missing")

    def test_add_vehicle(self, populated_storage, sample_vehicle, sample_vehicle2):
        mgr = CollectionManager(populated_storage)
        coll = mgr.create("Group")
        updated = mgr.add_vehicle(coll["id"], sample_vehicle.id)
        updated = mgr.add_vehicle(coll["id"], sample_vehicle2.id)
        assert len(updated["vehicle_ids"]) == 2

    def test_add_vehicle_dedupes(self, populated_storage, sample_vehicle):
        mgr = CollectionManager(populated_storage)
        coll = mgr.create("Group", vehicle_ids=[sample_vehicle.id])
        updated = mgr.add_vehicle(coll["id"], sample_vehicle.id)
        assert updated["vehicle_ids"].count(sample_vehicle.id) == 1

    def test_remove_vehicle(self, populated_storage, sample_vehicle):
        mgr = CollectionManager(populated_storage)
        coll = mgr.create("Group", vehicle_ids=[sample_vehicle.id])
        updated = mgr.remove_vehicle(coll["id"], sample_vehicle.id)
        assert sample_vehicle.id not in updated["vehicle_ids"]

    def test_rename(self, populated_storage):
        mgr = CollectionManager(populated_storage)
        coll = mgr.create("Old Name")
        updated = mgr.rename(coll["id"], "New Name")
        assert updated["name"] == "New Name"

    def test_rename_blank_raises(self, populated_storage):
        mgr = CollectionManager(populated_storage)
        coll = mgr.create("Name")
        with pytest.raises(ValidationError):
            mgr.rename(coll["id"], "  ")

    def test_delete(self, populated_storage):
        mgr = CollectionManager(populated_storage)
        coll = mgr.create("Temp")
        mgr.delete(coll["id"])
        assert mgr.list_all() == []

    def test_vehicles_in(self, populated_storage, sample_vehicle):
        mgr = CollectionManager(populated_storage)
        coll = mgr.create("Group", vehicle_ids=[sample_vehicle.id])
        vehicles = mgr.vehicles_in(coll["id"])
        assert len(vehicles) == 1

    def test_vehicles_in_skips_stale(self, populated_storage):
        mgr = CollectionManager(populated_storage)
        coll = mgr.create("Group")
        populated_storage.update_collection(coll["id"], {"vehicle_ids": ["stale_id"]})
        assert mgr.vehicles_in(coll["id"]) == []

    def test_collections_for_vehicle(self, populated_storage, sample_vehicle):
        mgr = CollectionManager(populated_storage)
        mgr.create("A", vehicle_ids=[sample_vehicle.id])
        mgr.create("B", vehicle_ids=[sample_vehicle.id])
        cols = mgr.collections_for_vehicle(sample_vehicle.id)
        assert len(cols) == 2

    def test_merge(self, populated_storage, sample_vehicle, sample_vehicle2):
        mgr = CollectionManager(populated_storage)
        t = mgr.create("Target", vehicle_ids=[sample_vehicle.id])
        s = mgr.create("Source", vehicle_ids=[sample_vehicle2.id])
        merged = mgr.merge(t["id"], s["id"])
        assert sample_vehicle2.id in merged["vehicle_ids"]
        assert len(mgr.list_all()) == 1

    def test_merge_dedupes_overlap(self, populated_storage, sample_vehicle):
        mgr = CollectionManager(populated_storage)
        t = mgr.create("Target", vehicle_ids=[sample_vehicle.id])
        s = mgr.create("Source", vehicle_ids=[sample_vehicle.id])
        merged = mgr.merge(t["id"], s["id"])
        assert merged["vehicle_ids"].count(sample_vehicle.id) == 1

    def test_description_stored(self, populated_storage):
        mgr = CollectionManager(populated_storage)
        coll = mgr.create("Herbs", description="Kitchen window")
        assert coll["description"] == "Kitchen window"

    def test_add_unknown_vehicle_raises(self, populated_storage):
        mgr = CollectionManager(populated_storage)
        coll = mgr.create("Group")
        with pytest.raises(NotFoundError):
            mgr.add_vehicle(coll["id"], "missing")
