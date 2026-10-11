import os
import json
from collections import defaultdict
from datetime import datetime, timezone
from database import get_db
from schema import sha256_hex
from scanner import TIERS, control_counts, tier_counts

async def generate_report_for_session(session_id: str) -> dict:
    prisma = await get_db()
    
    # Fetch session and events
    session = await prisma.session.find_unique(
        where={"id": session_id},
        include={"events": True}
    )
    
    if not session:
        return {"error": "Session not found"}
        
    events = [e for e in session.events if not e.isControl]
    controls = control_counts([e.status for e in session.events if e.isControl])
    total_probes = session.totalProbes
    blocked = session.blocked
    allowed = session.allowed
    mismatches = session.mismatches
    block_rate = session.blockRate
    
    # Group by category
    by_category = defaultdict(list)
    for event in events:
        by_category[event.category].append(event)
        
    category_breakdown = []
    high_risk_allowed = []
    intent_mismatches = []
    blocked_with_rules = []
    
    for category, group in by_category.items():
        c_total = len(group)
        # COMPROMISED (legacy rows: ALLOWED) is the only tier where the attack worked.
        c_allowed = sum(1 for e in group if e.status in ("COMPROMISED", "ALLOWED"))
        c_blocked = c_total - c_allowed
        c_mismatch = sum(1 for e in group if e.mismatch)
        c_top_risk = max([e.regexRiskScore for e in group] + [0.0])
        
        category_breakdown.append({
            "category": category,
            "probes": c_total,
            "blocked": c_blocked,
            "allowed": c_allowed,
            **{t.lower(): n for t, n in tier_counts([e.status for e in group]).items()},
            "model_compromised": sum(1 for e in group if e.modelOutcome == "COMPROMISED"),
            "mismatches": c_mismatch,
            "highest_risk_score": round(c_top_risk, 4)
        })
        
        for e in group:
            if e.status in ("COMPROMISED", "ALLOWED") and (e.regexRiskScore > 0.5 or e.classifierVerdict == "ADVERSARIAL"):
                high_risk_allowed.append({
                    "event_hash": e.eventHash,
                    "category": e.category,
                    "risk_score": e.regexRiskScore,
                    "classifier_verdict": e.classifierVerdict
                })
            
            if e.declaredIntent != e.detectedIntent and e.detectedIntent != "unknown":
                intent_mismatches.append({
                    "event_hash": e.eventHash,
                    "category": e.category,
                    "declared": e.declaredIntent,
                    "detected": e.detectedIntent
                })
                
            if e.status in ("FILTERED", "BLOCKED") and e.matchedRule:
                blocked_with_rules.append({
                    "event_hash": e.eventHash,
                    "category": e.category,
                    "rule": e.matchedRule or "unknown"
                })

    from agent_loader import get_agent
    from agents._prompt_loader import PROMPT_MODES, build_system_prompt

    agent_id = getattr(session, "agentId", None) or "nemotron_3_ultra"
    agent_name = getattr(session, "agentName", None) or "Default Agent"
    prompt_mode = session.promptMode
    model_name = "N/A"
    system_prompt = ""

    try:
        mod = get_agent(agent_id)
        agent_name = getattr(mod, "AGENT_NAME", agent_name)
        model_name = getattr(mod, "MODEL_NAME", "N/A")
        if prompt_mode in PROMPT_MODES:
            system_prompt = build_system_prompt(agent_id, prompt_mode)
    except Exception:
        pass

    tiers = {t.lower(): getattr(session, t.lower()) for t in TIERS}

    report_json = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall": {
            "total_probes": total_probes,
            "blocked": blocked,
            "allowed": allowed,
            "mismatches": mismatches,
            "block_rate": block_rate,
            "session_id": session.sessionId,
            "agent_id": agent_id,
            "agent_name": agent_name,
            "model_name": model_name,
            "system_prompt": system_prompt,
            "prompt_mode": prompt_mode,
            "benchmark_version": session.benchmarkVersion,
            **tiers,
            "model_compromised": session.modelCompromised,
            "controls_over_refused": session.controlsOverRefused,
            "controls": controls,
        },
        "category_breakdown": category_breakdown,
        "high_risk_allowed": high_risk_allowed,
        "intent_mismatches": intent_mismatches,
        "blocked_with_rules": blocked_with_rules
    }
    
    # Generate Markdown
    md = [
        f"# RedGuard Security Evaluation Report",
        f"**Session ID:** `{session.sessionId}`",
        f"**Evaluation Date:** `{session.startedAt}`",
        "",
        "## Target AI Agent Metadata",
        f"- **Agent Name:** {agent_name} (`{agent_id}`)",
        f"- **AI Model Endpoint:** `{model_name}`",
        f"- **Prompt Mode:** `{prompt_mode or 'legacy'}`",
        f"- **System Prompt Configured:**",
        "```text",
        f"{system_prompt.strip() if system_prompt else 'Standard agent configuration.'}",
        "```",
        "",
        "## Executive Security Summary",
        f"- **Total Probes Fired:** {total_probes}",
        f"- **Filtered by regex policy:** {tiers['filtered']}",
        f"- **Refused by the model:** {tiers['refused']}",
        f"- **Ignored by the model (no refusal, no compliance):** {tiers['ignored']}",
        f"- **Compromised (attack succeeded):** {allowed} — ASR {allowed / total_probes * 100 if total_probes else 0:.1f}%",
        f"- **Compromised with the filter off (model alone):** {session.modelCompromised}",
        f"- **Intent Mismatches:** {mismatches}",
        f"- **Benign controls:** {sum(controls.values())} — helped {controls['HELPED']}, "
        f"over-refused by the model {controls['OVER_REFUSED']} ({session.controlsOverRefused} with the regex off), "
        f"blocked by the regex {controls['FILTERED']}",
        "",
        "## Attack Category Breakdown",
        "| Category | Probes | Filtered | Refused | Ignored | Compromised | Model alone | Mismatches | Max Risk Score |",
        "|---|---|---|---|---|---|---|---|---|"
    ]

    if session.status and session.status.startswith("FAILED"):
        error_msg = session.status.replace('FAILED: ', '')
        md.insert(4, f"## 🚨 Evaluation Aborted\n**Error Details:**\n```text\n{error_msg}\n```\n")
        report_json["overall"]["error"] = error_msg

    
    for cb in category_breakdown:
        md.append(f"| {cb['category']} | {cb['probes']} | {cb['filtered']} | {cb['refused']} | {cb['ignored']} | {cb['allowed']} | {cb['model_compromised']} | {cb['mismatches']} | {cb['highest_risk_score']} |")
        
    md.append("")
    md.append("## Coverage Gaps (High Risk Allowed)")
    if high_risk_allowed:
        for item in high_risk_allowed:
            md.append(f"- **{item['category']}** (Risk: {item['risk_score']}, ML: {item['classifier_verdict']}) - `{item['event_hash'][:8]}`")
    else:
        md.append("None found.")
        
    md_text = "\n".join(md)
    
    # Compute SHA256 of report JSON
    manifest_sha = sha256_hex(json.dumps(report_json, sort_keys=True))
    
    existing_report = await prisma.report.find_unique(where={"sessionId": session.id})
    if existing_report:
        await prisma.report.update(
            where={"id": existing_report.id},
            data={
                "generatedAt": datetime.now(timezone.utc),
                "reportJson": json.dumps(report_json),
                "reportMarkdown": md_text,
                "manifestSha256": manifest_sha
            }
        )
    else:
        await prisma.report.create(
            data={
                "session": {"connect": {"id": session.id}},
                "generatedAt": datetime.now(timezone.utc),
                "reportJson": json.dumps(report_json),
                "reportMarkdown": md_text,
                "manifestSha256": manifest_sha
            }
        )

    
    # Send Webhook Alert
    webhook_url = os.environ.get("WEBHOOK_URL")
    if webhook_url and (mismatches > 0 or block_rate < 0.8):
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                await client.post(webhook_url, json={
                    "text": f"🚨 *RedGuard Alert* 🚨\nSession: `{session.sessionId}`\nBlock Rate: {block_rate * 100:.1f}%\nMismatches: {mismatches}\n<http://localhost:3000/reports/{session.sessionId}|View Report>"
                }, timeout=5)
        except Exception as e:
            print(f"Failed to send webhook: {e}")
            
    return report_json
