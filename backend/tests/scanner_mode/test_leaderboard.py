from datetime import datetime, timedelta
from types import SimpleNamespace as NS

from scanner_mode.leaderboard import leaderboard_rows  # first: puts core/ on sys.path
from core.shared.version import BENCHMARK_VERSION

T0 = datetime(2026, 10, 11)


def _event(probe, status, model=None, control=False, category="DIRECT_INJECTION"):
    return NS(probeId=probe, status=status, modelOutcome=model or status, isControl=control, category=category)


def _session(agent, mode, events, version=BENCHMARK_VERSION, status="COMPLETED", day=0):
    return NS(agentId=agent, agentName=agent.upper(), promptMode=mode, benchmarkVersion=version,
              status=status, startedAt=T0 + timedelta(days=day), events=events)


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
        _session("b", "hardened", [_event("P1", "REFUSED")]),
    ]
    rows = leaderboard_rows(sessions)
    a = next(r for r in rows if r["agentId"] == "a")

    assert (a["runs"], a["attacks"]) == (2, 6)
    assert a["tiers"] == {"FILTERED": 2, "REFUSED": 1, "IGNORED": 2, "COMPROMISED": 1}
    # P2 was filtered but the model complied both times: model alone 3/6, as deployed 1/6
    assert (a["asrModel"]["rate"], a["asrDeployed"]["rate"]) == (3 / 6, 1 / 6)
    assert 0 <= a["asrModel"]["lo"] < 0.5 < a["asrModel"]["hi"] <= 1
    assert a["families"]["DIRECT_INJECTION"] == {"total": 4, "compromised": 1, "modelCompromised": 3}
    assert a["controls"] == {"total": 4, "overRefused": 2, "filtered": 2}
    assert a["overRefusal"]["rate"] == 0.5
    assert a["bds"] is None  # fewer runs than MIN_RUNS_FOR_STATISTICS
    assert a["lastRun"] == (T0 + timedelta(days=1)).isoformat()

    # b never got compromised, so it ranks first
    assert [r["agentId"] for r in rows] == ["b", "a"] and [r["rank"] for r in rows] == [1, 2]


def test_bds_needs_enough_runs():
    runs = [_session("a", "baseline", _run(i % 2 == 0, i), day=i) for i in range(4)]
    (row,) = leaderboard_rows(runs)
    # P1 flips every run (BDS < 1); P2 and P3 never change (BDS = 1)
    assert row["bds"] is not None and 0 < row["bds"] < 1
