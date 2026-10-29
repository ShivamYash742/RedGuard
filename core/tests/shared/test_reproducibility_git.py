"""LAB-09: the commit stamp is the repo's, whatever directory the process was started from."""

import subprocess

import pytest

from core.shared import reproducibility as repro

pytestmark = pytest.mark.skipif(not (repro._REPO_ROOT / ".git").exists(), reason="not a git checkout (e.g. the Docker image)")


def test_the_stamp_comes_from_this_repo_not_the_working_directory(tmp_path, monkeypatch):
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repro._REPO_ROOT, capture_output=True, text=True).stdout.strip()
    monkeypatch.chdir(tmp_path)                       # a directory in no repository
    assert repro._get_git_commit() == head
    assert repro._get_git_status_clean() is not None
