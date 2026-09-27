"""
RedGuard Mode B Reproducibility Capture
=========================================

One function: what produced this run? (§17.)

The honest version of reproducibility here is *auditability*, not byte
determinism. Everything below the model — CEE, gateways, bus, trace assembly,
predicates, evaluator, metrics — is deterministic: same trace in, same verdict
out, always. The model is not: temperature 0 and a seed reduce variance but
guarantee nothing across calls or across provider-side model updates. So the
stamp records provider, model id, code versions and the exact commit, and the
full trace is persisted for every run. A published result is then auditable
even where it is not byte-reproducible — and that distinction must survive
into the paper rather than being quietly rounded up to "deterministic".

Git helpers are reused from `core/benchmark/reproducibility.py` (Mode A,
unchanged) rather than re-implemented — the plan explicitly wires them into a
live path.
"""

from __future__ import annotations

import os
import platform
from datetime import datetime, timezone
from typing import Any, Dict

from ..benchmark.reproducibility import _get_git_commit, _get_git_status_clean
from ..version import get_lab_version_info


def reproducibility_stamp() -> Dict[str, Any]:
    """Versions + code provenance + interpreter, captured at run time.

    `git_clean` is the load-bearing field: a result produced from a dirty
    working tree cannot be reconstructed from its commit, so it is recorded
    rather than assumed. `None` means the question could not be answered (no
    git, no repo, timeout) — which is not the same as clean.
    """
    commit = _get_git_commit()
    clean = _get_git_status_clean()
    if commit is None:
        # Inside a Docker image there is no .git to ask. The build records
        # the commit it was built from; whether that tree was clean cannot
        # be answered here, so `git_clean` stays None ("unknown"), never True.
        commit = os.getenv("REDGUARD_GIT_COMMIT") or None
        clean = None
    return {
        "versions": get_lab_version_info(),
        "git_commit": commit,
        "git_clean": clean,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
