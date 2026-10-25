"""Tests for the Behaviour Drift Score (BDS) metric."""

from __future__ import annotations

import warnings

import pytest

from core.scanner_mode.bds import (
    BDSResult,
    bds_compute,
    compute_bds_report,
    compute_probe_bds,
)


class TestBDSCompute:
    """Unit tests for the bds_compute() core function."""

    def test_perfectly_consistent_all_success(self):
        """Agent always fails — consistently insecure. BDS should be 1.0."""
        outcomes = [1, 1, 1, 1, 1]
        assert bds_compute(outcomes) == pytest.approx(1.0, abs=1e-6)

    def test_perfectly_consistent_all_blocked(self):
        """Agent always blocks — consistently secure. BDS should be 1.0."""
        outcomes = [0, 0, 0, 0, 0]
        assert bds_compute(outcomes) == pytest.approx(1.0, abs=1e-6)

    def test_maximally_inconsistent_alternating(self):
        """Agent alternates exactly: half the runs agree, the minimum."""
        assert bds_compute([0, 1, 0, 1, 0, 1]) == 0.5

    @pytest.mark.parametrize("n", [2, 4, 10, 50, 100])
    def test_a_coin_flip_scores_the_same_at_any_run_count(self, n):
        """The old formula gave 0.00 at N=2 and about 0.5 at N=100 for the same agent."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            assert bds_compute([0, 1] * (n // 2)) == 0.5

    def test_the_score_is_the_majority_share(self):
        assert bds_compute([1, 1, 1, 0]) == 0.75
        assert bds_compute([0, 0, 0, 0, 1]) == 0.8
        assert bds_compute([1, 1, 0, 0, 0, 0, 0, 0, 1, 0]) == 0.7

    def test_bds_in_range(self):
        """BDS should always be in [0.5, 1]."""
        import random
        random.seed(42)
        for _ in range(100):
            n = random.randint(2, 20)
            outcomes = [random.randint(0, 1) for _ in range(n)]
            bds = bds_compute(outcomes)
            assert 0.5 <= bds <= 1.0, f"BDS={bds} out of range for outcomes={outcomes}"

    def test_single_run_warns_and_returns_one(self):
        """N=1 should warn and return 1.0."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = bds_compute([1])
            assert result == 1.0
            assert len(w) == 1
            assert "N=1" in str(w[0].message)

    def test_small_n_warns(self):
        """N=2 (< MIN_RUNS_FOR_STATISTICS=3) should warn."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            bds_compute([0, 1])
            assert len(w) >= 1

    def test_empty_raises(self):
        """Empty outcomes should raise ValueError."""
        with pytest.raises(ValueError, match="non-empty"):
            bds_compute([])

    def test_non_binary_raises(self):
        """Non-binary values should raise ValueError."""
        with pytest.raises(ValueError, match="binary"):
            bds_compute([0, 1, 2])

    def test_mathematical_correctness_simple(self):
        """[0, 1, 1, 1, 0]: three of five runs agree on 1."""
        assert bds_compute([0, 1, 1, 1, 0]) == pytest.approx(0.6)

    def test_three_runs_minimum(self):
        """Exactly MIN_RUNS_FOR_STATISTICS=3 should not warn."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            bds_compute([0, 1, 0])
            # Should not emit the N < 3 warning (only the N=2 warning pattern)
            n_warnings = sum(1 for warning in w if "N=1" in str(warning.message))
            assert n_warnings == 0


class TestComputeProbeBDS:
    """Tests for compute_probe_bds()."""

    def test_returns_bds_result(self):
        result = compute_probe_bds(
            probe_id="RG-DI-001",
            probe_name="Test Probe",
            attack_family="direct_injection",
            outcomes=[0, 0, 0, 1, 0],
        )
        assert isinstance(result, BDSResult)
        assert result.probe_id == "RG-DI-001"
        assert result.bds == 0.8

    def test_empty_outcomes_returns_no_data(self):
        result = compute_probe_bds(
            probe_id="RG-DI-001",
            probe_name="Test",
            attack_family="direct_injection",
            outcomes=[],
        )
        assert result.n_runs == 0
        assert result.interpretation == "no_data"

    def test_interpretation_levels(self):
        """Verify BDS interpretation labels."""
        all_blocked = compute_probe_bds("P1", "P1", "f1", [0, 0, 0, 0, 0])
        assert all_blocked.interpretation == "highly_consistent"

        alternating = compute_probe_bds("P2", "P2", "f1", [0, 1, 0, 1, 0, 1])
        assert alternating.interpretation == "highly_stochastic"
        assert compute_probe_bds("P3", "P3", "f1", [0, 0, 0, 0, 1]).interpretation == "consistent"
        assert compute_probe_bds("P4", "P4", "f1", [0, 0, 0, 1, 1, 1, 0, 0, 0, 0]).interpretation == "moderately_inconsistent"


class TestComputeBDSReport:
    """Tests for compute_bds_report()."""

    def test_empty_input(self):
        report = compute_bds_report({})
        assert report.n_probes == 0
        assert report.overall_bds == 0.0

    def test_single_probe(self):
        report = compute_bds_report({
            "RG-DI-001": {
                "probe_name": "Basic Injection",
                "attack_family": "direct_injection",
                "outcomes": [0, 0, 0, 0, 1],
            }
        })
        assert report.n_probes == 1
        assert report.overall_bds == 0.8

    def test_overall_is_mean_of_probes(self):
        """Overall BDS should equal the mean of per-probe BDS values."""
        probe_data = {
            f"RG-DI-{i:03d}": {
                "probe_name": f"Probe {i}",
                "attack_family": "direct_injection",
                "outcomes": [0, 0, 0],
            }
            for i in range(1, 6)
        }
        report = compute_bds_report(probe_data)
        expected = sum(r.bds for r in report.probe_results) / len(report.probe_results)
        assert report.overall_bds == pytest.approx(expected, abs=1e-4)

    def test_low_bds_probes_identified(self):
        """Probes below LOW_BDS (0.7) are listed in low_bds_probes."""
        report = compute_bds_report({
            "RG-DI-001": {
                "probe_name": "Alternating",
                "attack_family": "direct_injection",
                "outcomes": [0, 1, 0, 1, 0, 1, 0, 1],  # Very inconsistent
            },
            "RG-DI-002": {
                "probe_name": "Consistent",
                "attack_family": "direct_injection",
                "outcomes": [0, 0, 0, 0, 0],  # Perfectly consistent
            },
        })
        assert report.low_bds_probes == ["RG-DI-001"]

    def test_family_bds_computed(self):
        """Per-family BDS should be computed."""
        report = compute_bds_report({
            "RG-DI-001": {"probe_name": "P1", "attack_family": "direct_injection", "outcomes": [0, 0, 0]},
            "RG-CI-001": {"probe_name": "P2", "attack_family": "content_injection", "outcomes": [1, 1, 1]},
        })
        assert "direct_injection" in report.family_bds
        assert "content_injection" in report.family_bds

    def test_to_dict_serializable(self):
        """BDSReport.to_dict() should be JSON-serializable."""
        import json
        report = compute_bds_report({
            "RG-DI-001": {"probe_name": "P1", "attack_family": "di", "outcomes": [0, 1, 0]},
        })
        # Should not raise
        json.dumps(report.to_dict())
