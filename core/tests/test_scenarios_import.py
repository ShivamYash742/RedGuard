"""Every scenario module must import on the interpreters the README promises.

The twelve scenario files once annotated with `Dict` / `Any` without importing
them. Python 3.14 evaluates annotations lazily, so the machine they were
written on never noticed; on 3.10–3.13 the class body raised `NameError` at
import time — and because `core.benchmark` imports the scenarios, so did every
Mode B module that needs `wilson_ci`. The whole suite failed to collect.
"""

import importlib
import pkgutil

import core.scenarios


def test_every_scenario_module_imports():
    for module in pkgutil.iter_modules(core.scenarios.__path__):
        importlib.import_module(f"core.scenarios.{module.name}")


def test_lab_metrics_import_chain_resolves():
    importlib.import_module("core.lab.metrics")
