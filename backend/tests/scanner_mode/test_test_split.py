"""The dev/test split: test probes are held out, frozen, reproducible and scored from evidence."""

import json
import re
from collections import Counter
from pathlib import Path

from scanner_mode import manifest  # first: it puts the repo root (core/, scripts/) on sys.path

from core.scanner_mode.datasets.loader import load_all_datasets

PROBES = load_all_datasets(validate=False)
TEST = [p for p in PROBES if p["split"] == "test"]
TEST_ATTACKS = [p for p in TEST if not p.get("benign_control")]
TEST_CONTROLS = [p for p in TEST if p.get("benign_control")]
BACKEND = Path(manifest.BACKEND)


def test_hand_written_probes_are_dev_and_generated_ones_are_test():
    for p in PROBES:
        number = int(p["id"].rsplit("-", 1)[1])
        assert p["split"] == ("test" if number >= 100 else "dev"), p["id"]


def test_the_test_split_is_big_enough_to_say_something():
    assert len(TEST_ATTACKS) >= 160 and len(TEST_CONTROLS) >= 80
    per_family = Counter(p["attack_family"] for p in TEST_ATTACKS)
    assert len(per_family) == 8 and min(per_family.values()) >= 15, per_family


def test_every_test_attack_is_scored_from_evidence_not_wording():
    for p in TEST_ATTACKS:
        assert p["evaluation_rules"].get("success_actions") or p.get("canary"), p["id"]
        assert not p["evaluation_rules"].get("success_indicators"), p["id"]


def test_every_test_control_that_reads_a_tool_has_an_attack_with_the_same_prompt_and_tool():
    attacks = {(p["prompt"], tuple(sorted(p.get("tool_fixtures", {})))) for p in TEST_ATTACKS}
    for c in TEST_CONTROLS:
        if c.get("tool_fixtures"):
            assert (c["prompt"], tuple(sorted(c["tool_fixtures"]))) in attacks, c["id"]


def test_generated_probes_are_exactly_what_the_generator_writes():
    from scripts.gen_test_probes import generate
    expected = {e["id"]: json.loads(json.dumps(e)) for entries in generate().values() for e in entries}
    assert {p["id"]: p for p in TEST} == expected


def test_nothing_the_filter_prompts_or_scorer_contain_comes_from_the_test_split():
    """A pattern or prompt tuned to a test item would contain its distinctive strings."""
    tuning = "\n".join((BACKEND / f).read_text(encoding="utf-8", errors="ignore").lower() for f in
                       ["scanner_mode/policy.yaml", "scanner_mode/inspector.py", "scanner_mode/agents/system_prompts.json",
                        "scanner_mode/agents/_prompt_loader.py"])
    tokens = set()
    for p in TEST:
        for spec in p["evaluation_rules"].get("success_actions", []):
            tokens.update(v.lower() for v in spec.get("args_contain", {}).values())
        tokens.update(re.findall(r"[a-z0-9-]+\.example", " ".join([p["prompt"], *p.get("tool_fixtures", {}).values()]).lower()))
    assert len(tokens) > 20
    for token in sorted(tokens):
        assert token not in tuning, f"{token!r} is a test-probe string and appears in the filter, prompts or loader"


def test_the_frozen_files_and_probe_sets_have_not_changed():
    changed = manifest.differences()
    assert not changed, (f"{changed} differ from scanner_mode/frozen_manifest.json. If the change is deliberate, run "
                         "`python -m scanner_mode.manifest --write` and bump BENCHMARK_VERSION: scores stop being comparable.")


def test_the_manifest_is_deterministic():
    assert manifest.current_manifest() == manifest.current_manifest()


def test_session_records_the_manifest_digest(client, policy_file):
    started = client.post("/api/scan/start", json={})
    assert started.status_code == 200, started.text
    session = next(s for s in client.get("/api/sessions").json() if s["id"] == started.json()["sessionId"])
    assert session["manifestSha256"] == manifest.current_manifest()["digest"]
