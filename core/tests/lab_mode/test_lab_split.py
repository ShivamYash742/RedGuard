"""The Lab dev/test split: generated cases are held out, reproducible and consistent with their templates."""

from core.lab_mode.cases import case_ids, load_all_cases, validate_all
from scripts.gen_test_cases import TEMPLATES, generate

CASES = {c["id"]: c for c in load_all_cases()}
TEST = {cid: c for cid, c in CASES.items() if c["split"] == "test"}
DEV = {cid: c for cid, c in CASES.items() if c["split"] == "dev"}


def test_hand_written_cases_are_dev_and_generated_ones_are_test():
    assert sorted(DEV) == [f"RGM-{n:03d}" for n in range(1, 11)]
    assert sorted(TEST) == [f"RGM-{n:03d}" for n in range(101, 131)]


def test_generated_cases_are_exactly_what_the_generator_writes():
    assert {c["id"]: c for c in generate()} == TEST


def test_every_test_case_is_a_reachable_attack_with_its_own_canary():
    canaries = [c["attack"]["canary"] for c in CASES.values()]
    assert len(set(canaries)) == len(canaries)
    for c in TEST.values():
        assert c["role"] == "attack" and set(c["objective_reachable_in_arms"]) >= {"attack", "attack_validated"}


def test_a_generated_case_keeps_its_templates_task_flag_and_route():
    for c in generate():
        template = CASES[TEMPLATES[(int(c["id"][4:]) - 101) // 6]]
        assert c["task"] == template["task"] and c["task_endorses_channel"] == template["task_endorses_channel"]
        assert c["attack"]["delivery"] == template["attack"]["delivery"] and c["clean_script"] == template["clean_script"]


def test_the_two_resources_and_three_wordings_are_all_used():
    resources = {c["eligibility"]["eligible_resources"][0] for c in TEST.values()}
    assert resources == {"customer_pii", "payroll"}
    assert len({str(c["attack"]["artifact"]) for c in TEST.values()}) == 30
