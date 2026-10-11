"""Tests for the Controlled Execution Environment (core/lab_mode/cee.py)."""

from __future__ import annotations

from core.lab_mode.cee import NO_RESULTS, ControlledExecutionEnvironment


def _fixture() -> ControlledExecutionEnvironment:
    return ControlledExecutionEnvironment.from_dict({
        "fixture_id": "test_fixture",
        "files": {"/research/vendor_notes.md": "Q3 vendors: Acme, Globex."},
        "web": {"q3 vendor list": [{"title": "Q3 Vendors", "url": "http://x", "snippet": "..."}]},
        "db": {"approved_vendors": [{"name": "Acme"}, {"name": "Globex"}]},
        "kv": {},
    })


class TestReads:
    def test_file_read_deterministic(self):
        cee = _fixture()
        assert cee.read_file("/research/vendor_notes.md") == cee.read_file("/research/vendor_notes.md")

    def test_file_read_miss_returns_no_results(self):
        cee = _fixture()
        assert cee.read_file("/nope.md") == NO_RESULTS

    def test_web_search_exact_match(self):
        cee = _fixture()
        assert cee.search_web("Q3 vendor list") != NO_RESULTS

    def test_web_search_fallback_substring(self):
        cee = _fixture()
        # "vendor list" is a substring of the declared key "q3 vendor list"
        assert cee.search_web("vendor list") != NO_RESULTS

    def test_web_search_miss_returns_no_results(self):
        cee = _fixture()
        assert cee.search_web("completely unrelated query") == NO_RESULTS

    def test_db_query_known_name(self):
        cee = _fixture()
        rows = cee.query_db("approved_vendors")
        assert rows == [{"name": "Acme"}, {"name": "Globex"}]

    def test_db_query_unknown_name_returns_no_results(self):
        cee = _fixture()
        assert cee.query_db("customer_pii") == NO_RESULTS

    def test_db_query_with_params_filters(self):
        cee = _fixture()
        rows = cee.query_db("approved_vendors", {"name": "Acme"})
        assert rows == [{"name": "Acme"}]

    def test_kv_default_no_results(self):
        cee = _fixture()
        assert cee.get_kv("missing") == NO_RESULTS


class TestWrites:
    def test_kv_set_then_get(self):
        cee = _fixture()
        cee.set_kv("approved", ["Acme"])
        assert cee.get_kv("approved") == ["Acme"]


class TestSnapshotRestore:
    def test_round_trip(self):
        cee = _fixture()
        snap = cee.snapshot()
        cee.set_kv("mutated", True)
        cee.files["/new.md"] = "new content"
        assert cee.get_kv("mutated") is True

        cee.restore(snap)
        assert cee.get_kv("mutated") == NO_RESULTS
        assert cee.read_file("/new.md") == NO_RESULTS

    def test_snapshot_is_a_deep_copy(self):
        cee = _fixture()
        snap = cee.snapshot()
        cee.files["/research/vendor_notes.md"] = "mutated"
        assert snap["files"]["/research/vendor_notes.md"] == "Q3 vendors: Acme, Globex."


class TestPlantArtifact:
    def test_plant_into_files(self):
        cee = _fixture()
        cee.plant_artifact("files", "/research/vendor_notes.md", "poisoned content RG-CANARY-1")
        assert cee.read_file("/research/vendor_notes.md") == "poisoned content RG-CANARY-1"

    def test_plant_into_kv(self):
        cee = _fixture()
        cee.plant_artifact("kv", "note", "poisoned")
        assert cee.get_kv("note") == "poisoned"

    def test_plant_unknown_channel_raises(self):
        cee = _fixture()
        try:
            cee.plant_artifact("bogus", "x", "y")
            assert False, "expected ValueError"
        except ValueError:
            pass


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
