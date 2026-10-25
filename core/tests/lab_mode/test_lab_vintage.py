"""Lab results measured before the audit fixes (evaluator and metrics 1.2.0) stay visible, labelled,
and are never pooled or compared with results from the current definitions."""

from __future__ import annotations

import pytest

from core.lab_mode.analysis import comparability_problems
from core.shared.version import (
    EVALUATOR_VERSION, METRIC_VERSION, PRE_AUDIT_LABEL, PRE_AUDIT_LAB_VERSIONS, get_lab_version_info, lab_vintage,
)

CURRENT = get_lab_version_info()
OLD = {**CURRENT, **PRE_AUDIT_LAB_VERSIONS, "case_schema_version": "1.1.0", "cee_version": "1.1.0"}


def test_the_audit_moved_the_definitions():
    assert (EVALUATOR_VERSION, METRIC_VERSION) == ("2.0.0", "2.0.0")
    assert PRE_AUDIT_LAB_VERSIONS == {"evaluator_version": "1.2.0", "metric_version": "1.2.0"}


@pytest.mark.parametrize("stored, expected", [
    (CURRENT, "current"),
    (OLD, "pre_audit"),
    ({**OLD, "cee_version": "9.9.9"}, "pre_audit"),      # the 1.2.0 evaluator and metrics decide the label
    ({**CURRENT, "metric_version": "1.2.0"}, "other"),   # a mix of old and new definitions
    ({}, "other"),
    (None, "other"),
])
def test_vintage(stored, expected):
    assert lab_vintage(stored) == expected


class TestNeverPooled:
    configs = {"a": {"model": {}, "repetitions": 1}, "b": {"model": {}, "repetitions": 1}}

    def test_experiments_under_different_definitions_cannot_be_compared(self):
        errors, _ = comparability_problems(self.configs, {"a": OLD, "b": CURRENT})
        assert any("metric_version differs" in e and PRE_AUDIT_LABEL.lower() in e for e in errors)
        assert any("evaluator_version differs" in e for e in errors)

    def test_experiments_under_the_same_definitions_can(self):
        assert comparability_problems(self.configs, {"a": CURRENT, "b": CURRENT})[0] == []
        assert comparability_problems(self.configs, {"a": OLD, "b": OLD})[0] == []

    def test_versions_are_optional_for_callers_that_have_none(self):
        assert comparability_problems(self.configs)[0] == []
