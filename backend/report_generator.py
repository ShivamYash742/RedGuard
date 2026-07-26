import os
import json
from collections import defaultdict
from datetime import datetime, timezone
from database import get_db
from prisma import Json
from schema import sha256_hex

async def generate_report_for_session(session_id: str) -> dict:
    prisma = await get_db()
    
    # Fetch session and events
    session = await prisma.session.find_unique(
        where={"id": session_id},
        include={"events": True}
    )
    
    if not session:
        return {"error": "Session not found"}
        
    events = session.events
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
        c_blocked = sum(1 for e in group if e.status == "BLOCKED")
        c_allowed = c_total - c_blocked
        c_mismatch = sum(1 for e in group if e.mismatch)
        c_top_risk = max([e.regexRiskScore for e in group] + [0.0])
        
        category_breakdown.append({
            "category": category,
            "probes": c_total,
            "blocked": c_blocked,
            "allowed": c_allowed,
            "mismatches": c_mismatch,
            "highest_risk_score": round(c_top_risk, 4)
        })
        
        for e in group:
            if e.status == "ALLOWED" and (e.regexRiskScore > 0.5 or e.classifierVerdict == "ADVERSARIAL"):
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
                
            if e.status == "BLOCKED":
                blocked_with_rules.append({
                    "event_hash": e.eventHash,
                    "category": e.category,
                    "rule": e.matchedRule or "unknown"
                })

    report_json = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall": {
            "total_probes": total_probes,
            "blocked": blocked,
            "allowed": allowed,
            "mismatches": mismatches,
            "block_rate": block_rate,
            "session_id": session.sessionId
        },
        "category_breakdown": category_breakdown,
        "high_risk_allowed": high_risk_allowed,
        "intent_mismatches": intent_mismatches,
        "blocked_with_rules": blocked_with_rules
    }
    
    # Generate Markdown
    md = [
        f"# RedGuard Security Report",
        f"**Session ID:** `{session.sessionId}`",
        f"**Date:** `{session.startedAt}`",
        "",
        "## Executive Summary",
        f"- **Total Probes Fired:** {total_probes}",
        f"- **Blocked:** {blocked}",
        f"- **Allowed (Gap):** {allowed}",
        f"- **Block Rate:** {block_rate * 100:.1f}%",
        f"- **Mismatches:** {mismatches}",
        "",
        "## Category Breakdown",
        "| Category | Probes | Blocked | Allowed | Mismatches | Max Risk |",
        "|---|---|---|---|---|---|"
    ]
    
    for cb in category_breakdown:
        md.append(f"| {cb['category']} | {cb['probes']} | {cb['blocked']} | {cb['allowed']} | {cb['mismatches']} | {cb['highest_risk_score']} |")
        
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
    
    # Save to DB
    await prisma.report.create(
        data={
            "session": {"connect": {"id": session.id}},
            "generatedAt": datetime.now(timezone.utc),
            "reportJson": Json(report_json),
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
