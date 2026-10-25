"""
Sample size, minimum detectable effect and paired comparison.

A leaderboard that ranks two agents on 46 probes is claiming more than the data
can say. These helpers state how much data a comparison needs and decide, for a
comparison that was run, whether it shows a difference or only noise.

Pure Python; no network and no database. Used by both modes.
"""

from __future__ import annotations

import itertools
import math
import random
from typing import Any, Dict, Optional, Sequence, Tuple

Z_ALPHA = 1.959964    # two-sided 5%
Z_POWER = 0.841621    # 80% power
_EXACT_LIMIT = 16     # nonzero differences up to this many are enumerated exactly


def n_per_arm(p1: float, p2: float, z_alpha: float = Z_ALPHA, z_power: float = Z_POWER) -> int:
    """Independent items per arm to tell rate p1 from p2 (two-sided 5%, 80% power, unpaired)."""
    if p1 == p2:
        raise ValueError("p1 and p2 must differ")
    pbar = (p1 + p2) / 2
    root = z_alpha * math.sqrt(2 * pbar * (1 - pbar)) + z_power * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))
    return math.ceil(root * root / (p1 - p2) ** 2)


def min_detectable_effect(n: int, p: float, z_alpha: float = Z_ALPHA, z_power: float = Z_POWER) -> Optional[float]:
    """Smallest drop from rate p that `n` independent items per arm detects (80% power). None when none can."""
    if n < 2 or p <= 0 or n_per_arm(p, 0.0, z_alpha, z_power) > n:
        return None
    lo, hi = 0.0, p      # hi is always a detectable drop
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if n_per_arm(p, p - mid, z_alpha, z_power) > n else (lo, mid)
    return round(hi, 4)


def min_detectable_difference_paired(sd: float, n: int, z_alpha: float = Z_ALPHA, z_power: float = Z_POWER) -> Optional[float]:
    """Smallest mean paired difference detectable with n clusters when per-cluster differences have spread `sd`."""
    return None if n < 2 else (z_alpha + z_power) * sd / math.sqrt(n)


def paired_difference(diffs: Sequence[float], *, seed: int = 0, n_boot: int = 4000) -> Dict[str, Any]:
    """Mean of per-cluster differences, a bootstrap interval over clusters, and a sign-flip test.

    `diffs[i]` is rate_A - rate_B on cluster i (a probe in Scanner mode, a case in Lab mode), so the unit
    of analysis is the cluster and repeated runs of one cluster cannot inflate n. The p-value is exact
    (all sign patterns) for up to 16 nonzero differences and a seeded Monte Carlo above that.
    The interval is a percentile bootstrap: with fewer than ~10 clusters treat it as indicative only.
    """
    n = len(diffs)
    if n == 0:
        return {"n": 0, "mean": None, "ci": None, "p": None, "sd": None}
    mean = sum(diffs) / n
    sd = math.sqrt(sum((d - mean) ** 2 for d in diffs) / (n - 1)) if n > 1 else 0.0
    rng = random.Random(seed)
    boots = sorted(sum(rng.choice(diffs) for _ in range(n)) / n for _ in range(n_boot))
    ci = [boots[int(0.025 * n_boot)], boots[int(0.975 * n_boot) - 1]]
    nonzero = [d for d in diffs if d != 0]
    p: Optional[float] = 1.0
    if nonzero:
        observed = abs(sum(nonzero))
        if len(nonzero) <= _EXACT_LIMIT:
            signs = itertools.product((1, -1), repeat=len(nonzero))
            extreme = sum(abs(sum(s * d for s, d in zip(sg, nonzero))) >= observed - 1e-12 for sg in signs)
            p = extreme / 2 ** len(nonzero)
        else:
            extreme = sum(abs(sum(rng.choice((1, -1)) * d for d in nonzero)) >= observed - 1e-12 for _ in range(n_boot))
            p = (extreme + 1) / (n_boot + 1)
    return {"n": n, "mean": mean, "ci": ci, "p": p, "sd": sd}


def comparison_verdict(result: Dict[str, Any], *, label_a: str = "A", label_b: str = "B", p_threshold: float = 0.05) -> Dict[str, Any]:
    """Turn a paired_difference result into a claim the page may show.

    A ranking needs both the interval to exclude zero and the test to pass; anything else is
    "no difference detected", reported with the smallest difference this much data could have detected.
    """
    n, mean, ci, p = result["n"], result["mean"], result["ci"], result["p"]
    if n == 0 or mean is None:
        return {"claim": "no_data", "text": "No shared items to compare."}
    separated = ci[0] > 0 or ci[1] < 0
    mdd = min_detectable_difference_paired(result["sd"] or 0.0, n)
    if separated and p is not None and p <= p_threshold:
        higher, lower = (label_a, label_b) if mean > 0 else (label_b, label_a)
        return {"claim": "difference", "higher": higher, "lower": lower, "min_detectable": mdd,
                "text": f"{higher} has the higher rate than {lower} (difference {abs(mean):.1%}, 95% CI {ci[0]:+.1%} to {ci[1]:+.1%}, p={p:.3f})."}
    detail = f"; this data could detect a difference of about {mdd:.1%}" if mdd is not None else ""
    return {"claim": "none", "higher": None, "lower": None, "min_detectable": mdd,
            "text": f"No difference detected between {label_a} and {label_b} ({mean:+.1%}, 95% CI {ci[0]:+.1%} to {ci[1]:+.1%}, p={p:.3f}){detail}."}


def holm(p_values: Sequence[Optional[float]]) -> Tuple[Optional[float], ...]:
    """Holm-adjusted p-values (family-wise error control across a pre-registered set of comparisons)."""
    idx = [i for i, p in enumerate(p_values) if p is not None]
    order = sorted(idx, key=lambda i: p_values[i])
    out: list = [None] * len(p_values)
    running, m = 0.0, len(order)
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p_values[i]))
        out[i] = running
    return tuple(out)
