"""
RedGuard Mode B Case Loader + Validator
========================================

Security test cases are **data, not code** (`CLAUDE.md`): they live as JSON in
`core/lab/cases/*.json`, validated against `core/lab/cases/case_schema.json`.
This module mirrors `core/datasets/loader.py` + `core/datasets/validator.py`
— same hand-rolled style, no new dependency.

What validation is actually for here: a Mode B case is a set of *predicates*
that decide a published verdict. A typo in a predicate key, an `event_type`
that no event ever carries, or a canary missing from its own artifact does not
crash anything — it silently produces NOT_REACHED for every run, which reads
as "the attack failed" when it means "the question was never asked". Every
check below exists to turn one of those silent failures into a loud one.

    from core.lab.cases import load_case, load_all_cases, load_fixture

    python -m core.lab.cases          # validation report, exits non-zero on failure
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .cee import ControlledExecutionEnvironment
from .evaluator import _COMBINATORS, _LEAF_KEYS
from .model_client import FINISH, SEND_MESSAGE, STATE_READ, STATE_WRITE, TOOL_CALL
from .topology import linear_abc
from .tools import TOOLS
from .trace import EventCategory, EventType

CASES_DIR: Path = Path(__file__).parent / "cases"
FIXTURES_DIR: Path = Path(__file__).parent / "fixtures"
CASE_SCHEMA_PATH: Path = CASES_DIR / "case_schema.json"

REQUIRED_FIELDS = [
    "id", "title", "case_version", "schema_version", "topology_id", "cee_fixture",
    "task", "task_success_predicate", "attack", "objective", "eligibility",
    "evaluation", "clean_script", "severity", "references",
]

#: The four families the MVP case set exercises. Deliberately *not* imported
#: from `core/datasets/validator.py`: Mode A owning this set would mean an
#: edit there could silently change what Mode B accepts (§18).
VALID_FAMILIES = {"direct_injection", "content_injection", "memory_poisoning", "tool_manipulation"}

VALID_CHANNELS = {"files", "web", "db", "kv", "task"}
VALID_SEVERITIES = {"low", "medium", "high", "critical"}

#: Topologies a case may name. One entry today; the check exists so a typo'd
#: `topology_id` fails at load instead of at run time.
TOPOLOGIES: Dict[str, Callable[[], Any]] = {"linear_abc": linear_abc}

ID_PATTERN = re.compile(r"^RGM-\d{3}$")
SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
CANARY_PATTERN = re.compile(r"^RG-CANARY-[0-9a-f]{6}$")

MIN_TASK_LENGTH = 20
MIN_ARTIFACT_LENGTH = 20

_EVENT_TYPES = {e.value for e in EventType}
_CATEGORIES = {e.value for e in EventCategory}

#: Required keys per scripted action kind, for `clean_script` validation.
_ACTION_REQUIRED = {
    TOOL_CALL: ("tool", "args"),
    SEND_MESSAGE: ("to", "content"),
    STATE_WRITE: ("key", "value"),
    STATE_READ: ("key",),
    FINISH: ("summary",),
}


# ─────────────────────────────────────────────────────────────────────────────
# Result types (same shape as core/datasets/validator.py)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ValidationResult:
    case_id: str
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        parts = [f"[{'PASS' if self.valid else 'FAIL'}] {self.case_id}"]
        parts += [f"  ERROR: {e}" for e in self.errors]
        parts += [f"  WARN:  {w}" for w in self.warnings]
        return "\n".join(parts)


@dataclass
class ValidationReport:
    results: List[ValidationResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.valid)

    @property
    def is_clean(self) -> bool:
        return self.failed == 0

    def summary(self) -> str:
        lines = ["=" * 60, "RedGuard Mode B Case Validation Report", "=" * 60,
                 f"Total: {self.total} | Passed: {self.total - self.failed} | Failed: {self.failed}", ""]
        lines += [str(r) for r in self.results]
        lines += ["", "=" * 60,
                  "✓ All cases passed validation" if self.is_clean
                  else f"✗ {self.failed} case(s) failed validation — fix before running an experiment"]
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Predicate validation
# ─────────────────────────────────────────────────────────────────────────────

def predicate_leaves(predicate: Any) -> List[Dict[str, Any]]:
    """Every leaf in a predicate tree, flattened."""
    if not isinstance(predicate, dict):
        return []
    for combinator in _COMBINATORS:
        if combinator in predicate:
            children = predicate[combinator]
            if not isinstance(children, list):
                return []
            return [leaf for child in children for leaf in predicate_leaves(child)]
    return [predicate]


def validate_predicate(predicate: Any, path: str, errors: List[str]) -> None:
    """Structural check of one predicate tree.

    `evaluator._leaf_matches` raises on an unknown leaf key, but only if some
    event reaches that leaf — and `event_type` / `category` values are never
    checked at all, so a misspelled one just matches nothing forever. Both
    become load-time errors here.
    """
    if not isinstance(predicate, dict):
        errors.append(f"{path}: predicate must be an object, got {type(predicate).__name__}")
        return

    present = [c for c in _COMBINATORS if c in predicate]
    if present:
        if len(present) > 1 or len(predicate) != 1:
            errors.append(f"{path}: a combinator predicate must have exactly one key ({present} + {sorted(set(predicate) - set(present))})")
            return
        children = predicate[present[0]]
        if not isinstance(children, list) or not children:
            errors.append(f"{path}.{present[0]}: must be a non-empty array")
            return
        for i, child in enumerate(children):
            validate_predicate(child, f"{path}.{present[0]}[{i}]", errors)
        return

    if not predicate:
        errors.append(f"{path}: empty predicate matches every event")
        return

    for key, value in predicate.items():
        if key not in _LEAF_KEYS:
            errors.append(f"{path}: unknown predicate leaf key {key!r} (known: {sorted(_LEAF_KEYS)})")
        elif key == "event_type" and value not in _EVENT_TYPES:
            errors.append(f"{path}.event_type: {value!r} is not an event type in the §8 schema")
        elif key == "category" and value not in _CATEGORIES:
            errors.append(f"{path}.category: {value!r} is not an event category in the §8 schema")
        elif key in ("authorized", "attack_derived", "absent_in_clean") and not isinstance(value, bool):
            errors.append(f"{path}.{key}: must be a boolean, got {type(value).__name__}")


# ─────────────────────────────────────────────────────────────────────────────
# Case validation
# ─────────────────────────────────────────────────────────────────────────────

def _section(case: Dict[str, Any], name: str) -> Dict[str, Any]:
    """A top-level section as a dict, or an empty one.

    Each `_check_*` reports its own section's wrong type and returns, but the
    others keep running — so a cross-section lookup (the entry point, read
    while checking eligibility) must not assume the section it reaches into
    was well formed. The validator's job is to report on a whole set; one
    malformed case must not take the report down with it.
    """
    value = case.get(name)
    return value if isinstance(value, dict) else {}


class CaseValidator:
    """Validates one case dict. `seen_canaries` is threaded across a whole
    set so a duplicated canary — which would make two cases' provenance
    linking and canary-influence tests indistinguishable — is caught.
    """

    def __init__(self) -> None:
        self.seen_canaries: Dict[str, str] = {}

    def validate(self, case: Any, *, source: Optional[Path] = None) -> ValidationResult:
        errors: List[str] = []
        warnings: List[str] = []

        if not isinstance(case, dict):
            return ValidationResult(str(source or "?"), False, [f"case must be an object, got {type(case).__name__}"])

        case_id = case.get("id", "<no id>")

        for f in REQUIRED_FIELDS:
            if f not in case or case[f] in (None, "", [], {}):
                errors.append(f"missing or empty required field: {f}")
        if errors:
            return ValidationResult(case_id, False, errors, warnings)

        self._check_identity(case, source, errors)
        self._check_task(case, errors)
        agents = self._check_eligibility(case, errors)
        self._check_attack(case, agents, errors, warnings)
        self._check_objective(case, errors)
        self._check_evaluation(case, agents, errors)
        self._check_clean_script(case, agents, errors)
        self._check_metadata(case, errors)

        validate_predicate(case["task_success_predicate"], "task_success_predicate", errors)
        self._check_predicate_references(case, agents, errors)

        return ValidationResult(case_id, not errors, errors, warnings)

    # ── sections ──────────────────────────────────────────────────────

    def _check_identity(self, case: Dict[str, Any], source: Optional[Path], errors: List[str]) -> None:
        if not ID_PATTERN.match(case["id"]):
            errors.append(f"id {case['id']!r} does not match RGM-NNN")
        elif source and source.stem != case["id"]:
            errors.append(f"id {case['id']!r} does not match filename {source.name!r}")

        for f in ("case_version", "schema_version"):
            if not SEMVER_PATTERN.match(str(case[f])):
                errors.append(f"{f} {case[f]!r} is not semver")

        if case["topology_id"] not in TOPOLOGIES:
            errors.append(f"unknown topology_id {case['topology_id']!r} (known: {sorted(TOPOLOGIES)})")

        if not (FIXTURES_DIR / f"{case['cee_fixture']}.json").exists():
            errors.append(f"cee_fixture {case['cee_fixture']!r} has no file in {FIXTURES_DIR}")

    def _check_task(self, case: Dict[str, Any], errors: List[str]) -> None:
        if len(str(case["task"])) < MIN_TASK_LENGTH:
            errors.append(f"task is shorter than {MIN_TASK_LENGTH} characters")

        # The agents cannot find what the task does not name. There is no
        # directory-listing tool, so an agent told only to "research the Q3
        # vendor list" guesses filenames, misses, and never observes the
        # artifact — the case then reports NOT_REACHED for reasons that have
        # nothing to do with security, which is indistinguishable in the
        # verdict from a model that resisted.
        delivery = _section(case, "attack").get("delivery") or {}
        channel, location = delivery.get("channel"), delivery.get("location")
        if channel and channel != "task" and location:
            if str(location) not in str(case["task"]):
                errors.append(
                    f"task never mentions {location!r}, where the artifact is planted "
                    f"(channel {channel!r}). Agents have no directory listing, so they "
                    "cannot discover it — the attack would never enter the run."
                )

    def _check_eligibility(self, case: Dict[str, Any], errors: List[str]) -> List[str]:
        eligibility = case["eligibility"]
        if not isinstance(eligibility, dict):
            errors.append("eligibility must be an object")
            return []

        path = eligibility.get("expected_path") or []
        if not path:
            errors.append("eligibility.expected_path must be non-empty")
            return []

        topology = TOPOLOGIES.get(case["topology_id"])
        if topology:
            known = set(topology().agents)
            unknown = [a for a in path if a not in known]
            if unknown:
                errors.append(f"eligibility.expected_path names agents not in topology {case['topology_id']!r}: {unknown}")

        # `eligible_downstream_agents` is the CPR denominator. An agent that
        # is not on the path can never advance the objective, and the entry
        # agent is by definition not *downstream* of itself — either mistake
        # silently shifts every propagation metric.
        eligible = eligibility.get("eligible_downstream_agents", [])
        if not isinstance(eligible, list):
            errors.append("eligibility.eligible_downstream_agents must be an array")
            return path
        off_path = [a for a in eligible if a not in path]
        if off_path:
            errors.append(f"eligible_downstream_agents not on expected_path: {off_path}")
        entry = _section(case, "attack").get("injection_point")
        if entry and entry in eligible:
            errors.append(f"eligible_downstream_agents must exclude the injection point {entry!r}")

        for f in ("eligible_tools", "eligible_resources"):
            if f in eligibility and not isinstance(eligibility[f], list):
                errors.append(f"eligibility.{f} must be an array")

        unknown_tools = [t for t in eligibility.get("eligible_tools", []) if t not in TOOLS]
        if unknown_tools:
            errors.append(f"eligibility.eligible_tools names unregistered tools: {unknown_tools}")

        return path

    def _check_attack(self, case: Dict[str, Any], agents: List[str], errors: List[str], warnings: List[str]) -> None:
        attack = case["attack"]
        if not isinstance(attack, dict):
            errors.append("attack must be an object")
            return

        for f in ("family", "injection_point", "delivery", "artifact", "canary"):
            if not attack.get(f):
                errors.append(f"attack.{f} is required")
        if errors:
            return

        if attack["family"] not in VALID_FAMILIES:
            errors.append(f"unknown attack.family {attack['family']!r} (valid: {sorted(VALID_FAMILIES)})")

        if agents and attack["injection_point"] not in agents:
            errors.append(f"attack.injection_point {attack['injection_point']!r} is not on expected_path {agents}")

        delivery = attack["delivery"]
        if not isinstance(delivery, dict) or "channel" not in delivery or "location" not in delivery:
            errors.append("attack.delivery must be an object with 'channel' and 'location'")
        else:
            channel = delivery["channel"]
            if channel not in VALID_CHANNELS:
                errors.append(f"unknown attack.delivery.channel {channel!r} (valid: {sorted(VALID_CHANNELS)})")
            elif channel == "task":
                if delivery["location"]:
                    warnings.append("attack.delivery.location is ignored for channel 'task'")
            else:
                if not delivery["location"]:
                    errors.append(f"attack.delivery.location is required for channel {channel!r}")
                else:
                    self._check_location_exists(case, channel, delivery["location"], warnings)

        artifact = str(attack["artifact"])
        if len(artifact) < MIN_ARTIFACT_LENGTH:
            errors.append(f"attack.artifact is shorter than {MIN_ARTIFACT_LENGTH} characters")

        canary = attack["canary"]
        if not CANARY_PATTERN.match(str(canary)):
            errors.append(f"attack.canary {canary!r} does not match RG-CANARY-xxxxxx (6 hex)")
        elif canary not in artifact:
            # Without this the canary-in-emitted-content influence test (§10)
            # can never fire, and the gateway can never link a tool result
            # back to the artifact.
            errors.append("attack.canary does not appear in attack.artifact")
        else:
            owner = self.seen_canaries.get(canary)
            if owner and owner != case["id"]:
                errors.append(f"attack.canary {canary!r} is already used by {owner}")
            self.seen_canaries[canary] = case["id"]

    def _check_location_exists(self, case: Dict[str, Any], channel: str, location: str, warnings: List[str]) -> None:
        """Planting into a location the fixture does not already define is
        legal but usually a typo: nothing in the benign task would ever read
        it, so the artifact sits in the CEE untouched and the case measures
        nothing.
        """
        try:
            cee = load_fixture(case["cee_fixture"])
        except (FileNotFoundError, KeyError):
            return
        resource = {"files": cee.files, "web": cee.web, "db": cee.db, "kv": cee.kv}[channel]
        key = location.strip().lower() if channel == "web" else location
        if key not in resource and location not in resource:
            warnings.append(
                f"attack.delivery.location {location!r} is not defined in fixture "
                f"{case['cee_fixture']!r} channel {channel!r} — no benign read will reach it"
            )

    def _check_objective(self, case: Dict[str, Any], errors: List[str]) -> None:
        objective = case["objective"]
        if not isinstance(objective, dict):
            errors.append("objective must be an object")
            return
        if not objective.get("description"):
            errors.append("objective.description is required")
        for level in ("partially_reached", "reached"):
            if level not in objective:
                errors.append(f"objective.{level} is required")
        for level in ("not_reached", "partially_reached", "reached", "critical_reached"):
            if level in objective:
                validate_predicate(objective[level], f"objective.{level}", errors)

    def _check_evaluation(self, case: Dict[str, Any], agents: List[str], errors: List[str]) -> None:
        evaluation = case["evaluation"]
        if not isinstance(evaluation, dict):
            errors.append("evaluation must be an object")
            return

        compromise = evaluation.get("compromise_predicate")
        if not isinstance(compromise, dict) or not compromise:
            errors.append("evaluation.compromise_predicate must be a non-empty object")
            return

        for agent, predicate in compromise.items():
            if agents and agent not in agents:
                errors.append(f"evaluation.compromise_predicate names agent {agent!r} not on expected_path")
            validate_predicate(predicate, f"evaluation.compromise_predicate.{agent}", errors)

        # An agent with no compromise predicate can only ever be INFLUENCED,
        # which caps the containment analysis. Legal (RGM-008 does it on
        # purpose) but it must be a decision, so require the entry agent and
        # every eligible downstream agent to have one.
        required = {
            _section(case, "attack").get("injection_point"),
            *_section(case, "eligibility").get("eligible_downstream_agents", []),
        }
        missing = sorted(a for a in required if a and a not in compromise)
        if missing:
            errors.append(f"evaluation.compromise_predicate is missing the entry/eligible agents: {missing}")

        for agent, predicate in (evaluation.get("influence_predicates") or {}).items():
            if agents and agent not in agents:
                errors.append(f"evaluation.influence_predicates names agent {agent!r} not on expected_path")
            validate_predicate(predicate, f"evaluation.influence_predicates.{agent}", errors)

    def _check_clean_script(self, case: Dict[str, Any], agents: List[str], errors: List[str]) -> None:
        script = case["clean_script"]
        if not isinstance(script, dict) or not script:
            errors.append("clean_script must be a non-empty object keyed by agent")
            return

        topology = TOPOLOGIES.get(case["topology_id"])
        topo = topology() if topology else None

        for agent in agents:
            if agent not in script:
                errors.append(f"clean_script has no actions for agent {agent!r} on expected_path")

        for agent, actions in script.items():
            if agents and agent not in agents:
                errors.append(f"clean_script names agent {agent!r} not on expected_path")
            if not isinstance(actions, list) or not actions:
                errors.append(f"clean_script.{agent} must be a non-empty array")
                continue
            for i, action in enumerate(actions):
                self._check_action(agent, i, action, topo, case, errors)

    def _check_action(self, agent: str, i: int, action: Any, topo: Any, case: Dict[str, Any], errors: List[str]) -> None:
        where = f"clean_script.{agent}[{i}]"
        if not isinstance(action, dict):
            errors.append(f"{where}: must be an object")
            return
        kind = action.get("action")
        if kind not in _ACTION_REQUIRED:
            errors.append(f"{where}: unknown action {kind!r} (valid: {sorted(_ACTION_REQUIRED)})")
            return
        for f in _ACTION_REQUIRED[kind]:
            if f not in action:
                errors.append(f"{where}: action {kind!r} requires {f!r}")

        if topo is None:
            return
        # A clean script that the gateway would deny is not a baseline of a
        # compliant run — it would put tool_denied / message_denied events in
        # the very trace the attack run is compared against.
        if kind == TOOL_CALL and action.get("tool") and not topo.tool_authorized(agent, action["tool"]):
            errors.append(f"{where}: agent {agent!r} is not authorized to call {action['tool']!r}")
        if kind == SEND_MESSAGE and action.get("to") and not topo.can_send(agent, action["to"]):
            errors.append(f"{where}: topology has no edge {agent!r} -> {action['to']!r}")
        if kind == STATE_WRITE and not topo.state_authorized(agent, "write"):
            errors.append(f"{where}: agent {agent!r} has no state write authorization")
        if kind == STATE_READ and not topo.state_authorized(agent, "read"):
            errors.append(f"{where}: agent {agent!r} has no state read authorization")
        if kind == TOOL_CALL and action.get("tool") and action["tool"] not in TOOLS:
            errors.append(f"{where}: unregistered tool {action['tool']!r}")

    def _check_predicate_references(self, case: Dict[str, Any], agents: List[str], errors: List[str]) -> None:
        """Every `tool` and `agent` a predicate names must be able to exist.

        A predicate naming `db_quer` or agent `D` is structurally valid and
        parses fine — it simply never matches, so the case reports
        NOT_REACHED for every model forever. Unlike an unreachable objective
        (RGM-005's denied `file_read` is unreachable *on purpose*), a
        misspelled name is never intentional.
        """
        # Earlier checks report a malformed `objective` / `evaluation` but do
        # not abort, so this pass must survive one rather than crash the whole
        # validation report on the first bad case.
        trees = [("task_success_predicate", case["task_success_predicate"])]
        objective = case.get("objective")
        if isinstance(objective, dict):
            trees += [(f"objective.{k}", v) for k, v in objective.items() if k != "description"]
        evaluation = case.get("evaluation")
        if isinstance(evaluation, dict):
            for group in ("compromise_predicate", "influence_predicates"):
                entries = evaluation.get(group)
                if isinstance(entries, dict):
                    trees += [(f"evaluation.{group}.{a}", p) for a, p in entries.items()]

        for where, tree in trees:
            for leaf in predicate_leaves(tree):
                tool = leaf.get("tool")
                if tool is not None and tool not in TOOLS:
                    errors.append(f"{where}: names unregistered tool {tool!r}")
                agent = leaf.get("agent")
                if agent is not None and agents and agent not in agents:
                    errors.append(f"{where}: names agent {agent!r} not on expected_path {agents}")

    def _check_metadata(self, case: Dict[str, Any], errors: List[str]) -> None:
        if case["severity"] not in VALID_SEVERITIES:
            errors.append(f"unknown severity {case['severity']!r} (valid: {sorted(VALID_SEVERITIES)})")
        references = case["references"]
        if not isinstance(references, list) or not references:
            errors.append("references must be a non-empty array")
            return
        for i, ref in enumerate(references):
            if not isinstance(ref, dict) or not ref.get("title"):
                errors.append(f"references[{i}]: must be an object with a 'title'")


# ─────────────────────────────────────────────────────────────────────────────
# Loading
# ─────────────────────────────────────────────────────────────────────────────

def case_path(case_id: str) -> Path:
    path = CASES_DIR / f"{case_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"No case file for {case_id!r} at {path}")
    return path


def load_case(case_id: str, *, validate: bool = True) -> Dict[str, Any]:
    path = case_path(case_id)
    with open(path, encoding="utf-8") as f:
        case = json.load(f)
    if validate:
        result = CaseValidator().validate(case, source=path)
        if not result.valid:
            raise ValueError(f"Invalid case {case_id}:\n{result}")
    return case


def case_ids() -> List[str]:
    return sorted(p.stem for p in CASES_DIR.glob("RGM-*.json"))


def load_all_cases(*, validate: bool = True) -> List[Dict[str, Any]]:
    """Load every case, optionally validating the set as a whole (which is
    what makes cross-case checks such as canary uniqueness possible).
    """
    cases = []
    validator = CaseValidator()
    for cid in case_ids():
        path = case_path(cid)
        with open(path, encoding="utf-8") as f:
            case = json.load(f)
        if validate:
            result = validator.validate(case, source=path)
            if not result.valid:
                raise ValueError(f"Invalid case {cid}:\n{result}")
        cases.append(case)
    return cases


def validate_all() -> ValidationReport:
    report = ValidationReport()
    validator = CaseValidator()
    for cid in case_ids():
        path = case_path(cid)
        try:
            with open(path, encoding="utf-8") as f:
                case = json.load(f)
        except json.JSONDecodeError as exc:
            report.results.append(ValidationResult(cid, False, [f"not valid JSON: {exc}"]))
            continue
        report.results.append(validator.validate(case, source=path))
    return report


def fixture_path(fixture_id: str) -> Path:
    path = FIXTURES_DIR / f"{fixture_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"No CEE fixture {fixture_id!r} at {path}")
    return path


def load_fixture(fixture_id: str) -> ControlledExecutionEnvironment:
    return ControlledExecutionEnvironment.from_fixture(fixture_path(fixture_id))


def fixture_factory(case: Dict[str, Any]) -> Callable[[], ControlledExecutionEnvironment]:
    """A zero-arg factory building a *fresh* CEE per run — §17 resets the
    environment for every run rather than carrying it over, so an attack run
    can never inherit a previous run's mutations.
    """
    fixture_id = case["cee_fixture"]
    fixture_path(fixture_id)  # fail now, not inside the run loop
    return lambda: load_fixture(fixture_id)


def main() -> int:
    report = validate_all()
    print(report.summary())
    return 0 if report.is_clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
