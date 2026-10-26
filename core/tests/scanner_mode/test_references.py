"""Every arXiv reference in the probe corpus must be real and match what arXiv says.

verified_arxiv.json lists each ID with its exact arXiv title, checked against the
arXiv API. To cite a new paper, look it up first and add it there; a guessed ID
fails here.
"""

import json
import re
from pathlib import Path

import pytest

from core.scanner_mode.datasets.loader import load_all_datasets

VERIFIED = json.loads((Path(__file__).parent / "verified_arxiv.json").read_text())
ARXIV_ID = re.compile(r"^\d{4}\.\d{4,5}$")


def is_placeholder(arxiv_id: str) -> bool:
    """NNNN.00000, 1234.56789 and similar made-up IDs."""
    tail = arxiv_id.split(".")[-1]
    return tail == "0" * len(tail) or arxiv_id in {"1234.56789", "0000.00000"}


@pytest.mark.parametrize("bad", ["2407.00000", "NNNN.00000", "1234.56789", "0000.00000"])
def test_placeholder_ids_are_rejected(bad):
    assert is_placeholder(bad) or not ARXIV_ID.match(bad)


REFS = [(p["id"], r) for p in load_all_datasets(validate=False) for r in p["references"]]


@pytest.mark.parametrize("probe_id, ref", REFS, ids=lambda x: x if isinstance(x, str) else x.get("arxiv_id", "?"))
def test_every_reference_is_a_verified_paper(probe_id, ref):
    arxiv_id = ref.get("arxiv_id")
    assert arxiv_id and ARXIV_ID.match(arxiv_id) and not is_placeholder(arxiv_id), f"{probe_id}: {arxiv_id!r}"
    assert arxiv_id in VERIFIED, f"{probe_id}: {arxiv_id} has not been checked against arXiv (add it to verified_arxiv.json)"
    assert ref["title"] == VERIFIED[arxiv_id]["title"], f"{probe_id}: title does not match arXiv"
    assert ref["url"] == f"https://arxiv.org/abs/{arxiv_id}"
