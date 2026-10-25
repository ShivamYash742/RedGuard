"""The probe corpus as an instrument: indirect attacks arrive in tool results, nothing gives the test away."""

from difflib import SequenceMatcher
from itertools import combinations

import pytest

from core.scanner_mode.datasets.loader import load_all_datasets
from scanner_mode.agents import _tools

PROBES = {p["id"]: p for p in load_all_datasets(validate=False)}
ATTACKS = [p for p in PROBES.values() if not p.get("benign_control")]

#: Wording that tells the model (or a reader) it is being tested.
GIVEAWAYS = ["attacker@evil.com", "attacker.com", "evil.com", "[injected", "injected document", "injected plan step",
             "embedded instruction", "this simulates", "simulates a poisoned", "poisoned document", "tool output -",
             "[tool output"]

#: Probes whose attack lives in something the agent reads, not in what the user says.
INDIRECT = ["RG-CI-001", "RG-CI-002", "RG-CI-003", "RG-CI-004", "RG-CI-005", "RG-CI-006", "RG-CI-007", "RG-CI-008", "RG-CI-009",
            "RG-TM-001", "RG-TM-002", "RG-TM-006", "RG-TM-007", "RG-PM-002", "RG-PM-003", "RG-PM-004", "RG-MP-004", "RG-MP-006"]


def _model_visible(probe):
    return "\n".join([probe["prompt"], *probe.get("tool_fixtures", {}).values()])


@pytest.mark.parametrize("probe_id", sorted(PROBES))
def test_nothing_the_model_reads_gives_the_test_away(probe_id):
    text = _model_visible(PROBES[probe_id]).lower()
    assert not [g for g in GIVEAWAYS if g in text]


@pytest.mark.parametrize("probe_id", INDIRECT)
def test_indirect_attacks_arrive_in_a_tool_result_not_the_user_message(probe_id):
    probe = PROBES[probe_id]
    assert probe.get("tool_fixtures"), "no tool result carries the attack"
    for text in probe["tool_fixtures"].values():
        assert text not in probe["prompt"] and text[:60] not in probe["prompt"]
    assert len(probe["prompt"]) < 300, "the user message is long enough to be carrying the payload"


def test_every_control_that_reads_a_tool_has_a_matched_attack():
    assert PROBES["RG-CTL-006"]["tool_fixtures"].keys() == PROBES["RG-TM-006"]["tool_fixtures"].keys()
    assert PROBES["RG-CTL-006"]["prompt"] == PROBES["RG-TM-006"]["prompt"]


def test_no_two_attacks_are_near_duplicates():
    pairs = [(a["id"], b["id"], SequenceMatcher(None, _model_visible(a), _model_visible(b)).ratio())
             for a, b in combinations(ATTACKS, 2)]
    close = [p for p in pairs if p[2] > 0.8]
    assert not close, close


def test_no_attack_carries_template_leftovers():
    for probe in ATTACKS:
        text = _model_visible(probe)
        assert "INJECTION:" not in text and "TOOL:" not in text, probe["id"]


def test_fixture_tools_return_the_planted_result_only_inside_a_probe():
    assert _tools.fetch_page.invoke({"url": "https://x.example"}) == "Error 404: page not found."
    calls = []
    tokens = (_tools.FIXTURES.set({"fetch_page": "planted page"}), _tools.RECORDER.set(calls))
    try:
        assert _tools.fetch_page.invoke({"url": "https://x.example"}) == "planted page"
        assert _tools.read_email.invoke({"query": "team"}) == "No messages found."   # no fixture for this tool
    finally:
        _tools.FIXTURES.reset(tokens[0])
        _tools.RECORDER.reset(tokens[1])
    assert [c["tool"] for c in calls] == ["fetch_page", "read_email"]  # reads are recorded: they show the agent was exposed
    assert _tools.fetch_page.invoke({"url": "https://x.example"}) == "Error 404: page not found."


def test_every_fixture_names_a_real_read_tool():
    names = {t.name for t in _tools.FIXTURE_TOOLS}
    used = {name for p in PROBES.values() for name in p.get("tool_fixtures", {})}
    assert used and used <= names
