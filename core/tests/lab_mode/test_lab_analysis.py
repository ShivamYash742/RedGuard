"""Tests for core/lab_mode/analysis.py — arm summaries and the cross-arm
comparisons that are §11's actual research output (EXP-4, EXP-6).

Verdicts are built directly rather than run through `evaluate()`: what is
under test is the aggregation and the honesty of what it reports, not the
evaluator.
"""

from __future__ import annotations

import pytest

from core.lab_mode.analysis import (
    ARMS,
    STANDARD_COMPARISONS,
    arm_summary,
    compare_arms,
    compare_standard,
    compromise_by_agent,
)
from core.lab_mode.evaluator import (
    AgentImpactLevel,
    AgentImpactResult,
    Containment,
    ObjectiveAchievement,
    ObjectiveResult,
    SystemOutcome,
    Verdict,
)
from core.lab_mode.metrics import RunOutcome, rate_ci


def _case(case_id="RGM-001", entry="A", eligible=("B", "C")):
    return {
        "id": case_id,
        "attack": {"injection_point": entry},
        "eligibility": {
            "eligible_downstream_agents": list(eligible),
            "expected_path": ["A", "B", "C"],
        },
    }


def _verdict(impact, objective="NOT_REACHED", system_outcome="TASK_COMPLETED_WITH_DEVIATION",
             containment_status="NOT_CONTAINED", containment_agent=None, mechanism=None):
    return Verdict(
        agent_impact={a: AgentImpactResult(AgentImpactLevel(v)) for a, v in impact.items()},
        objective=ObjectiveResult(ObjectiveAchievement(objective)),
        containment=Containment(status=containment_status, agent=containment_agent, mechanism=mechanism),
        system_outcome=SystemOutcome(system_outcome),
    )


def _compromised(n, case_id="RGM-001"):
    return [
        RunOutcome(_case(case_id), _verdict(
            {"A": "COMPROMISED", "B": "COMPROMISED", "C": "COMPROMISED"}, objective="REACHED"))
        for _ in range(n)
    ]


def _clean(n, case_id="RGM-001"):
    return [
        RunOutcome(_case(case_id), _verdict(
            {"A": "NOT_INFLUENCED", "B": "NOT_INFLUENCED", "C": "NOT_INFLUENCED"},
            containment_status="CONTAINED", containment_agent="B", mechanism="agent_non_compliance"))
        for _ in range(n)
    ]


class TestArmSummary:
    def test_reports_every_aggregate(self):
        summary = arm_summary(_compromised(5))
        for key in ("icr", "asr", "cpr", "depth", "coverage", "containment_rate",
                    "objective_histogram", "per_case", "macro"):
            assert key in summary

    def test_invalid_runs_are_excluded_and_counted(self):
        """§21.8: a failed clean run makes its pair uninterpretable. Dropping
        it silently would deflate every rate computed from the denominator,
        so the exclusion has to be visible."""
        outcomes = _compromised(3) + [
            RunOutcome(_case(), _verdict({"A": "COMPROMISED"}, system_outcome="RUN_INVALID"))
        ]
        summary = arm_summary(outcomes)

        assert summary["n_runs"] == 4
        assert summary["n_valid"] == 3
        assert summary["n_invalid"] == 1
        assert summary["icr"]["value"] == 1.0  # not 3/4

    def test_rates_carry_wilson_intervals(self):
        summary = arm_summary(_compromised(5))
        assert summary["icr"]["value"] == 1.0
        low, high = summary["icr"]["ci"]
        # 5/5 is not proof of 100% — the interval has to admit that.
        assert low < 1.0 and high == pytest.approx(1.0)

    def test_cpr_is_na_when_nothing_was_compromised(self):
        summary = arm_summary(_clean(5))
        assert summary["cpr"] == "n/a"
        assert summary["cpr_denominator_size"] == 0

    def test_objective_histogram_covers_every_level(self):
        histogram = arm_summary(_compromised(2) + _clean(3))["objective_histogram"]
        assert histogram == {
            "NOT_REACHED": 3, "PARTIALLY_REACHED": 0, "REACHED": 2, "CRITICAL_REACHED": 0,
        }

    def test_macro_average_weights_cases_equally(self):
        """A case that happened to run more often must not dominate the
        headline — that is the whole point of the macro figure."""
        outcomes = _compromised(9, "RGM-001") + _clean(1, "RGM-002")
        summary = arm_summary(outcomes)
        assert summary["icr"]["value"] == pytest.approx(0.9)   # micro, run-weighted
        assert summary["macro"]["icr"] == pytest.approx(0.5)   # macro, case-weighted

    def test_empty_arm_does_not_crash(self):
        summary = arm_summary([])
        assert summary["n_valid"] == 0
        assert summary["icr"]["value"] is None
        assert summary["cpr"] == "n/a"


class TestCompareArms:
    def test_difference_is_variant_minus_baseline(self):
        result = compare_arms("attack", _compromised(5), "attack_validated", _clean(5))
        asr = result["metrics"]["asr"]
        assert asr["baseline"]["value"] == 1.0
        assert asr["variant"]["value"] == 0.0
        # Negative means the variant suppressed attacks.
        assert asr["difference"] == pytest.approx(-1.0)

    def test_separated_intervals_are_flagged_as_such(self):
        # six cases that all succeed against six that never do: separated even after clustering
        many = [f"RGM-00{i}" for i in range(1, 7)]
        result = compare_arms("attack", [o for c in many for o in _compromised(5, c)],
                              "attack_validated", [o for c in many for o in _clean(5, c)])
        assert result["metrics"]["asr"]["overlapping"] is False

    def test_overlapping_intervals_are_flagged(self):
        """The case the caveat exists for: a visible delta that the data
        cannot distinguish from repetition noise."""
        result = compare_arms("attack", _compromised(2) + _clean(1),
                              "attack_validated", _compromised(1) + _clean(2))
        assert result["metrics"]["asr"]["overlapping"] is True

    def test_cpr_comparison_marks_itself_incomparable_when_either_side_is_na(self):
        """"n/a" minus a number is undefined, not zero — it must never
        render as "no change" (§10.3)."""
        result = compare_arms("attack", _clean(5), "attack_permissive_tools", _compromised(5))
        cpr = result["metrics"]["cpr"]
        assert cpr["baseline"] == "n/a"
        assert cpr["comparable"] is False

    def test_carries_the_no_significance_test_caveat(self):
        result = compare_arms("attack", _compromised(5), "attack_validated", _clean(5))
        assert "significance test" in result["caveat"]
        assert "§21.6" in result["caveat"]

    def test_both_full_summaries_are_embedded(self):
        result = compare_arms("attack", _compromised(5), "attack_validated", _clean(5))
        assert result["baseline_summary"]["n_valid"] == 5
        assert result["variant_summary"]["n_valid"] == 5


class TestCompareStandard:
    def test_runs_the_comparisons_whose_arms_are_present(self):
        results = compare_standard({
            "attack": _compromised(5),
            "attack_permissive_tools": _compromised(5),
        })
        assert "EXP-4" in results
        # attack_validated was never run — that is not a null result.
        assert "EXP-6" not in results

    def test_missing_arms_are_skipped_not_reported_as_null(self):
        assert compare_standard({"attack": _compromised(3)}) == {}

    def test_standard_comparisons_reference_real_arms(self):
        """A comparison naming an arm that does not exist would silently
        never run — it would look like "no effect found" rather than "never
        measured"."""
        for _, baseline, variant in STANDARD_COMPARISONS:
            assert baseline in ARMS, baseline
            assert variant in ARMS, variant


class TestCompromiseByAgent:
    def test_counts_impact_levels_per_agent(self):
        table = compromise_by_agent(_compromised(2) + _clean(3))
        assert table["A"]["COMPROMISED"] == 2
        assert table["A"]["NOT_INFLUENCED"] == 3
        assert table["C"]["COMPROMISED"] == 2

    def test_invalid_runs_are_excluded(self):
        outcomes = _compromised(2) + [
            RunOutcome(_case(), _verdict({"A": "COMPROMISED"}, system_outcome="RUN_INVALID"))
        ]
        assert compromise_by_agent(outcomes)["A"]["COMPROMISED"] == 2


class TestClusteredIntervals:
    """Runs of one case share its task, artifact and wording, so they succeed
    or fail together. Pooling them as independent trials gave intervals that
    were too narrow."""

    def test_one_case_counts_as_one_independent_observation(self):
        """L6: five repetitions of one case are not five trials. The old fallback gave the plain
        Wilson interval over the repetitions, which no single case can justify."""
        icr = arm_summary(_compromised(3) + _clean(2))["icr"]
        assert icr["ci_method"] == "wilson_single_cluster" and icr["n_eff"] == 1.0
        assert icr["ci"] == pytest.approx(list(rate_ci(0.6, 1)))
        assert icr["ci"][1] - icr["ci"][0] > rate_ci(3, 5)[1] - rate_ci(3, 5)[0]

    def test_cases_that_move_together_widen_the_interval(self):
        icr = arm_summary(_compromised(5, "RGM-001") + _clean(5, "RGM-002"))["icr"]
        naive_low, naive_high = rate_ci(5, 10)
        assert icr["ci_method"] == "wilson_design_effect"
        assert icr["n_eff"] == pytest.approx(2.0)   # two cases, each all-or-nothing
        assert icr["ci"][1] - icr["ci"][0] > naive_high - naive_low

    def test_uncorrelated_cases_keep_their_full_sample(self):
        outcomes = (_compromised(3, "RGM-001") + _clean(2, "RGM-001")
                    + _compromised(2, "RGM-002") + _clean(3, "RGM-002"))
        icr = arm_summary(outcomes)["icr"]
        assert icr["icc"] == 0.0
        assert icr["n_eff"] == pytest.approx(10.0)

    def test_uniform_outcomes_count_each_case_once(self):
        """No variation to estimate the correlation from: the conservative
        reading, since uniform outcomes are what correlated runs produce."""
        outcomes = _compromised(5, "RGM-001") + _compromised(5, "RGM-002") + _compromised(5, "RGM-003")
        icr = arm_summary(outcomes)["icr"]
        assert icr["value"] == 1.0
        assert icr["n_eff"] == pytest.approx(3.0)
        assert icr["ci"][0] == pytest.approx(rate_ci(3, 3)[0])


SIX_CASES = [f"RGM-00{i}" for i in range(1, 7)]


class TestPairedComparison:
    def test_arms_are_compared_case_by_case(self):
        baseline = [o for c in SIX_CASES for o in _compromised(3, c)]
        variant = [o for c in SIX_CASES for o in _clean(3, c)]
        paired = compare_arms("attack", baseline, "attack_capability_gateway", variant)["metrics"]["asr"]["paired"]
        assert paired["n_cases"] == 6
        assert paired["mean_difference"] == pytest.approx(-1.0)
        assert paired["cases_lower"] == 6 and paired["cases_higher"] == 0
        assert paired["excludes_zero"] is True

    def test_too_few_shared_cases_give_counts_but_no_interval(self):
        baseline = [o for c in SIX_CASES[:3] for o in _compromised(3, c)]
        variant = [o for c in SIX_CASES[:3] for o in _clean(3, c)]
        paired = compare_arms("attack", baseline, "attack_validated", variant)["metrics"]["asr"]["paired"]
        assert paired["cases_lower"] == 3
        assert paired["ci"] is None and paired["excludes_zero"] is None

    def test_only_cases_both_arms_ran_are_paired(self):
        baseline = _compromised(3, "RGM-001") + _compromised(3, "RGM-002")
        variant = _clean(3, "RGM-002") + _clean(3, "RGM-003")
        paired = compare_arms("attack", baseline, "attack_validated", variant)["metrics"]["asr"]["paired"]
        assert paired["n_cases"] == 1
