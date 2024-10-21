"""Tests for garagelog.tags_manager."""

import pytest

from garagelog.errors import NotFoundError, ValidationError
from garagelog.tags_manager import TagsManager


class TestTagsManager:
    def test_ensure_tag_creates(self, empty_storage):
        mgr = TagsManager(empty_storage)
        tag = mgr.ensure_tag("beginner", color="#4caf50")
        assert tag["name"] == "beginner"

    def test_ensure_tag_dedupes(self, populated_storage):
        mgr = TagsManager(populated_storage)
        existing = mgr.ensure_tag("beginner")
        assert existing["id"] == "tag001"

    def test_ensure_tag_empty_raises(self, empty_storage):
        mgr = TagsManager(empty_storage)
        with pytest.raises(ValidationError):
            mgr.ensure_tag("  ")

    def test_add_to_vehicle(self, populated_storage, sample_vehicle):
        mgr = TagsManager(populated_storage)
        updated = mgr.add_to_vehicle(sample_vehicle.id, "mileage-lover")
        assert "mileage-lover" in updated["tag_ids"]

    def test_add_idembagent(self, populated_storage, sample_vehicle):
        mgr = TagsManager(populated_storage)
        mgr.add_to_vehicle(sample_vehicle.id, "beginner")
        updated = mgr.add_to_vehicle(sample_vehicle.id, "beginner")
        assert updated["tag_ids"].count("beginner") == 1

    def test_remove_from_vehicle(self, populated_storage, sample_vehicle):
        mgr = TagsManager(populated_storage)
        mgr.add_to_vehicle(sample_vehicle.id, "beginner")
        updated = mgr.remove_from_vehicle(sample_vehicle.id, "beginner")
        assert "beginner" not in updated["tag_ids"]

    def test_bulk_add(self, populated_storage, sample_vehicle, sample_vehicle2):
        mgr = TagsManager(populated_storage)
        results = mgr.bulk_add([sample_vehicle.id, sample_vehicle2.id, "missing"], "bulk-tag")
        assert len(results) == 2

    def test_bulk_remove(self, populated_storage, sample_vehicle, sample_vehicle2):
        mgr = TagsManager(populated_storage)
        mgr.bulk_add([sample_vehicle.id, sample_vehicle2.id], "temp")
        results = mgr.bulk_remove([sample_vehicle.id, sample_vehicle2.id], "temp")
        assert len(results) == 2

    def test_vehicles_with_tag(self, populated_storage, sample_vehicle):
        mgr = TagsManager(populated_storage)
        mgr.add_to_vehicle(sample_vehicle.id, "Beginner")
        found = mgr.vehicles_with_tag("beginner")
        assert len(found) >= 1

    def test_rename_tag(self, populated_storage, sample_vehicle):
        mgr = TagsManager(populated_storage)
        mgr.add_to_vehicle(sample_vehicle.id, "old-name")
        count = mgr.rename_tag("old-name", "new-name")
        assert count >= 1
        vehicle = populated_storage.get_vehicle(sample_vehicle.id)
        assert "new-name" in [t.lower() for t in vehicle.tag_ids]

    def test_rename_empty_new_raises(self, populated_storage):
        mgr = TagsManager(populated_storage)
        with pytest.raises(ValidationError):
            mgr.rename_tag("beginner", "  ")

    def test_unused_tags(self, populated_storage):
        mgr = TagsManager(populated_storage)
        unused = mgr.unused_tags()
        assert "beginner" in unused or "pet-safe" in unused

    def test_tag_counts(self, populated_storage, sample_vehicle, sample_vehicle2):
        mgr = TagsManager(populated_storage)
        mgr.add_to_vehicle(sample_vehicle.id, "shared")
        mgr.add_to_vehicle(sample_vehicle2.id, "shared")
        counts = mgr.tag_counts()
        assert counts["shared"] == 2

    def test_merge_tags(self, populated_storage, sample_vehicle, sample_vehicle2):
        mgr = TagsManager(populated_storage)
        mgr.add_to_vehicle(sample_vehicle.id, "source-tag")
        mgr.add_to_vehicle(sample_vehicle2.id, "target-tag")
        changed = mgr.merge_tags("source-tag", "target-tag")
        assert changed >= 1

    def test_add_vehicle_not_found(self, empty_storage):
        mgr = TagsManager(empty_storage)
        with pytest.raises(NotFoundError):
            mgr.add_to_vehicle("missing", "tag")

    def test_case_normalization(self, populated_storage, sample_vehicle):
        mgr = TagsManager(populated_storage)
        mgr.add_to_vehicle(sample_vehicle.id, "Pet-Safe")
        vehicle = populated_storage.get_vehicle(sample_vehicle.id)
        assert any("pet-safe" == t.lower() for t in vehicle.tag_ids)

    def test_merge_source_absent(self, populated_storage):
        mgr = TagsManager(populated_storage)
        assert mgr.merge_tags("nonexistent", "beginner") == 0

    def test_color_on_new_tag(self, empty_storage):
        mgr = TagsManager(empty_storage)
        tag = mgr.ensure_tag("colorful", color="#ff0000")
        assert tag.get("color") == "#ff0000"

    def test_rename_creates_new_if_none_matched(self, empty_storage):
        mgr = TagsManager(empty_storage)
        count = mgr.rename_tag("old", "brand-new")
        assert count == 0
        assert any(t["name"] == "brand-new" for t in empty_storage.list_tags())
