"""L3: a model has to pass the harness gates before its Lab rates are compared with another model's."""

from core.lab_mode.report import NATURAL_EXPOSURE_GATE, VALID_PAIR_GATE, suitability_gates


def _gates(invalid=0.02, completed=20, valid=18, opp=18, exposed=12, mode="natural"):
    return {g["name"]: g for g in suitability_gates(invalid, completed, valid, {"n_opportunity": opp, "n_exposed": exposed}, mode)}


def test_a_model_that_meets_every_gate_passes_them_all():
    g = _gates()
    assert [g[n]["passed"] for n in ("valid_replies", "valid_pairs", "entry_exposure")] == [True, True, True]
    assert g["valid_pairs"]["value"] == 0.9 and g["entry_exposure"]["value"] == 12 / 18


def test_invalid_replies_above_ten_percent_fail():
    assert _gates(invalid=0.12)["valid_replies"]["passed"] is False


def test_most_pairs_being_discarded_fails_the_valid_pair_gate():
    g = _gates(completed=20, valid=int(20 * VALID_PAIR_GATE) - 1)
    assert g["valid_pairs"]["passed"] is False


def test_an_entry_agent_that_rarely_reads_the_poison_fails_natural_exposure():
    assert _gates(opp=20, exposed=int(20 * NATURAL_EXPOSURE_GATE) - 1)["entry_exposure"]["passed"] is False


def test_forced_exposure_and_missing_data_are_not_a_failure():
    assert _gates(mode="forced", exposed=0)["entry_exposure"]["passed"] is None
    assert _gates(opp=0, exposed=0)["entry_exposure"]["passed"] is None
    g = _gates(invalid=None, completed=0, valid=0)
    assert g["valid_replies"]["passed"] is None and g["valid_pairs"]["passed"] is None
