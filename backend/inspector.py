import re
import yaml
from pathlib import Path
from typing import Dict, Any, List

class Inspector:
    def __init__(self, policy_path: str = None):
        if policy_path is None:
            policy_path = str(Path(__file__).parent / "policy.yaml")
        self.policy_path = policy_path
        self.policy = self._load_policy()
        self.patterns = self._compile_patterns()

    def _load_policy(self) -> Dict[str, Any]:
        try:
            with open(self.policy_path, "r") as f:
                return yaml.safe_load(f)
        except Exception:
            return {"ingress_rules": [], "default_action": "ALLOW"}

    def _compile_patterns(self):
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
                    if float(actual_val) < float(value):
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
