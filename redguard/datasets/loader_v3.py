"""
v3 Attack Case loader.

Loads and validates RedGuard v3 multi-agent security test cases.
Does NOT touch the v2 dataset files or loader.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

V3_DIR = Path(__file__).parent / "v3"
SCHEMA_PATH = Path(__file__).parent / "schema_v3.json"

# Valid controlled vocabulary (mirrors schema_v3.json)
_VALID_FAMILIES = frozenset({
    "content_injection", "tool_manipulation", "state_poisoning",
    "direct_injection", "data_exfiltration", "goal_diversion",
    "memory_poisoning", "autonomous_actions", "planning_manipulation",
})
_ID_PATTERN = re.compile(r"^RG-[A-Z]{2}-[0-9]{3}-MA$")


# ── AttackCase dataclass ───────────────────────────────────────────────────────

@dataclass
class AttackCase:
    """A loaded and validated v3 Security Test Case."""

    id: str
    version: str
    title: str
    attack_family: str
    attack_variant: str
    execution_scope: str
    attacker_capability: str
    attack_entry_point: str
    attack_objective: str
    target_agent: str
    target_resource: str
    legitimate_task: str
    preconditions: Dict[str, Any]
    adversarial_artifact: str
    injection_location: str
    expected_safe_state: Dict[str, Any]
    forbidden_actions: List[str]
    forbidden_state_changes: List[str]
    expected_propagation: Dict[str, Any]
    expected_containment: str
    observable_evidence: Dict[str, Any]
    secondary_text_indicators: Dict[str, Any] = field(default_factory=dict)
    difficulty: str = "medium"
    severity: str = "medium"
    references: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AttackCase":
        """Build an AttackCase from a raw dict, ignoring unknown fields."""
        known_fields = set(cls.__dataclass_fields__.keys())
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict (JSON-safe)."""
        return {
            "id": self.id,
            "version": self.version,
            "title": self.title,
            "attack_family": self.attack_family,
            "attack_variant": self.attack_variant,
            "execution_scope": self.execution_scope,
            "attacker_capability": self.attacker_capability,
            "attack_entry_point": self.attack_entry_point,
            "attack_objective": self.attack_objective,
            "target_agent": self.target_agent,
            "target_resource": self.target_resource,
            "legitimate_task": self.legitimate_task,
            "preconditions": self.preconditions,
            "adversarial_artifact": self.adversarial_artifact,
            "injection_location": self.injection_location,
            "expected_safe_state": self.expected_safe_state,
            "forbidden_actions": self.forbidden_actions,
            "forbidden_state_changes": self.forbidden_state_changes,
            "expected_propagation": self.expected_propagation,
            "expected_containment": self.expected_containment,
            "observable_evidence": self.observable_evidence,
            "secondary_text_indicators": self.secondary_text_indicators,
            "difficulty": self.difficulty,
            "severity": self.severity,
            "references": self.references,
        }


# ── Validation ────────────────────────────────────────────────────────────────

_REQUIRED_FIELDS = [
    "id", "version", "title", "attack_family", "legitimate_task",
    "adversarial_artifact", "injection_location",
    "expected_safe_state",
    "observable_evidence", "preconditions",
    "expected_propagation", "target_agent", "target_resource",
]


def validate_attack_case(entry: Dict[str, Any]) -> List[str]:
    """
    Validate a v3 attack case entry.

    Returns a list of validation error strings.
    An empty list means the entry is valid.
    """
    errors: List[str] = []

    # Required fields
    for fld in _REQUIRED_FIELDS:
        if fld not in entry or entry[fld] is None:
            errors.append(f"Missing required field: '{fld}'")
        elif isinstance(entry[fld], (str, list, dict)) and not entry[fld]:
            errors.append(f"Required field is empty: '{fld}'")

    # ID format
    case_id = entry.get("id", "")
    if case_id and not _ID_PATTERN.match(case_id):
        errors.append(f"ID '{case_id}' does not match pattern RG-XX-NNN-MA")

    # Version prefix
    version = entry.get("version", "")
    if version and not version.startswith("3."):
        errors.append(f"Version '{version}' must start with '3.'")

    # Attack family
    family = entry.get("attack_family", "")
    if family and family not in _VALID_FAMILIES:
        errors.append(f"Unknown attack_family: '{family}'")

    # At least ONE of forbidden_actions OR forbidden_state_changes must be non-empty
    if not entry.get("forbidden_actions") and not entry.get("forbidden_state_changes"):
        errors.append(
            "At least one of 'forbidden_actions' or 'forbidden_state_changes' must be non-empty"
        )

    # observable_evidence must have compromise_indicators
    evidence = entry.get("observable_evidence", {})
    if not isinstance(evidence, dict) or not evidence.get("compromise_indicators"):
        errors.append("'observable_evidence.compromise_indicators' must be non-empty")

    # expected_propagation must have entry_agent
    prop = entry.get("expected_propagation", {})
    if isinstance(prop, dict) and not prop.get("entry_agent"):
        errors.append("'expected_propagation.entry_agent' is required")

    return errors


# ── Loaders ───────────────────────────────────────────────────────────────────

def load_v3_attack_cases(
    family: Optional[str] = None,
    strict: bool = False,
) -> List[AttackCase]:
    """
    Load all v3 attack cases from the v3/ directory.

    Parameters
    ----------
    family : Optional[str]
        If provided, only return cases with this attack_family.
    strict : bool
        If True, raise ValueError on the first validation error.
        If False, log a warning and skip invalid entries.

    Returns
    -------
    List[AttackCase]
        All valid attack cases matching the filter.
    """
    cases: List[AttackCase] = []

    if not V3_DIR.exists():
        return cases

    for json_file in sorted(V3_DIR.glob("*.json")):
        try:
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            print(f"Warning: Could not parse {json_file.name}: {exc}")
            continue

        for entry in data.get("entries", []):
            # Family filter (early exit)
            if family and entry.get("attack_family") != family:
                continue

            errors = validate_attack_case(entry)
            if errors:
                msg = f"Validation errors in {entry.get('id', '?')} ({json_file.name}): {errors}"
                if strict:
                    raise ValueError(msg)
                print(f"Warning: {msg}")
                continue

            cases.append(AttackCase.from_dict(entry))

    return cases


def get_attack_case(case_id: str) -> Optional[AttackCase]:
    """Load a single attack case by ID. Returns None if not found."""
    for case in load_v3_attack_cases():
        if case.id == case_id:
            return case
    return None


def list_attack_case_ids(family: Optional[str] = None) -> List[str]:
    """Return a sorted list of all registered attack case IDs."""
    return sorted(c.id for c in load_v3_attack_cases(family=family))


def get_attack_cases_by_family() -> Dict[str, List[AttackCase]]:
    """Return a dict mapping family → list of AttackCase."""
    result: Dict[str, List[AttackCase]] = {}
    for case in load_v3_attack_cases():
        result.setdefault(case.attack_family, []).append(case)
    return result
