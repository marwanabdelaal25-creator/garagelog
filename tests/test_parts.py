"""Tests for garagelog.parts."""

import pytest

from garagelog.errors import NotFoundError, ValidationError
from garagelog.parts import LabelCatalog


class TestLabelCatalog:
    def test_register(self, populated_storage, sample_vehicle, tmp_path):
        catalog = LabelCatalog(populated_storage)
        label_path = tmp_path / "fern.jpg"
        label_path.write_bytes(b"fake")
        row = catalog.register(sample_vehicle.id, str(label_path), caption="New growth")
        assert row["filename"] == "fern.jpg"
        assert row["caption"] == "New growth"

    def test_empty_path_raises(self, populated_storage, sample_vehicle):
        catalog = LabelCatalog(populated_storage)
        with pytest.raises(ValidationError):
            catalog.register(sample_vehicle.id, "   ")

    def test_unknown_vehicle_raises(self, empty_storage, tmp_path):
        catalog = LabelCatalog(empty_storage)
        with pytest.raises(NotFoundError):
            catalog.register("missing", str(tmp_path / "x.jpg"))

    def test_for_vehicle(self, populated_storage, sample_vehicle, tmp_path):
        catalog = LabelCatalog(populated_storage)
        p1 = tmp_path / "a.jpg"
        p2 = tmp_path / "b.jpg"
        p1.write_bytes(b"x")
        p2.write_bytes(b"x")
        catalog.register(sample_vehicle.id, str(p1), taken_at="2024-01-01T00:00:00+00:00")
        catalog.register(sample_vehicle.id, str(p2), taken_at="2024-06-01T00:00:00+00:00")
        rows = catalog.for_vehicle(sample_vehicle.id)
        assert rows[0]["taken_at"] >= rows[1]["taken_at"]

    def test_get(self, populated_storage, sample_vehicle, tmp_path):
        catalog = LabelCatalog(populated_storage)
        path = tmp_path / "pic.jpg"
        path.write_bytes(b"x")
        row = catalog.register(sample_vehicle.id, str(path))
        found = catalog.get(row["id"])
        assert found["id"] == row["id"]

    def test_get_not_found(self, populated_storage):
        catalog = LabelCatalog(populated_storage)
        with pytest.raises(NotFoundError):
            catalog.get("missing")

    def test_update_caption(self, populated_storage, sample_vehicle, tmp_path):
        catalog = LabelCatalog(populated_storage)
        path = tmp_path / "pic.jpg"
        path.write_bytes(b"x")
        row = catalog.register(sample_vehicle.id, str(path))
        updated = catalog.update_caption(row["id"], "Updated caption")
        assert updated["caption"] == "Updated caption"

    def test_delete(self, populated_storage, sample_vehicle, tmp_path):
        catalog = LabelCatalog(populated_storage)
        path = tmp_path / "pic.jpg"
        path.write_bytes(b"x")
        row = catalog.register(sample_vehicle.id, str(path))
        removed = catalog.delete(row["id"])
        assert removed["id"] == row["id"]
        with pytest.raises(NotFoundError):
            catalog.get(row["id"])

    def test_missing_files(self, populated_storage, sample_vehicle, tmp_path):
        catalog = LabelCatalog(populated_storage)
        missing_path = tmp_path / "gone.jpg"
        catalog.register(sample_vehicle.id, str(missing_path))
        missing = catalog.missing_files()
        assert len(missing) == 1

    def test_missing_files_empty_when_exists(self, populated_storage, sample_vehicle, tmp_path):
        catalog = LabelCatalog(populated_storage)
        path = tmp_path / "exists.jpg"
        path.write_bytes(b"x")
        catalog.register(sample_vehicle.id, str(path))
        assert catalog.missing_files() == []

    def test_custom_taken_at(self, populated_storage, sample_vehicle, tmp_path):
        catalog = LabelCatalog(populated_storage)
        path = tmp_path / "pic.jpg"
        path.write_bytes(b"x")
        row = catalog.register(sample_vehicle.id, str(path), taken_at="2023-05-01T00:00:00+00:00")
        assert row["taken_at"].startswith("2023-05-01")

    def test_registered_at_set(self, populated_storage, sample_vehicle, tmp_path):
        catalog = LabelCatalog(populated_storage)
        path = tmp_path / "pic.jpg"
        path.write_bytes(b"x")
        row = catalog.register(sample_vehicle.id, str(path))
        assert "registered_at" in row

    def test_multiple_labels(self, populated_storage, sample_vehicle, tmp_path):
        catalog = LabelCatalog(populated_storage)
        for i in range(3):
            p = tmp_path / f"{i}.jpg"
            p.write_bytes(b"x")
            catalog.register(sample_vehicle.id, str(p))
        assert len(catalog.for_vehicle(sample_vehicle.id)) == 3

    def test_bucket_constant(self):
        assert LabelCatalog.BUCKET == "labels"

    def test_path_normalization(self, populated_storage, sample_vehicle, tmp_path):
        catalog = LabelCatalog(populated_storage)
        path = tmp_path / "subdir" / "pic.jpg"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"x")
        row = catalog.register(sample_vehicle.id, str(path))
        assert "subdir" in row["path"]

    def test_delete_not_found(self, populated_storage):
        catalog = LabelCatalog(populated_storage)
        with pytest.raises(NotFoundError):
            catalog.delete("missing")

    def test_caption_default_empty(self, populated_storage, sample_vehicle, tmp_path):
        catalog = LabelCatalog(populated_storage)
        path = tmp_path / "pic.jpg"
        path.write_bytes(b"x")
        row = catalog.register(sample_vehicle.id, str(path))
        assert row["caption"] == ""
