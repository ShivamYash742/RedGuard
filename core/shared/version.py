"""
RedGuard Benchmark Versioning
==============================

Canonical version constants for the RedGuard benchmark.

Versioning follows Semantic Versioning 2.0.0 (semver.org):
  MAJOR.MINOR.PATCH

  MAJOR: Breaking changes to benchmark structure, probe IDs, or metric definitions.
  MINOR: New probes, new families, or new metrics (backwards compatible).
  PATCH: Bug fixes, documentation corrections, minor improvements.

Researchers should pin BENCHMARK_VERSION when citing results:
  "We evaluate on RedGuard Benchmark v1.0.0"

Keeping DATASET_VERSION and PROBE_SCHEMA_VERSION separate from BENCHMARK_VERSION
allows the dataset content to evolve independently of the evaluation infrastructure.
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# Core Version Strings
# ─────────────────────────────────────────────────────────────────────────────

#: Overall benchmark version. Bump MAJOR for any breaking change to probe IDs,
#: metric definitions, or evaluation methodology.
BENCHMARK_VERSION: str = "5.0.0"

#: Earlier benchmark versions whose stored results are still shown, apart from
#: the current ones and labelled "measured before the audit fixes". Their scoring,
#: prompts and tools differ, so they are never pooled with BENCHMARK_VERSION runs.
PRE_AUDIT_BENCHMARK_VERSIONS: tuple = ("4.0.0",)

#: Version of the benchmark dataset (JSON files in core/scanner_mode/datasets/).
#: Bump when probes are added, removed, or their prompts change materially.
DATASET_VERSION: str = "5.0.0"

#: Version of the probe JSON schema (core/scanner_mode/datasets/schema.json).
#: Bump when new required fields are added to dataset entries.
PROBE_SCHEMA_VERSION: str = "5.0.0"

#: Minimum number of runs per probe required for statistical metrics (BDS, CI).
MIN_RUNS_FOR_STATISTICS: int = 3


# ─────────────────────────────────────────────────────────────────────────────
# Mode B (Multi-Agent Lab) Versions
# ─────────────────────────────────────────────────────────────────────────────
#
# Mode B answers a different question from different evidence, so it versions
# separately (MULTI_AGENT_LAB_PLAN.md §17). Every experiment row and evidence
# bundle embeds all six, so a published verdict can be traced to the exact
# definitions that produced it. Bump the one whose meaning changed:
#
#   LAB_SCHEMA_VERSION  trace event schema (§8) or the lab_* Prisma models
#   CASE_SCHEMA_VERSION core/lab_mode/cases/case_schema.json
#   CEE_VERSION         CEE semantics (resource lookup, snapshot, planting)
#   TOPOLOGY_VERSION    topology definitions or authorization tables
#   EVALUATOR_VERSION   verdict definitions or the predicate DSL
#   METRIC_VERSION      any metric formula in §10
#
# A METRIC_VERSION bump means previously published numbers are not comparable
# to new ones — that is the point of keeping it separate from the others.

#: Version of the Mode B trace/event schema and its persistence models.
LAB_SCHEMA_VERSION: str = "1.1.0"

#: Version of the Mode B security test case schema.
CASE_SCHEMA_VERSION: str = "2.0.0"

#: Version of the Controlled Execution Environment semantics.
CEE_VERSION: str = "2.0.0"

#: Version of the topology definitions and authorization tables.
TOPOLOGY_VERSION: str = "1.1.0"

#: Version of the verdict definitions and predicate DSL.
EVALUATOR_VERSION: str = "2.0.0"

#: Version of the Mode B metric formulas.
METRIC_VERSION: str = "2.0.0"

#: Human-readable release name.
RELEASE_NAME: str = "RedGuard v5.0.0"

#: Citation key for the benchmark paper (placeholder until published).
CITATION_KEY: str = "redguard2024"


# ─────────────────────────────────────────────────────────────────────────────
# Compatibility
# ─────────────────────────────────────────────────────────────────────────────

def get_version_info() -> dict:
    """Return all version information as a dictionary.

    Suitable for embedding in reports and reproducibility artifacts.

    Returns:
        dict with benchmark_version, dataset_version, probe_schema_version,
        min_runs_for_statistics, and release_name.
    """
    return {
        "benchmark_version": BENCHMARK_VERSION,
        "dataset_version": DATASET_VERSION,
        "probe_schema_version": PROBE_SCHEMA_VERSION,
        "min_runs_for_statistics": MIN_RUNS_FOR_STATISTICS,
        "release_name": RELEASE_NAME,
        "citation_key": CITATION_KEY,
    }


#: The Lab definitions behind results measured before the audit fixes (the Oct 2026 sweeps). Their
#: verdicts used substring predicates, pooled controls and unreachable cases, and counted unexposed
#: runs as resisted, so they are shown labelled and never pooled with results from the current ones.
PRE_AUDIT_LAB_VERSIONS: dict = {"evaluator_version": "1.2.0", "metric_version": "1.2.0"}

#: The stored versions that decide whether two Lab experiments' numbers mean the same thing.
LAB_DEFINITION_KEYS = ("evaluator_version", "metric_version", "case_schema_version", "cee_version")

PRE_AUDIT_LABEL = "Measured before the audit fixes"


def lab_vintage(stored_versions: dict | None) -> str:
    """"current" if an experiment's stored definitions are the ones in this code, "pre_audit" if
    they are the 1.2.0 ones, else "other" (a different or unrecorded set)."""
    stored = stored_versions or {}
    current = get_lab_version_info()
    if all(stored.get(k) == current[k] for k in LAB_DEFINITION_KEYS):
        return "current"
    if all(stored.get(k) == v for k, v in PRE_AUDIT_LAB_VERSIONS.items()):
        return "pre_audit"
    return "other"


def get_lab_version_info() -> dict:
    """Return the Mode B version constants.

    Kept separate from `get_version_info()` so Mode A consumers
    (`reproducibility.py`, the datasets page) see no new keys.
    """
    return {
        "benchmark_version": BENCHMARK_VERSION,
        "lab_schema_version": LAB_SCHEMA_VERSION,
        "case_schema_version": CASE_SCHEMA_VERSION,
        "cee_version": CEE_VERSION,
        "topology_version": TOPOLOGY_VERSION,
        "evaluator_version": EVALUATOR_VERSION,
        "metric_version": METRIC_VERSION,
    }


def parse_version(version_string: str) -> tuple[int, int, int]:
    """Parse a semver string into a (major, minor, patch) tuple.

    Args:
        version_string: A semver string like "1.0.0".

    Returns:
        Tuple of (major, minor, patch) integers.

    Raises:
        ValueError: If the version string is not a valid semver.
    """
    parts = version_string.split(".")
    if len(parts) != 3:
        raise ValueError(
            f"Invalid version string '{version_string}'. Expected MAJOR.MINOR.PATCH"
        )
    try:
        return int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        raise ValueError(
            f"Version string '{version_string}' contains non-integer parts"
        )


def is_compatible(required: str, current: str) -> bool:
    """Check if current version satisfies required version (same major, current >= required).

    Args:
        required: Required version string.
        current: Current version string.

    Returns:
        True if compatible.
    """
    req = parse_version(required)
    cur = parse_version(current)
    return cur[0] == req[0] and cur >= req


# ─────────────────────────────────────────────────────────────────────────────
# Module-level convenience
# ─────────────────────────────────────────────────────────────────────────────

__version__ = BENCHMARK_VERSION
__all__ = [
    "BENCHMARK_VERSION",
    "DATASET_VERSION",
    "PROBE_SCHEMA_VERSION",
    "MIN_RUNS_FOR_STATISTICS",
    "RELEASE_NAME",
    "CITATION_KEY",
    "LAB_SCHEMA_VERSION",
    "CASE_SCHEMA_VERSION",
    "CEE_VERSION",
    "TOPOLOGY_VERSION",
    "EVALUATOR_VERSION",
    "METRIC_VERSION",
    "PRE_AUDIT_LAB_VERSIONS",
    "PRE_AUDIT_LABEL",
    "lab_vintage",
    "get_version_info",
    "get_lab_version_info",
    "parse_version",
    "is_compatible",
]
