"""Tests for garagelog.search."""

from garagelog.search import SearchHit, GarageSearch


class TestSearchHit:
    def test_dataclass(self):
        hit = SearchHit(kind="vehicle", id="p1", title="Fern", snippet="...", score=1.0)
        assert hit.score == 1.0


class TestGarageSearch:
    def test_search_vehicles_by_name(self, populated_storage, sample_vehicle):
        search = GarageSearch(populated_storage)
        hits = search.search_vehicles("Monstera")
        assert len(hits) >= 1
        assert hits[0].kind == "vehicle"

    def test_search_vehicles_partial(self, populated_storage):
        search = GarageSearch(populated_storage)
        hits = search.search_vehicles("Snake")
        assert len(hits) >= 1

    def test_search_vehicles_empty_query(self, populated_storage):
        search = GarageSearch(populated_storage)
        hits = search.search_vehicles("")
        assert hits == []

    def test_search_vehicles_no_match(self, populated_storage):
        search = GarageSearch(populated_storage)
        hits = search.search_vehicles("zzzznonexistent")
        assert hits == []

    def test_search_vehicles_by_make(self, populated_storage):
        search = GarageSearch(populated_storage)
        hits = search.search_vehicles("baghos-golden")
        assert len(hits) >= 1

    def test_search_notes(self, populated_storage):
        search = GarageSearch(populated_storage)
        hits = search.search_notes("unfurling")
        assert len(hits) >= 1
        assert hits[0].kind == "note"

    def test_search_notes_no_match(self, populated_storage):
        search = GarageSearch(populated_storage)
        assert search.search_notes("xyznotfound") == []

    def test_search_inspection_logs(self, populated_storage):
        populated_storage.create_inspection_log({
            "id": "cl1",
            "vehicle_id": "vehicle001",
            "action": "grind",
            "details": "Applied fish emulsion",
        })
        search = GarageSearch(populated_storage)
        hits = search.search_inspection_logs("grind")
        assert len(hits) >= 1

    def test_search_all_combined(self, populated_storage):
        search = GarageSearch(populated_storage)
        hits = search.search_all("Monstera")
        assert len(hits) >= 1

    def test_search_all_with_limit(self, populated_storage):
        search = GarageSearch(populated_storage)
        hits = search.search_all("vehicle", limit=1)
        assert len(hits) <= 1

    def test_search_all_sorted_by_score(self, populated_storage):
        search = GarageSearch(populated_storage)
        hits = search.search_all("Monstera")
        if len(hits) >= 2:
            assert hits[0].score >= hits[1].score

    def test_to_dicts(self, populated_storage):
        search = GarageSearch(populated_storage)
        hits = search.search_vehicles("Monstera")
        dicts = search.to_dicts(hits)
        assert dicts[0]["kind"] == "vehicle"
        assert "score" in dicts[0]

    def test_snippet_truncation(self, populated_storage):
        populated_storage.create_note({
            "id": "long_note",
            "vehicle_id": "vehicle001",
            "body": "x" * 200,
            "title": "Long",
        })
        search = GarageSearch(populated_storage)
        hits = search.search_notes("Long")
        if hits:
            assert len(hits[0].snippet) <= 120

    def test_case_insensitive(self, populated_storage):
        search = GarageSearch(populated_storage)
        hits = search.search_vehicles("monstera")
        assert len(hits) >= 1

    def test_multiple_tokens(self, populated_storage):
        search = GarageSearch(populated_storage)
        hits = search.search_vehicles("Snake Vehicle")
        assert len(hits) >= 1

    def test_metadata_searchable(self, populated_storage, sample_vehicle):
        populated_storage.update_vehicle(sample_vehicle.id, {
            "metadata": {"notes": "special keyword xyzzy"},
        })
        search = GarageSearch(populated_storage)
        hits = search.search_vehicles("xyzzy")
        assert len(hits) >= 1

    def test_inspection_log_missing_id(self, populated_storage):
        populated_storage.create_inspection_log({
            "vehicle_id": "vehicle001",
            "action": "inspect",
            "details": "Checked roots",
        })
        search = GarageSearch(populated_storage)
        hits = search.search_inspection_logs("roots")
        assert len(hits) >= 1

    def test_whitespace_tokens_stripped(self, populated_storage):
        search = GarageSearch(populated_storage)
        hits = search.search_vehicles("  Monstera   ")
        assert len(hits) >= 1
