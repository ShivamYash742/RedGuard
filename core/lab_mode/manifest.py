"""
What the Lab's numbers were measured with.

Hashes the code that decides what a run is and what a verdict says (runner, environment, tools, topology, trace,
evaluator, metrics, case schema, fixture) and the dev and test case sets separately. `frozen_manifest.json` holds
the expected values and a test fails when they differ, so editing an evaluator rule, a predicate or a held-out
case after results exist cannot happen silently. When a change is deliberate, rewrite the file and bump the
version that matches it (EVALUATOR_VERSION / METRIC_VERSION / CASE_SCHEMA_VERSION): numbers stop being comparable.

    python -m core.lab_mode.manifest --write
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

from ..shared.manifest import digest, probes_sha256, tree_hashes
from .cases import load_all_cases

LAB_DIR = Path(__file__).resolve().parent
FROZEN_FILE = LAB_DIR / "frozen_manifest.json"
FROZEN_PATHS = ["runner.py", "cee.py", "tools.py", "topology.py", "trace.py", "evidence.py", "evaluator.py", "metrics.py",
                "model_client.py", "cases/case_schema.json", "fixtures"]


def current_manifest() -> Dict[str, Any]:
    files = tree_hashes(LAB_DIR, [LAB_DIR / p for p in FROZEN_PATHS])
    cases = load_all_cases(validate=False)
    dev = probes_sha256(c for c in cases if c.get("split", "dev") == "dev")
    test = probes_sha256(c for c in cases if c.get("split") == "test")
    return {"files": files, "devCases": dev, "testCases": test, "digest": digest({**files, "devCases": dev, "testCases": test})}


def differences() -> list:
    """Names whose hash differs from the frozen value (empty = nothing changed)."""
    now, then = current_manifest(), json.loads(FROZEN_FILE.read_text(encoding="utf-8"))
    changed = sorted(n for n in set(now["files"]) | set(then["files"]) if now["files"].get(n) != then["files"].get(n))
    return changed + [k for k in ("devCases", "testCases") if now[k] != then[k]]


if __name__ == "__main__":
    if "--write" in sys.argv:
        FROZEN_FILE.write_text(json.dumps(current_manifest(), indent=2) + "\n", encoding="utf-8")
        print(f"wrote {FROZEN_FILE.name}")
    else:
        print("\n".join(differences()) or "frozen manifest matches")
