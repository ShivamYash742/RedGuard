"""
Regex-filter false positives on a held-out benign set.

    cd backend && python -m scanner_mode.filter_eval [--set xstest_safe.csv] [--split all|tune|holdout] [--list]

Runs every prompt of a benign set (default: the XSTest safe prompts, CC BY 4.0, see
core/scanner_mode/benign_sets/README.md) through the Inspector and reports how many
the policy would DENY, with a Wilson 95% interval, overall and by prompt type.
No model is called. The set is for reporting, not tuning: patterns must not be edited
to pass it. If a pattern is changed, tune on `--split tune` (even ids) and report only
`--split holdout` (odd ids).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))  # so `core` imports when run from backend/

from scanner_mode.inspector import Inspector
from core.shared.statistics import wilson_ci

SETS_DIR = REPO_ROOT / "core" / "scanner_mode" / "benign_sets"


def load_set(name: str = "xstest_safe.csv", split: str = "all") -> List[Dict[str, str]]:
    with (SETS_DIR / name).open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if split == "tune":
        return [r for r in rows if int(r["id"]) % 2 == 0]
    if split == "holdout":
        return [r for r in rows if int(r["id"]) % 2 == 1]
    if split != "all":
        raise ValueError("split must be all, tune or holdout")
    return rows


def _rate(denied: int, total: int) -> Dict[str, Any]:
    lo, hi = wilson_ci(denied, total)
    return {"denied": denied, "total": total, "rate": denied / total if total else 0.0, "lo": lo, "hi": hi}


def evaluate(rows: List[Dict[str, str]], inspector: Inspector | None = None) -> Dict[str, Any]:
    """Block rate of the filter over benign prompts; `blocked` lists what it denied."""
    inspector = inspector or Inspector()
    by_type: Dict[str, List[bool]] = defaultdict(list)
    blocked = []
    for row in rows:
        result = inspector.process(row["prompt"])["policy_result"]
        denied = result["verdict"] == "DENY"
        by_type[row["type"]].append(denied)
        if denied:
            blocked.append({"id": row["id"], "type": row["type"], "prompt": row["prompt"], "rule": result["matched_rule"]})
    return {
        "policy_sha256": inspector.policy_sha256,
        "overall": _rate(len(blocked), len(rows)),
        "by_type": {t: _rate(sum(v), len(v)) for t, v in sorted(by_type.items())},
        "blocked": blocked,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--set", default="xstest_safe.csv")
    parser.add_argument("--split", default="all", choices=["all", "tune", "holdout"])
    parser.add_argument("--list", action="store_true", help="print the denied prompts")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = evaluate(load_set(args.set, args.split))
    if args.json:
        print(json.dumps(result, indent=2))
        return
    o = result["overall"]
    print(f"{args.set} [{args.split}]  policy {result['policy_sha256'][:12]}")
    print(f"denied {o['denied']} / {o['total']} = {o['rate']:.1%}   95% CI {o['lo']:.1%}-{o['hi']:.1%}")
    for t, r in result["by_type"].items():
        print(f"  {t:26s} {r['denied']:3d} / {r['total']:3d}  {r['rate']:6.1%}")
    if args.list:
        for b in result["blocked"]:
            print(f"  [{b['id']}] {b['type']} ({b['rule']}): {b['prompt']}")


if __name__ == "__main__":
    main()
