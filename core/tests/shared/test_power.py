"""Sample-size and paired-comparison helpers."""
import pytest

from core.shared.power import (comparison_verdict, holm, min_detectable_difference_paired,
                               min_detectable_effect, n_per_arm, paired_difference)


def test_n_per_arm_matches_the_textbook_values():
    assert n_per_arm(0.20, 0.10) == 199
    assert n_per_arm(0.20, 0.05) == 76
    assert n_per_arm(0.10, 0.05) == 435
    with pytest.raises(ValueError):
        n_per_arm(0.2, 0.2)


def test_min_detectable_effect_inverts_n_per_arm():
    d = min_detectable_effect(199, 0.20)
    assert d == pytest.approx(0.10, abs=0.005)
    assert min_detectable_effect(8, 0.20) is None          # 8 items cannot detect even a drop to zero
    assert min_detectable_effect(100, 0.0) is None


def test_46_probes_cannot_see_a_ten_point_difference():
    assert min_detectable_effect(46, 0.20) > 0.15


def test_paired_difference_exact_sign_flip():
    r = paired_difference([1.0] * 8)                        # every cluster favours A
    assert r["mean"] == 1.0 and r["p"] == pytest.approx(2 / 2 ** 8)
    assert paired_difference([0.0] * 5)["p"] == 1.0
    assert paired_difference([])["mean"] is None


def test_paired_difference_is_seeded():
    d = [0.5, -0.25, 0.0, 0.25, 0.5, 0.0, 0.25, 0.5, 0.0, 0.25, 0.5, 0.5, 0.0, 0.25, 0.25, 0.5, 0.25, 0.5]   # > 16 nonzero? 14 nonzero
    assert paired_difference(d, seed=3) == paired_difference(d, seed=3)


def test_monte_carlo_branch_above_the_exact_limit():
    r = paired_difference([0.5] * 40, seed=1)
    assert r["p"] < 0.001 and r["ci"][0] > 0


def test_verdict_needs_interval_and_test_to_agree():
    clear = comparison_verdict(paired_difference([0.5] * 12), label_a="a", label_b="b")
    assert clear["claim"] == "difference" and clear["higher"] == "a" and clear["lower"] == "b"
    noisy = comparison_verdict(paired_difference([1.0, -1.0, 0.0, 0.5, -0.5, 0.0]), label_a="a", label_b="b")
    assert noisy["claim"] == "none" and "No difference detected" in noisy["text"]
    assert comparison_verdict(paired_difference([]))["claim"] == "no_data"


def test_holm_is_monotone_and_skips_none():
    adj = holm([0.01, None, 0.04, 0.03])
    assert adj[1] is None
    assert adj[0] == pytest.approx(0.03) and adj[3] == pytest.approx(0.06) and adj[2] == pytest.approx(0.06)


def test_paired_mdd():
    assert min_detectable_difference_paired(0.3, 36) == pytest.approx(0.14, abs=0.01)
    assert min_detectable_difference_paired(0.3, 1) is None
