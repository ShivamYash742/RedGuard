"""The Lab's frozen code and case sets: a change has to be deliberate."""

from core.lab_mode import manifest
from core.lab_mode.repro import reproducibility_stamp


def test_the_frozen_files_and_case_sets_have_not_changed():
    changed = manifest.differences()
    assert not changed, (f"{changed} differ from core/lab_mode/frozen_manifest.json. If the change is deliberate, run "
                         "`python -m core.lab_mode.manifest --write` and bump the matching version: results stop being comparable.")


def test_the_manifest_is_deterministic_and_separates_dev_from_test():
    a, b = manifest.current_manifest(), manifest.current_manifest()
    assert a == b and a["devCases"] != a["testCases"]


def test_every_run_stamp_carries_the_digest():
    assert reproducibility_stamp()["manifest"] == manifest.current_manifest()["digest"]
