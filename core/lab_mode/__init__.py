"""
Lab mode (formerly Mode B)
==========================

Multi-agent security laboratory: a deterministic Controlled Execution
Environment, a topology-aware message bus, a tool gateway, an append-only
trace, a harness-owned agent runner, a deterministic evaluator, metrics and
reports. Never imports `core.scanner_mode`. Design sections (§N) cited in
this package refer to MULTI_AGENT_LAB_PLAN.md (in git history).

Public names are resolved lazily (PEP 562). Importing them eagerly here would
make `python -m core.lab_mode.cases` and `python -m core.lab_mode.smoke` — both
documented entry points — import their module twice and warn about it, since
the package `__init__` would already have loaded it.
"""

from typing import Any

_EXPORTS = {
    "ATTACK": "runner",
    "CLEAN": "runner",
    "RunConfig": "runner",
    "run_case": "runner",
    "run_pair": "runner",
    "run_repetitions": "runner",
    "evaluate": "evaluator",
    "fixture_factory": "cases",
    "load_all_cases": "cases",
    "load_case": "cases",
    "load_fixture": "cases",
    "validate_all": "cases",
    "reproducibility_stamp": "repro",
}


def __getattr__(name: str) -> Any:
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    return getattr(import_module(f".{module}", __name__), name)


def __dir__() -> list:
    return sorted(_EXPORTS)


__all__ = [
    "ATTACK",
    "CLEAN",
    "RunConfig",
    "evaluate",
    "fixture_factory",
    "load_all_cases",
    "load_case",
    "load_fixture",
    "reproducibility_stamp",
    "run_case",
    "run_pair",
    "run_repetitions",
    "validate_all",
]
