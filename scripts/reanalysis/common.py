"""Shared helpers for the re-analysis scripts.

Everything here is read-only on the source database: it is copied to a temporary folder first and the
copy is opened with SQLite's read-only, immutable mode, so no code path can write to the original or
to the copy. No model is called anywhere in scripts/reanalysis/.
"""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator

REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "backend"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

NOTE = "Re-analysis of stored outputs; no new model runs."


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


@contextmanager
def open_copy(source: Path) -> Iterator[sqlite3.Connection]:
    """Copy `source` to a temp folder and yield a read-only, immutable connection to the copy."""
    source = Path(source)
    if source.resolve() == (REPO / "backend" / "prisma" / "dev.db").resolve():
        raise SystemExit("refusing to analyse backend/prisma/dev.db: it is the committed demo seed, not an experiment database")
    with tempfile.TemporaryDirectory(prefix="redguard-reanalysis-") as tmp:
        copy = Path(tmp) / source.name
        shutil.copy2(source, copy)
        conn = sqlite3.connect(f"file:{copy}?mode=ro&immutable=1", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()


def stamp(source: Path) -> Dict[str, Any]:
    """Versions, source checksum and a reminder of what this is, written into every output."""
    from core.shared.version import get_lab_version_info, get_version_info

    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, timeout=10).stdout.strip() or None
    except Exception:
        commit = None
    return {
        "note": NOTE,
        "source_db": Path(source).name,
        "source_sha256": sha256_file(Path(source)),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "analysis_code_git_commit": commit,
        "scanner_versions": get_version_info(),
        "lab_versions": get_lab_version_info(),
    }
