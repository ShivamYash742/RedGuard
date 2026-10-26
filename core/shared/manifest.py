"""
Content hashes that pin what a result was measured with.

A number is only comparable to another if the same probes, prompts, filter and scorer produced it. These
helpers hash a set of files (and a set of probes) so a session can record one digest, and a test can fail when
something that must stay frozen changes. Pure Python; no network and no database.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping


def file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tree_hashes(root: Path, files: Iterable[Path]) -> Dict[str, str]:
    """{path relative to root, posix style: sha256}, sorted. A directory contributes every file under it."""
    out: Dict[str, str] = {}
    for item in files:
        item = Path(item)
        for f in sorted(item.rglob("*")) if item.is_dir() else [item]:
            if f.is_file() and "__pycache__" not in f.parts:
                out[f.relative_to(root).as_posix()] = file_sha256(f)
    return dict(sorted(out.items()))


def probes_sha256(probes: Iterable[Mapping[str, Any]]) -> str:
    """Hash of the probes' full content, in id order, so any edit to one changes it."""
    ordered = sorted(probes, key=lambda p: p["id"])
    return hashlib.sha256(json.dumps(ordered, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def digest(parts: Mapping[str, str]) -> str:
    """One hash over named hashes; the names are part of it."""
    return hashlib.sha256("\n".join(f"{k}={v}" for k, v in sorted(parts.items())).encode("utf-8")).hexdigest()
