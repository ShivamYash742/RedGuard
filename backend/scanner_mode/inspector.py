import re
import yaml
from pathlib import Path
from typing import Dict, Any, List

from scanner_mode.schema import sha256_hex

#: The rule file. Opened by path, not relative to the working directory, so
#: the policy endpoints and the scan record read the same file wherever the
#: server was started from.
POLICY_PATH = Path(__file__).parent / "policy.yaml"


class PolicyError(ValueError):
    """policy.yaml is missing, unreadable or invalid. The filter fails closed:
    a scan never starts on a policy that did not load."""


ACTIONS = ("DENY", "ALLOW", "LOG")
MATCH_TYPES = ("boolean", "exact", "threshold")
#: Fields a condition may test besides the contains_<pattern> flags. The shipped
#: policy also names ml_aligned_block / ml_aligned_allow, which nothing sets, so
#: those two rules never match.
_METADATA_FIELDS = {"token_count", "intent_category", "risk_score", "ml_aligned_block", "ml_aligned_allow"}


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def parse_policy(text: str) -> Dict[str, Any]:
    """Parse and validate policy YAML; raise PolicyError on the first problem.
    Used for the file at load time and for every PUT /api/policy body."""
    try:
        policy = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise PolicyError(f"invalid YAML: {exc}") from exc
    if not isinstance(policy, dict):
        raise PolicyError("policy must be a mapping with ingress_rules")
    if policy.get("default_action", "ALLOW") not in ACTIONS:
        raise PolicyError(f"default_action must be one of {ACTIONS}")
    rules = policy.get("ingress_rules")
    if not isinstance(rules, list):
        raise PolicyError("ingress_rules must be a list")

    fields = {f"contains_{key}" for key in Inspector._compile_patterns()} | _METADATA_FIELDS
    for i, rule in enumerate(rules):
        where = f"ingress_rules[{i}]"
        if not isinstance(rule, dict):
            raise PolicyError(f"{where} must be a mapping")
        if not isinstance(rule.get("name"), str) or not rule["name"]:
            raise PolicyError(f"{where} needs a name")
        where = f"rule {rule['name']!r}"
        if not _is_number(rule.get("priority")):
            raise PolicyError(f"{where}: priority must be a number")
        if rule.get("action") not in ACTIONS:
            raise PolicyError(f"{where}: action must be one of {ACTIONS}")
        conditions = rule.get("conditions")
        # A rule without conditions would match every prompt.
        if not isinstance(conditions, list) or not conditions:
            raise PolicyError(f"{where}: conditions must be a non-empty list")
        for cond in conditions:
            if not isinstance(cond, dict):
                raise PolicyError(f"{where}: each condition must be a mapping")
            if cond.get("field") not in fields:
                raise PolicyError(f"{where}: unknown field {cond.get('field')!r}")
            match_type, value = cond.get("match_type"), cond.get("value")
            if match_type not in MATCH_TYPES:
                raise PolicyError(f"{where}: match_type must be one of {MATCH_TYPES}")
            ok = {"boolean": isinstance(value, bool), "threshold": _is_number(value),
                  "exact": isinstance(value, (str, int, float))}[match_type]
            if not ok:
                raise PolicyError(f"{where}: value {value!r} does not fit match_type {match_type}")
    return policy


class Inspector:
    def __init__(self, policy_path: str = None):
        if policy_path is None:
            policy_path = str(POLICY_PATH)
        self.policy_path = policy_path
        self.policy_text = self._read_policy()
        self.policy_sha256 = sha256_hex(self.policy_text)
        try:
            self.policy = parse_policy(self.policy_text)
        except PolicyError as exc:
            raise PolicyError(f"{self.policy_path}: {exc}") from exc
        self.patterns = self._compile_patterns()

    def _read_policy(self) -> str:
        try:
            return Path(self.policy_path).read_text()
        except OSError as exc:
            raise PolicyError(f"cannot read policy {self.policy_path}: {exc}") from exc

    @staticmethod
    def _compile_patterns():
        # Each pattern matches the shape of an attack (a verb aimed at a target),
        # not a single word: "token", "upload", "kill" or a URL alone blocked
        # 20 of 25 ordinary questions. Two matches reach the 0.2 risk threshold
        # in policy.yaml, so a loose pattern costs twice. [^.\n]{0,N} keeps a
        # match inside one sentence.
        secrets = (r"api[ _]?keys?|(access|session|auth|bearer) tokens?|passwords?|password hash(es)?"
                   r"|secrets?|credentials|private keys?|connection strings?")
        patterns = {
            "injection_patterns":
                r"\b(ignore|disregard|forget|override|replaces?)\b[^.\n]{0,40}\b(previous|prior|above|earlier|all|your|system)\b"
                r"[^.\n]{0,30}\b(instructions?|rules|prompts?|guidelines|polic(y|ies))\b"
                r"|\bsystem override\b|\binternal note\b",
            "role_impersonation":
                r"\byou are now\b[^.\n]{0,30}\b(unrestricted|unfiltered|jailbroken|dan|developer mode|debug mode|maintenance mode)\b"
                r"|\b(act|behave|respond) as (an? )?(unrestricted|unfiltered|jailbroken|uncensored|dan)\b"
                r"|\b(enter|enable|activate)\b[^.\n]{0,15}\b(developer|debug|maintenance|god|dan) mode\b"
                r"|(?m:^\s*assistant\s*:)",  # a fabricated assistant turn pasted into the input
            "exfiltration":
                r"\b(pastebin|webhook\.site|requestbin|transfer\.sh)\b"
                r"|\b(send|forward|upload|post|exfiltrate)\b[^.\n]{0,50}\b(" + secrets +
                r"|financial (records|information|data)|payment details|all (emails|messages|files|records|data))\b",
            "sensitive_paths":
                r"/etc/(shadow|passwd|sudoers)\b|~/\.ssh\b|\bid_rsa\b|/root/"
                r"|\b(show|print|cat|display|dump|reveal|output)\b[^.\n]{0,40}(?<![\w.])\.env\b",
            "system_commands":
                r"\brm\s+-rf\s+[/~*]|\b(curl|wget)\b[^|\n]*\|\s*(sudo\s+)?(ba|z)?sh\b|\bchmod\s+(-R\s+)?777\b",
            "credentials":
                r"\bAPI_KEY\b|\b(reveal|show|print|output|display|dump|repeat|expose|leak|send)\b[^.\n]{0,25}"
                r"\b(your|the|all|any|their|users?'?|admin|system)\b[^.\n]{0,15}\b(" + secrets + r")\b",
            "malware_request":
                r"\breverse shell\b|\b(write|create|build|generate|make)\b[^.\n]{0,30}\b(malware|ransomware|keylogger|rootkit|botnet)\b",
            "harm_patterns":
                r"\b(kill|poison|murder|hurt)\s+(someone|somebody|people|a person|my (wife|husband|partner|boss|neighbou?r))\b"
                r"|\b(build|make|assemble)\b[^.\n]{0,15}\b(bomb|explosive)s?\b",
            # A decode-then-act request, or a long mixed-case base64 blob (hex hashes have no capitals).
            "obfuscation":
                r"\b(decode|decrypt|deobfuscate)\b[^.\n]{0,60}\b(execute|run|follow|obey)\b"
                r"|(?-i:\b(?=[A-Za-z0-9+/]*[a-z])(?=[A-Za-z0-9+/]*[A-Z])[A-Za-z0-9+/]{40,}={0,2})",
            "phishing_patterns": r"\bverify your account\b|\bclick here urgently\b",
            "pii_request": r"\b(ssn|social security number|credit card number|cvv)\b",
        }
        return {key: re.compile(rx, re.IGNORECASE) for key, rx in patterns.items()}

    def inspect(self, prompt: str) -> Dict[str, Any]:
        metadata = {}
        risk_score = 0.0
        
        # Check patterns
        for key, pattern in self.patterns.items():
            contains = bool(pattern.search(prompt))
            metadata[f"contains_{key}"] = contains
            if contains:
                risk_score += 0.1

        # Token count approximation
        metadata["token_count"] = len(prompt.split())
        
        # Determine intent_category (naive approach for DPI)
        intent_category = "unknown"
        if metadata.get("contains_credentials"):
            intent_category = "credential_access"
            risk_score += 0.2
        elif metadata.get("contains_sensitive_paths"):
            intent_category = "file_io"
            risk_score += 0.2
            
        metadata["intent_category"] = intent_category

        # Cap risk score at 1.0
        metadata["risk_score"] = min(1.0, risk_score)
        
        return metadata

    def evaluate_policy(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        rules = self.policy.get("ingress_rules", [])
        
        # Sort rules by priority (highest first)
        rules = sorted(rules, key=lambda x: x.get("priority", 0), reverse=True)
        
        for rule in rules:
            conditions = rule.get("conditions", [])
            matches = True
            
            for condition in conditions:
                field = condition.get("field")
                match_type = condition.get("match_type")
                value = condition.get("value")
                
                if field not in metadata:
                    matches = False
                    break
                    
                actual_val = metadata[field]
                
                if match_type == "boolean":
                    if bool(actual_val) != bool(value):
                        matches = False
                        break
                elif match_type == "exact":
                    if actual_val != value:
                        matches = False
                        break
                elif match_type == "threshold":
                    try:
                        below = float(actual_val) < float(value)
                    except (TypeError, ValueError):
                        below = True  # a threshold on a text field (the validator cannot know field types) never matches
                    if below:
                        matches = False
                        break
            
            if matches:
                return {
                    "verdict": rule.get("action", "ALLOW"),
                    "matched_rule": rule.get("name"),
                    "deny_message": rule.get("deny_message")
                }
                
        return {
            "verdict": self.policy.get("default_action", "ALLOW"),
            "matched_rule": None,
            "deny_message": None
        }

    def process(self, prompt: str) -> Dict[str, Any]:
        metadata = self.inspect(prompt)
        policy_result = self.evaluate_policy(metadata)
        
        return {
            "metadata": metadata,
            "policy_result": policy_result
        }
