import asyncio
import os
import httpx
from prisma import Json
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, Any, List, Tuple

from inspector import Inspector
from database import get_db
from schema import sha256_hex
from agent_loader import get_agent, DEFAULT_AGENT_ID

from probes import (
    CONTENT_INJECTION,
    SEMANTIC_MANIPULATION,
    COGNITIVE_STATE,
    BEHAVIOURAL_CONTROL,
    SYSTEMIC,
    HUMAN_IN_THE_LOOP,
)

CLASSIFIER_URL = os.environ.get("CLASSIFIER_URL", "https://api.mohitchdev.me/agent/classify")

async def _probe_groups() -> List[Tuple[str, List[str]]]:
    base_groups = {
        "CONTENT_INJECTION": list(CONTENT_INJECTION),
        "SEMANTIC_MANIPULATION": list(SEMANTIC_MANIPULATION),
        "COGNITIVE_STATE": list(COGNITIVE_STATE),
        "BEHAVIOURAL_CONTROL": list(BEHAVIOURAL_CONTROL),
        "SYSTEMIC": list(SYSTEMIC),
        "HUMAN_IN_THE_LOOP": list(HUMAN_IN_THE_LOOP),
    }

    try:
        prisma = await get_db()
        custom_probes = await prisma.customprobe.find_many(where={"active": True})
        for cp in custom_probes:
            cat = cp.category.upper()
            if cat not in base_groups:
                base_groups[cat] = []
            base_groups[cat].append(cp.promptText)
    except Exception as e:
        print(f"Error loading custom probes: {e}")

    return [(cat, probes) for cat, probes in base_groups.items()]

async def _classify_probe(client: httpx.AsyncClient, prompt: str) -> Tuple[bool, Dict[str, Any], bool, str]:
    payload = {"prompt": prompt}
    try:
        resp = await client.post(CLASSIFIER_URL, json=payload, timeout=10)
        resp.raise_for_status()
        return True, resp.json(), False, ""
    except Exception as exc:
        return False, {"error": "classifier_unreachable"}, True, str(exc)

async def _invoke_agent(agent_id: str, prompt: str) -> str:
    """Forward an allowed prompt to the selected agent and return its response."""
    try:
        mod = get_agent(agent_id)
        return await mod.invoke(prompt)
    except Exception as exc:
        return f"Agent error ({agent_id}): {exc}"

async def run_scan(session_id: str, agent_id: str = DEFAULT_AGENT_ID) -> AsyncGenerator[Dict[str, Any], None]:
    prisma = await get_db()
    inspector = Inspector()
    
    # Save policy snapshot
    policy_yaml = ""
    try:
        with open("policy.yaml", "r") as f:
            policy_yaml = f.read()
    except:
        pass

    await prisma.policysnapshot.create(
        data={
            "session": {"connect": {"id": session_id}},
            "policyYaml": policy_yaml,
            "policyName": "agenttrap-policy",
            "version": "1.0"
        }
    )

    groups = await _probe_groups()
    total_probes = sum(len(probes) for _, probes in groups)
    
    blocked = 0
    allowed = 0
    mismatches = 0
    fired = 0
    
    yield {
        "event": "scan_start",
        "data": {
            "total_probes": total_probes
        }
    }

    async with httpx.AsyncClient() as client:
        for category, probes in groups:
            for idx, prompt in enumerate(probes, start=1):
                timestamp = datetime.now(timezone.utc)
                prompt_hash = sha256_hex(prompt)
                
                # 1. Inspect locally
                insp_result = inspector.process(prompt)
                regex_verdict = insp_result["policy_result"]["verdict"]
                regex_risk = insp_result["metadata"]["risk_score"]
                matched_rule = insp_result["policy_result"]["matched_rule"]
                
                # 2. Call ML Classifier
                clf_ok, clf_res, clf_err, clf_err_msg = await _classify_probe(client, prompt)
                clf_verdict = None
                clf_score = None
                
                if clf_ok:
                    clf_verdict = clf_res.get("verdict", "BENIGN").upper()
                    # extract score
                    for k in ("risk_score", "score", "risk", "probability"):
                        if k in clf_res:
                            clf_score = float(clf_res[k])
                            break
                            
                # 3. Determine status and mismatch
                status = "BLOCKED" if regex_verdict == "DENY" else "ALLOWED"
                
                # Mismatch logic: regex missed it (ALLOWED) but ML caught it (ADVERSARIAL)
                # Or regex blocked it but ML said BENIGN
                mismatch = False
                if regex_verdict == "ALLOW" and clf_verdict == "ADVERSARIAL":
                    mismatch = True
                elif regex_verdict == "DENY" and clf_verdict == "BENIGN":
                    mismatch = True
                    
                if status == "BLOCKED":
                    blocked += 1
                else:
                    allowed += 1
                    
                if mismatch:
                    mismatches += 1
                    
                # 4. Forward if allowed
                response_excerpt = ""
                if status == "ALLOWED":
                    response_excerpt = await _invoke_agent(agent_id, prompt)
                    # truncate response
                    if len(response_excerpt) > 500:
                        response_excerpt = response_excerpt[:497] + "..."
                        
                declared_intent = f"redteam:{category.lower()}"
                detected_intent = str(clf_res.get("detected_intent", "unknown")) if clf_ok else "unknown"

                event_hash_source = f"{session_id}{prompt_hash}{timestamp.isoformat()}"
                event_hash = sha256_hex(event_hash_source)

                # Write event to Prisma
                event = await prisma.probeevent.create(
                    data={
                        "session": {"connect": {"id": session_id}},
                        "timestamp": timestamp,
                        "category": category,
                        "probeIndex": idx,
                        "promptText": prompt,
                        "promptHash": prompt_hash,
                        "regexVerdict": regex_verdict,
                        "regexRiskScore": float(regex_risk),
                        "regexMetadata": Json(insp_result["metadata"]),
                        "matchedRule": matched_rule,
                        "classifierAvailable": not clf_err,
                        "classifierVerdict": clf_verdict,
                        "classifierScore": float(clf_score) if clf_score is not None else None,
                        "classifierResult": Json(clf_res) if clf_res else None,
                        "status": status,
                        "mismatch": mismatch,
                        "declaredIntent": declared_intent,
                        "detectedIntent": detected_intent,
                        "responseExcerpt": response_excerpt,
                        "eventHash": event_hash
                    }
                )
                
                fired += 1
                
                # Yield result for SSE
                yield {
                    "event": "probe_result",
                    "data": {
                        "category": category,
                        "index": idx,
                        "status": status,
                        "risk": regex_risk,
                        "mismatch": mismatch,
                        "matchedRule": matched_rule
                    }
                }
                
                # Small delay to prevent rate limits
                await asyncio.sleep(0.5)

    # Update session
    block_rate = blocked / fired if fired > 0 else 0.0
    await prisma.session.update(
        where={"id": session_id},
        data={
            "status": "COMPLETED",
            "finishedAt": datetime.now(timezone.utc),
            "totalProbes": fired,
            "blocked": blocked,
            "allowed": allowed,
            "mismatches": mismatches,
            "blockRate": block_rate
        }
    )
    
    yield {
        "event": "scan_complete",
        "data": {
            "total": fired,
            "blocked": blocked,
            "allowed": allowed,
            "mismatches": mismatches,
            "blockRate": block_rate
        }
    }
