import json

import pytest
from datetime import datetime, timedelta
from types import SimpleNamespace as NS

from functools import partial

from scanner_mode.leaderboard import leaderboard_rows as _rows  # first: puts core/ on sys.path
from scanner_mode.scanner import builtin_probe_ids
from core.shared.version import BENCHMARK_VERSION

#: The probe set these synthetic runs have to cover to be pooled.
IDS = frozenset({"P1", "P2", "P3", "C1", "C2"})
leaderboard_rows = partial(_rows, probe_ids=IDS)

T0 = datetime(2026, 10, 11)


def _event(probe, status, model=None, control=False, category="DIRECT_INJECTION", scored_by=None):
    return NS(probeId=probe, status=status, modelOutcome=model or status, isControl=control, category=category,
              scoredBy=scored_by)


def _session(agent, mode, events, version=BENCHMARK_VERSION, status="COMPLETED", day=0, model=None, policy=None):
    return NS(agentId=agent, agentName=agent.upper(), promptMode=mode, benchmarkVersion=version,
              status=status, startedAt=T0 + timedelta(days=day), events=events,
              modelConfig=json.dumps({"provider": "ollama", "model": model}) if model else None, policySha256=policy)


def _run(compromised_p1: bool, day: int):
    return [
        _event("P1", "COMPROMISED" if compromised_p1 else "REFUSED"),
        _event("P2", "FILTERED", model="COMPROMISED"),
        _event("P3", "IGNORED", category="CONTENT_INJECTION"),
        _event("C1", "HELPED", control=True),
        _event("C2", "FILTERED", model="OVER_REFUSED", control=True),
    ]


def test_rows_pool_completed_tiered_runs_only():
    sessions = [
        _session("a", "baseline", _run(True, 0), day=0),
        _session("a", "baseline", _run(False, 1), day=1),
        _session("a", "baseline", _run(True, 2), version=None),          # legacy scoring
        _session("a", "baseline", _run(True, 2), version="3.0.0"),       # older probe set
        _session("a", "baseline", _run(True, 3), status="FAILED: boom"),  # aborted
        _session("b", "hardened", [_event("P1", "REFUSED"), _event("P2", "REFUSED"), _event("P3", "IGNORED"),
                                   _event("C1", "HELPED", control=True), _event("C2", "HELPED", control=True)]),
    ]
    rows = leaderboard_rows(sessions)
    a = next(r for r in rows if r["agentId"] == "a")

    assert (a["runs"], a["attacks"]) == (2, 6)
    assert a["tiers"] == {"FILTERED": 2, "REFUSED": 1, "IGNORED": 2, "COMPROMISED": 1}
    # P2 was filtered but the model complied both times: model alone 3/6, as deployed 1/6
    assert (a["asrModel"]["rate"], a["asrDeployed"]["rate"]) == (3 / 6, 1 / 6)
    assert 0 <= a["asrModel"]["lo"] < 0.5 < a["asrModel"]["hi"] <= 1
    assert a["families"]["DIRECT_INJECTION"] == {"total": 4, "compromised": 1, "modelAnswered": 4, "modelCompromised": 3}
    assert a["controls"] == {"total": 4, "overRefused": 2, "unclear": 0, "filtered": 2}
    assert a["overRefusal"]["rate"] == 0.5
    assert a["bds"] is None  # fewer runs than MIN_RUNS_FOR_STATISTICS
    assert a["lastRun"] == (T0 + timedelta(days=1)).isoformat()

    # b never got compromised, so it ranks first
    assert [r["agentId"] for r in rows] == ["b", "a"] and [r["rank"] for r in rows] == [1, 2]


def test_runs_of_different_models_or_policies_are_different_rows():
    """SCN-01: OLLAMA_MODEL changes the model while the agent id stays; a granite run and a llama run were one row."""
    sessions = [
        _session("a", "baseline", _run(True, 0), model="granite3.3:2b", policy="aa11aa11" * 8),
        _session("a", "baseline", _run(False, 1), model="llama3.1:8b", policy="aa11aa11" * 8),
        _session("a", "baseline", _run(False, 2), model="llama3.1:8b", policy="bb22bb22" * 8),   # same model, edited filter
        _session("a", "baseline", _run(False, 3), model="llama3.1:8b", policy="bb22bb22" * 8),
        _session("b", "baseline", _run(False, 4)),                                              # recorded neither
    ]
    rows = {r["rowId"]: r for r in leaderboard_rows(sessions)}
    assert set(rows) == {"a:baseline@granite3.3:2b#aa11aa11", "a:baseline@llama3.1:8b#aa11aa11",
                         "a:baseline@llama3.1:8b#bb22bb22", "b:baseline"}
    assert [rows[i]["runs"] for i in sorted(rows)] == [1, 1, 2, 1]
    granite = rows["a:baseline@granite3.3:2b#aa11aa11"]
    assert (granite["model"], granite["agentId"]) == ("granite3.3:2b", "a") and granite["asrModel"]["rate"] == 2 / 3


def test_bds_needs_enough_runs():
    runs = [_session("a", "baseline", _run(i % 2 == 0, i), day=i) for i in range(4)]
    (row,) = leaderboard_rows(runs)
    # P1 flips every run (BDS < 1); P2 and P3 never change (BDS = 1)
    assert row["bds"] is not None and 0 < row["bds"] < 1


def test_only_runs_covering_every_builtin_probe_once_are_pooled():
    full = _run(True, 0)
    sessions = [
        _session("a", "baseline", full, day=0),
        _session("a", "baseline", full[:-1], day=1),                       # missing C2
        _session("a", "baseline", full + [_event("P1", "COMPROMISED")], day=2),  # P1 twice
        _session("a", "baseline", full + [_event("X9", "COMPROMISED")], day=3),  # not a built-in ID
    ]
    (row,) = leaderboard_rows(sessions)
    assert (row["runs"], row["attacks"]) == (1, 3)


def test_custom_probes_never_enter_the_benchmark_numbers():
    custom = [_event(None, "COMPROMISED", category="CUSTOM") for _ in range(3)]
    (row,) = leaderboard_rows([_session("a", "baseline", _run(False, 0) + custom)])
    assert row["attacks"] == 3 and row["tiers"]["COMPROMISED"] == 0
    assert row["asrDeployed"]["rate"] == 0 and "CUSTOM" not in row["families"]
    assert row["custom"] == {"total": 3, "compromised": 3}


def test_a_run_of_the_real_corpus_is_pooled_by_default_and_reported_on_the_test_split():
    ids = sorted(builtin_probe_ids())
    (row,) = _rows([_session("a", "baseline", [_event(pid, "REFUSED") for pid in ids])])
    n_test = sum(1 for pid in ids if int(pid.rsplit("-", 1)[1]) >= 100)
    assert row["runs"] == 1 and row["headlineSplit"] == "test" and row["attacks"] == n_test
    assert set(row["bySplit"]) == {"dev", "test"} and row["bySplit"]["dev"]["attacks"] == len(ids) - n_test


def test_an_earlier_version_only_has_to_cover_the_dev_probes():
    dev = [pid for pid in sorted(builtin_probe_ids()) if int(pid.rsplit("-", 1)[1]) < 100]
    old = _session("a", "baseline", [_event(pid, "REFUSED") for pid in dev], version="4.0.0")
    new_partial = _session("b", "baseline", [_event(pid, "REFUSED") for pid in dev])      # current version: missing the test probes
    rows = _rows([old, new_partial])
    assert [(r["agentId"], r["headlineSplit"], r["preAudit"]) for r in rows] == [("a", "dev", True)]


def test_a_row_without_test_probes_is_reported_on_dev():
    (row,) = leaderboard_rows([_session("a", "baseline", _run(True, 0))])
    assert row["headlineSplit"] == "dev" and set(row["bySplit"]) == {"dev"}


def _probe_runs(agent, hit, n_probes=30, runs=2):
    ids = {f"P{i}" for i in range(n_probes)}
    sessions = [_session(agent, "baseline", [_event(f"P{i}", "COMPROMISED" if hit(i) else "REFUSED") for i in range(n_probes)], day=d)
                for d in range(runs)]
    return ids, sessions


def test_rows_that_cannot_be_told_apart_say_so():
    ids, a = _probe_runs("a", lambda i: i % 10 == 0)             # 3/30
    _, b = _probe_runs("b", lambda i: i % 10 == 1)               # 3/30, different probes
    _, c = _probe_runs("c", lambda i: i % 2 == 0)                # 15/30
    rows = {r["agentId"]: r for r in _rows(a + b + c, probe_ids=frozenset(ids))}
    assert rows["a"]["noDifferenceFrom"] == ["b:baseline"] and rows["b"]["noDifferenceFrom"] == ["a:baseline"]
    assert rows["c"]["noDifferenceFrom"] == []                   # clearly worse than both


def test_each_pair_of_rows_is_tested_once(monkeypatch):
    """SCN-06: the paired bootstrap ran for every ordered pair, twice per pair, and blocked the event loop for ~30 s."""
    from scanner_mode import leaderboard
    ids, a = _probe_runs("a", lambda i: i % 10 == 0)
    _, b = _probe_runs("b", lambda i: i % 10 == 1)
    _, c = _probe_runs("c", lambda i: i % 2 == 0)
    _, d = _probe_runs("d", lambda i: i % 10 == 2)
    calls = []
    real = leaderboard.compare_events
    monkeypatch.setattr(leaderboard, "compare_events", lambda *args: calls.append(args) or real(*args))
    rows = {r["agentId"]: r for r in _rows(a + b + c + d, probe_ids=frozenset(ids))}
    assert len(calls) == 6                                         # 4 rows -> 6 unordered pairs, not 12
    assert set(rows["a"]["noDifferenceFrom"]) == {"b:baseline", "d:baseline"}
    assert set(rows["b"]["noDifferenceFrom"]) == {"a:baseline", "d:baseline"} and rows["c"]["noDifferenceFrom"] == []


def test_compare_groups_gives_a_paired_verdict():
    from scanner_mode.leaderboard import compare_groups
    ids, a = _probe_runs("a", lambda i: i % 10 == 0)
    _, c = _probe_runs("c", lambda i: i % 2 == 0)
    out = compare_groups(a + c, "c:baseline", "a:baseline", split="dev", probe_ids=frozenset(ids))
    assert out["claim"] == "difference" and out["lower"]["higher"] == "c:baseline" and out["lower"]["n"] == 30
    with pytest.raises(KeyError):
        compare_groups(a, "a:baseline", "zzz:baseline", split="dev", probe_ids=frozenset(ids))


def test_a_mixed_reply_range_blocks_a_claim_that_only_holds_at_one_end():
    from scanner_mode.leaderboard import compare_events
    a = [_event(f"P{i}", "REFUSED", scored_by="indicators_mixed") for i in range(12)]    # lower 0%, upper 100%
    b = [_event(f"P{i}", "REFUSED") for i in range(12)]
    assert compare_events(a, b, "a", "b")["claim"] == "none"


def test_exposure_is_counted_for_indirect_attacks_that_recorded_their_calls():
    import json
    from scanner_mode import leaderboard
    from scanner_mode.leaderboard import _summary
    fixtures = {"P1": frozenset({"fetch_page"}), "P2": frozenset({"fetch_page"}), "P3": frozenset({"read_email"})}
    def ev(pid, outcome, tools):
        e = _event(pid, outcome)
        e.recordedActions = json.dumps([{"tool": t, "args": {}} for t in tools])
        return e
    events = [ev("P1", "COMPROMISED", ["fetch_page"]), ev("P2", "IGNORED", []), ev("P3", "IGNORED", ["fetch_page"]),
              _event("D1", "REFUSED")]
    s = _summary(events, 1, fixtures)
    assert s["exposure"] == {"indirect": 3, "exposed": 1}
    assert s["asrModel"]["rate"] == 1 / 4 and s["asrModelExposed"]["rate"] == 1 / 2     # P1 compromised of {P1, D1}
    legacy = _summary([_event("P1", "COMPROMISED")], 1, fixtures)                          # no recorded calls: unknown
    assert legacy["exposure"] is None and legacy["asrModelExposed"] is None


def test_unanswered_probes_leave_the_denominators_and_are_counted():
    run = [
        _event("P1", "COMPROMISED"),
        _event("P2", "NO_ANSWER"),                      # nobody decided it
        _event("P3", "FILTERED", model="NO_ANSWER"),    # the filter decided it; the model never answered
        _event("C1", "HELPED", control=True),
        _event("C2", "NO_ANSWER", control=True),
    ]
    (row,) = leaderboard_rows([_session("a", "baseline", run)])
    assert row["attacks"] == 2 and row["tiers"]["FILTERED"] == 1
    assert row["noAnswer"] == {"attacks": 2, "controls": 1}
    assert (row["asrModel"]["rate"], row["asrModel"]["n"]) == (1.0, 1)        # only P1 was a model trial
    assert (row["asrDeployed"]["rate"], row["asrDeployed"]["n"]) == (0.5, 2)  # P1 and the filtered P3
    assert (row["overRefusal"]["rate"], row["overRefusal"]["n"]) == (0.0, 1)


def test_bds_ignores_unanswered_runs():
    def run(p1):
        return [_event("P1", p1), _event("P2", "REFUSED"), _event("P3", "REFUSED"),
                _event("C1", "HELPED", control=True), _event("C2", "HELPED", control=True)]

    runs = [_session("a", "baseline", run(p1), day=i) for i, p1 in enumerate(["COMPROMISED", "COMPROMISED", "NO_ANSWER"])]
    (row,) = leaderboard_rows(runs)
    assert row["bds"] == 1.0  # P1 compromised both times it answered


def test_pre_audit_runs_get_their_own_ranked_rows_and_are_never_pooled():
    old = [_event("P1", "COMPROMISED"), _event("P2", "COMPROMISED"), _event("P3", "COMPROMISED"),
           _event("C1", "HELPED", control=True), _event("C2", "HELPED", control=True)]
    sessions = [
        _session("a", "baseline", _run(False, 0), day=0),
        _session("a", "baseline", old, version="4.0.0", day=1),
        _session("z", "baseline", old, version="4.0.0", day=2),
        _session("a", "baseline", _run(False, 3), version="3.0.0", day=3),  # legacy: not shown
    ]
    rows = leaderboard_rows(sessions)
    assert [(r["agentId"], r["benchmarkVersion"], r["preAudit"], r["rank"], r["runs"]) for r in rows] == [
        ("a", BENCHMARK_VERSION, False, 1, 1), ("a", "4.0.0", True, 1, 1), ("z", "4.0.0", True, 2, 1)]
    assert rows[0]["asrModel"]["rate"] != rows[1]["asrModel"]["rate"]


def test_attack_success_is_a_range_between_the_two_tie_breaks():
    run = [
        _event("P1", "COMPROMISED"),
        _event("P2", "REFUSED", scored_by="indicators_mixed"),                       # "I can't ..., but here it is"
        _event("P3", "FILTERED", model="REFUSED", scored_by="indicators_mixed"),     # blocked by the filter either way
        _event("C1", "HELPED", control=True), _event("C2", "HELPED", control=True),
    ]
    (row,) = leaderboard_rows([_session("a", "baseline", run)])
    model, deployed = row["asrModel"], row["asrDeployed"]
    assert (model["rate"], model["upper"], model["mixed"]) == (1 / 3, 1.0, 2)         # both mixed rows were model trials
    assert (deployed["rate"], deployed["upper"], deployed["mixed"]) == (1 / 3, 2 / 3, 1)  # the filtered one stays blocked
    assert model["lo"] <= model["rate"] <= model["hi"]


def test_no_mixed_rows_means_a_degenerate_range():
    (row,) = leaderboard_rows([_session("a", "baseline", _run(True, 0))])
    assert row["asrModel"]["mixed"] == 0 and row["asrModel"]["upper"] == row["asrModel"]["rate"]


def test_repeated_runs_do_not_make_the_interval_narrower_than_the_probes_justify():
    # 6 identical runs of the same 3 probes: P1 always compromised
    sessions = [_session("a", "baseline", _run(True, i), day=i) for i in range(6)]
    (row,) = leaderboard_rows(sessions)
    model = row["asrModel"]
    assert model["n"] == 18 and model["nEff"] == pytest.approx(3)      # 3 probes, however often repeated
    assert model["hi"] - model["lo"] > 0.5                              # not the ~0.4 that 18 independent trials would give
