"""
What the Scanner's numbers were measured with.

`current_manifest()` hashes the files that were frozen before the held-out (test) probes were written: the
filter, the prompts, the tools, the scorer and the sandbox, plus the content of the dev and test probe sets
separately. `frozen_manifest.json` holds the expected values. A test fails when they differ, so tuning a
pattern, prompt or indicator against the test split (or editing a test probe after a run) cannot happen
silently. When a change is deliberate, rewrite the file and bump BENCHMARK_VERSION, since scores stop being
comparable:

    cd backend && python -m scanner_mode.manifest --write
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

from scanner_mode.scanner import builtin_probes  # first: it puts the repo root (core/) on sys.path

from core.shared.manifest import digest, probes_sha256, tree_hashes

BACKEND = Path(__file__).resolve().parent.parent
FROZEN_FILE = Path(__file__).with_name("frozen_manifest.json")

#: Everything that decides how a probe is filtered, prompted, run and scored. Not the datasets: those are
#: hashed by content below so dev and test can be told apart.
FROZEN_PATHS = [
    "scanner_mode/policy.yaml", "scanner_mode/inspector.py", "scanner_mode/scanner.py",
    "scanner_mode/agents/system_prompts.json", "scanner_mode/agents/_prompt_loader.py",
    "scanner_mode/agents/_tools.py", "scanner_mode/agents/_scaffold.py",
    "scanner_mode/agents/web_search_fixtures.json", "scanner_mode/agents/sandbox",
]


def current_manifest() -> Dict[str, Any]:
    files = tree_hashes(BACKEND, [BACKEND / p for p in FROZEN_PATHS])
    probes = [p for group in builtin_probes().values() for p in group]
    dev = probes_sha256(p for p in probes if p["split"] == "dev")
    test = probes_sha256(p for p in probes if p["split"] == "test")
    return {"files": files, "devProbes": dev, "testProbes": test,
            "digest": digest({**files, "devProbes": dev, "testProbes": test})}


def frozen_manifest() -> Dict[str, Any]:
    return json.loads(FROZEN_FILE.read_text(encoding="utf-8"))


def differences() -> list:
    """Names whose hash differs from the frozen value (empty = nothing changed)."""
    now, then = current_manifest(), frozen_manifest()
    names = set(now["files"]) | set(then["files"])
    changed = sorted(n for n in names if now["files"].get(n) != then["files"].get(n))
    return changed + [k for k in ("devProbes", "testProbes") if now[k] != then[k]]


if __name__ == "__main__":
    if "--write" in sys.argv:
        FROZEN_FILE.write_text(json.dumps(current_manifest(), indent=2) + "\n", encoding="utf-8")
        print(f"wrote {FROZEN_FILE.name}")
    else:
        print("\n".join(differences()) or "frozen manifest matches")
