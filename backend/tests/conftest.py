"""Shared fixtures for the backend suite.

`migrated_db_template` exists because the committed `prisma/dev.db` is seed
data for Mode A's demo and does not carry the Mode B `lab_*` tables — and
CLAUDE.md forbids writing to it. So the lab tests never read it directly:
once per session it is copied into a temp dir and brought up to the current
schema with `prisma db push` (additive), and each test copies *that*.

Without this, a fresh clone failed every lab store/API test with
`TableNotFoundError` — the tables only ever existed on the machine that had
pushed the schema locally.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).parent.parent
DEV_DB = BACKEND_DIR / "prisma" / "dev.db"
SCHEMA = BACKEND_DIR / "prisma" / "schema.prisma"


def _prisma_cli() -> list:
    exe = shutil.which("prisma", path=str(Path(sys.executable).parent)) or shutil.which("prisma")
    return [exe] if exe else [sys.executable, "-m", "prisma"]


@pytest.fixture(scope="session")
def migrated_db_template(tmp_path_factory) -> Path:
    template = tmp_path_factory.mktemp("db") / "template.db"
    shutil.copyfile(DEV_DB, template)
    env = {**os.environ, "DATABASE_URL": f"file:{template}"}
    result = subprocess.run(
        [*_prisma_cli(), "db", "push", "--schema", str(SCHEMA), "--skip-generate"],
        env=env, capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"prisma db push failed:\n{result.stdout}\n{result.stderr}")
    return template
