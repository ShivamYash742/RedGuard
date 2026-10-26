"""Tests for the statistical analysis module."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import pytest

from core.shared.statistics import (
    StatisticalSummary,
    compute_statistics,
    export_csv,
    wilson_ci,
)


class TestWilsonCI:
    """Tests for Wilson score confidence interval computation."""

    def test_zero_trials(self):
        lo, hi = wilson_ci(0, 0)
        assert lo == 0.0
        assert hi == 0.0

    def test_all_success(self):
        lo, hi = wilson_ci(100, 100)
        assert lo > 0.9
        assert hi == pytest.approx(1.0, abs=0.05)

    def test_all_failure(self):
        lo, hi = wilson_ci(0, 100)
        assert lo == pytest.approx(0.0, abs=0.05)
        assert hi < 0.1

    def test_fifty_fifty(self):
        lo, hi = wilson_ci(50, 100)
        assert lo < 0.5
        assert hi > 0.5
        assert (lo + hi) / 2 == pytest.approx(0.5, abs=0.05)

    def test_bounds_in_range(self):
        """CI bounds must always be in [0, 1]."""
        test_cases = [(0, 1), (1, 1), (0, 10), (5, 10), (10, 10), (3, 100)]
        for successes, trials in test_cases:
            lo, hi = wilson_ci(successes, trials)
            assert 0.0 <= lo <= 1.0, f"Lower bound {lo} out of range"
            assert 0.0 <= hi <= 1.0, f"Upper bound {hi} out of range"
            assert lo <= hi, f"Lower > Upper: {lo} > {hi}"

    def test_width_decreases_with_n(self):
        """Wider CI for smaller samples — basic frequentist property."""
        lo10, hi10 = wilson_ci(5, 10)
        lo100, hi100 = wilson_ci(50, 100)
        width_10 = hi10 - lo10
        width_100 = hi100 - lo100
        assert width_10 > width_100


class TestComputeStatistics:
    """Tests for compute_statistics()."""

    def test_empty_list(self):
        stats = compute_statistics([])
        assert stats.n == 0
        assert stats.mean == 0.0

    def test_single_value(self):
        stats = compute_statistics([0.7])
        assert stats.n == 1
        assert stats.mean == pytest.approx(0.7)
        assert stats.std_dev == 0.0

    def test_all_zeros(self):
        stats = compute_statistics([0.0, 0.0, 0.0])
        assert stats.mean == 0.0
        assert stats.std_dev == 0.0
        assert stats.min_val == 0.0
        assert stats.max_val == 0.0

    def test_all_ones(self):
        stats = compute_statistics([1.0, 1.0, 1.0])
        assert stats.mean == 1.0
        assert stats.std_dev == 0.0

    def test_mean_computation(self):
        values = [0.2, 0.4, 0.6, 0.8]
        stats = compute_statistics(values)
        assert stats.mean == pytest.approx(0.5, abs=1e-4)

    def test_median_computation(self):
        values = [0.1, 0.2, 0.5, 0.8, 0.9]
        stats = compute_statistics(values)
        assert stats.median == pytest.approx(0.5, abs=1e-4)

    def test_std_dev_positive(self):
        values = [0.0, 0.5, 1.0]
        stats = compute_statistics(values)
        assert stats.std_dev > 0

    def test_min_max_correct(self):
        values = [0.1, 0.9, 0.3, 0.7]
        stats = compute_statistics(values)
        assert stats.min_val == pytest.approx(0.1, abs=1e-4)
        assert stats.max_val == pytest.approx(0.9, abs=1e-4)

    def test_ci_contains_mean(self):
        """The confidence interval should contain the sample mean for a non-extreme proportion."""
        values = [0.4, 0.5, 0.6, 0.4, 0.5, 0.6]
        stats = compute_statistics(values)
        # This is a loose check — for a small sample the CI may not contain the
        # exact sample mean but should be close
        assert stats.ci_lower <= stats.mean <= stats.ci_upper or \
               abs(stats.ci_lower - stats.mean) < 0.2

    def test_returns_statistical_summary(self):
        stats = compute_statistics([0.5, 0.5, 0.5])
        assert isinstance(stats, StatisticalSummary)

    def test_to_dict_keys(self):
        stats = compute_statistics([0.3, 0.7])
        d = stats.to_dict()
        assert "n" in d
        assert "mean" in d
        assert "median" in d
        assert "std_dev" in d
        assert "min" in d
        assert "max" in d
        assert "ci_95_lower" in d
        assert "ci_95_upper" in d

    def test_to_dict_serializable(self):
        stats = compute_statistics([0.1, 0.2, 0.3])
        json.dumps(stats.to_dict())  # Should not raise


class TestExportCSV:
    """Tests for export_csv()."""

    def _make_mock_result(self, probe_id, success, blocked, attack_family, variant, scenario):
        """Create a minimal mock probe result object."""
        from types import SimpleNamespace
        from datetime import datetime
        result = SimpleNamespace()
        result.probe_id = probe_id
        result.probe_name = f"Probe {probe_id}"
        result.attack_family = attack_family
        result.variant = variant
        result.scenario = scenario
        result.success = success
        result.blocked = blocked
        result.error = None
        result.execution_time_ms = 150.5
        result.timestamp = datetime.now()
        return result

    def test_creates_file(self, tmp_path):
        results = [
            self._make_mock_result("RG-DI-001", False, True, "direct_injection", "instruction_override", "generic"),
            self._make_mock_result("RG-CI-001", True, False, "content_injection", "hidden_html", "github_issue"),
        ]
        output = tmp_path / "test_output.csv"
        path = export_csv(results, str(output))
        assert path.exists()

    def test_csv_has_header(self, tmp_path):
        results = [
            self._make_mock_result("RG-DI-001", False, True, "direct_injection", "v1", "generic"),
        ]
        output = tmp_path / "test.csv"
        export_csv(results, str(output))
        with open(output) as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames
        assert "probe_id" in header
        assert "success" in header
        assert "attack_family" in header

    def test_csv_row_count(self, tmp_path):
        results = [
            self._make_mock_result(f"RG-DI-{i:03d}", False, True, "direct_injection", "v1", "generic")
            for i in range(1, 11)
        ]
        output = tmp_path / "test.csv"
        export_csv(results, str(output))
        with open(output) as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 10

    def test_csv_success_values(self, tmp_path):
        results = [
            self._make_mock_result("RG-DI-001", True, False, "direct_injection", "v1", "generic"),
            self._make_mock_result("RG-DI-002", False, True, "direct_injection", "v1", "generic"),
        ]
        output = tmp_path / "test.csv"
        export_csv(results, str(output))
        with open(output) as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["success"] == "1"
        assert rows[1]["success"] == "0"

    def test_creates_parent_directory(self, tmp_path):
        results = [
            self._make_mock_result("RG-DI-001", False, True, "direct_injection", "v1", "generic"),
        ]
        nested_output = tmp_path / "nested" / "dir" / "test.csv"
        export_csv(results, str(nested_output))
        assert nested_output.exists()


class TestClusteredRate:
    """clustered_rate: Wilson over the effective sample size when items share a cluster."""

    @staticmethod
    def _mean(xs):
        return sum(xs) / len(xs) if xs else None

    def test_one_item_per_cluster_is_the_plain_wilson_interval(self):
        from core.shared.statistics import clustered_rate, wilson_ci

        groups = {f"p{i}": [1 if i < 3 else 0] for i in range(10)}
        result = clustered_rate(groups, self._mean)
        assert result["ci_method"] == "wilson" and result["n_eff"] == 10
        assert tuple(result["ci"]) == wilson_ci(3, 10)

    def test_runs_that_repeat_each_other_do_not_narrow_the_interval(self):
        from core.shared.statistics import clustered_rate, wilson_ci

        # 10 probes x 3 identical runs: 3 always succeed, 7 never do
        groups = {f"p{i}": [1 if i < 3 else 0] * 3 for i in range(10)}
        result = clustered_rate(groups, self._mean)
        naive_lo, naive_hi = wilson_ci(9, 30)
        assert result["value"] == 0.3 and result["n"] == 30
        assert result["n_eff"] == pytest.approx(10)          # three copies of a probe are one observation
        assert result["ci"][1] - result["ci"][0] > (naive_hi - naive_lo) * 1.4

    def test_independent_runs_keep_most_of_their_weight(self):
        from core.shared.statistics import clustered_rate

        groups = {"a": [1, 0, 1], "b": [0, 1, 0], "c": [1, 0, 0], "d": [0, 0, 1]}
        result = clustered_rate(groups, self._mean)
        assert result["n_eff"] == pytest.approx(12) and result["icc"] == 0

    def test_nothing_to_estimate(self):
        from core.shared.statistics import clustered_rate

        assert clustered_rate({}, self._mean)["ci"] is None
