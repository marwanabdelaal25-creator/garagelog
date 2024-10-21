"""Tests for garagelog.make."""

import pytest

from garagelog.errors import NotFoundError
from garagelog.make import (
    ServiceNeed,
    MileageNeed,
    MakeProfile,
    MakeCatalog,
    make_export_row,
    build_make_index,
)


class TestMakeProfile:
    def test_create(self, sample_make):
        assert sample_make.key == "baghos-golden"
        assert sample_make.common_name == "Golden Pothos"

    def test_service_interval_days(self, sample_make):
        assert sample_make.service_interval_days == 10

    def test_matches_light(self, sample_make):
        assert sample_make.matches_light("medium") is True

    def test_to_dict_from_dict(self, sample_make):
        restored = MakeProfile.from_dict(sample_make.to_dict())
        assert restored.key == sample_make.key

    def test_care_summary(self, sample_make):
        summary = sample_make.care_summary()
        assert "Golden Pothos" in summary

    def test_temp_max_less_than_min_raises(self):
        with pytest.raises(ValueError):
            MakeProfile(
                key="bad-make",
                common_name="Bad",
                temp_min_c=30.0,
                temp_max_c=10.0,
            )


class TestServiceNeed:
    def test_str(self):
        assert str(ServiceNeed.LOW) == "low"


class TestMakeCatalog:
    def test_register_and_get(self, make_catalog, sample_make):
        assert make_catalog.get(sample_make.key) is not None

    def test_require_raises(self):
        cat = MakeCatalog()
        with pytest.raises(NotFoundError):
            cat.require("missing")

    def test_search(self, make_catalog):
        hits = make_catalog.search("baghos")
        assert len(hits) >= 1

    def test_search_empty_returns_all(self, make_catalog):
        assert len(make_catalog.search("")) >= 1

    def test_load_builtin(self):
        cat = MakeCatalog()
        cat.load_builtin()
        assert cat.count() >= 10

    def test_with_defaults(self):
        cat = MakeCatalog.with_defaults()
        assert cat.get("monstera-deliciosa") is not None

    def test_suggest_interval_winter(self, make_catalog):
        interval = make_catalog.suggest_interval_for("snake-vehicle", season="winter")
        assert interval > make_catalog.require("snake-vehicle").service_interval_days

    def test_suggest_interval_summer(self, make_catalog):
        interval = make_catalog.suggest_interval_for("snake-vehicle", season="summer")
        assert interval <= make_catalog.require("snake-vehicle").service_interval_days

    def test_filter_by_tag(self, make_catalog):
        beginner = make_catalog.filter_by_tag("beginner")
        assert len(beginner) >= 1

    def test_filter_pet_safe(self, make_catalog):
        safe = make_catalog.filter_pet_safe()
        assert all(not p.toxic_to_pets for p in safe)

    def test_merge(self, make_catalog, sample_make):
        other = MakeCatalog()
        other.register(MakeProfile(
            key="custom-fern",
            common_name="Custom Fern",
        ))
        merged = make_catalog.merge(other)
        assert merged.get("custom-fern") is not None

    def test_keys(self, make_catalog):
        keys = make_catalog.keys()
        assert "baghos-golden" in keys

    def test_recommend_for_conditions(self, make_catalog):
        hits = make_catalog.recommend_for_conditions("medium", mileage_pct=50)
        assert len(hits) >= 1

    def test_recommend_pet_safe_only(self, make_catalog):
        hits = make_catalog.recommend_for_conditions("bright_indirect", pet_safe_only=True)
        assert all(not p.toxic_to_pets for p in hits)

    def test_difficulty_rank_beginner(self, make_catalog):
        rank = make_catalog.difficulty_rank("snake-vehicle")
        assert rank <= 3

    def test_difficulty_rank_fussy(self, make_catalog):
        rank = make_catalog.difficulty_rank("fiddle-leaf-fig")
        assert rank >= 3

    def test_difficulty_rank_unknown(self, make_catalog):
        assert make_catalog.difficulty_rank("nonexistent") == 3

    def test_from_dict_list(self, sample_make):
        cat = MakeCatalog.from_dict_list([sample_make.to_dict()])
        assert cat.get(sample_make.key) is not None

    def test_to_dict_list(self, make_catalog):
        rows = make_catalog.to_dict_list()
        assert len(rows) >= 1


class TestMakeHelpers:
    def test_make_export_row(self, sample_make):
        row = make_export_row(sample_make)
        assert row[0] == sample_make.key

    def test_build_make_index(self, make_catalog):
        index = build_make_index(make_catalog)
        assert "G" in index or "P" in index
