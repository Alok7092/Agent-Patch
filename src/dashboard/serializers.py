import json
from src.models import SecurityNote, MatchResult, LandscapeEntry, AIAnalysis


def serialize_landscape(entries: list[LandscapeEntry]) -> list[dict]:
    seen = {}
    for e in entries:
        if e.sid not in seen:
            seen[e.sid] = {
                "sid": e.sid,
                "tier": e.tier or "",
                "role": e.description or e.product or "",
                "comp": f"{e.component_code} {e.version}" if e.component_code else "",
                "owner": e.basis_contact or "",
            }
    return list(seen.values())


def serialize_notes(
    notes: list[SecurityNote],
    matches: list[MatchResult],
    landscape_entries: list[LandscapeEntry] = None,
    ai_analyses: list[AIAnalysis] = None,
) -> list[dict]:
    matches_by_note = {}
    for m in matches:
        matches_by_note.setdefault(m.note_number, []).append(m)

    ai_by_note = {}
    if ai_analyses:
        for a in ai_analyses:
            if a.note_number not in ai_by_note:
                ai_by_note[a.note_number] = a

    sp_lookup = {}
    if landscape_entries:
        for e in landscape_entries:
            if e.sid and e.component_code:
                sp = e.notes.replace("SP: ", "") if e.notes and e.notes.startswith("SP:") else ""
                sp_lookup[(e.sid, e.component_code)] = sp

    result = []
    for n in notes:
        note_matches = matches_by_note.get(n.note_number, [])
        sev_map = {"hot_news": "Hot News", "high": "High", "medium": "Medium", "low": "Low"}
        sev = sev_map.get(n.priority, "Medium")

        match_list = []
        for m in note_matches:
            sp = sp_lookup.get((m.sid, m.component), "") if sp_lookup else ""
            match_list.append({
                "sid": m.sid,
                "source": "rule" if m.match_source == "rules_engine" else "ai",
                "component": m.component or "",
                "version": m.system_version or "",
                "sp": sp,
                "desc": f"{m.component} {m.system_version}".strip(),
                "reason": m.match_reason or "",
                "gate_outcome": m.gate_outcome or "",
                "review_code": m.manual_review_code or "",
                "status": m.status or "pending",
            })

        components = json.loads(n.components) if n.components else []
        version_ranges = json.loads(n.version_ranges) if n.version_ranges else []
        raw = json.loads(n.raw_content) if n.raw_content else {}
        sections = raw.get("sections", [])

        # AI analysis metadata
        ai = ai_by_note.get(n.note_number)
        ai_data = None
        if ai:
            evidence = json.loads(ai.evidence) if ai.evidence else []
            unknowns = json.loads(ai.critical_unknowns) if ai.critical_unknowns else []
            assumptions = json.loads(ai.assumptions) if ai.assumptions else []
            contradictions = json.loads(ai.contradictions) if ai.contradictions else []
            triggers = json.loads(ai.manual_review_triggers) if ai.manual_review_triggers else []

            from src.matching.models import MANUAL_REVIEW_CODES
            review_items = []
            confirmed = [f"{e['claim']}: {e['value']}" for e in evidence]
            for code in triggers:
                desc = MANUAL_REVIEW_CODES.get(code, "Unknown")
                if code == "MR-01" and unknowns:
                    for u in unknowns:
                        review_items.append({
                            "code": code, "description": desc,
                            "confirmed": confirmed,
                            "question": f"Can you confirm: {u}",
                            "options": ["Yes", "No", "Unable to determine"],
                        })
                elif code == "MR-02" and contradictions:
                    for c in contradictions:
                        review_items.append({
                            "code": code, "description": desc,
                            "confirmed": confirmed,
                            "question": f"Evidence conflict: {c}. Which is correct?",
                            "options": ["First source", "Second source", "Unable to determine"],
                        })
                elif code == "MR-06" and assumptions:
                    for a in assumptions:
                        review_items.append({
                            "code": code, "description": desc,
                            "confirmed": confirmed,
                            "question": f"Assumption: {a}. Is this correct?",
                            "options": ["Yes, confirmed", "No, incorrect", "Unable to determine"],
                        })
                else:
                    review_items.append({
                        "code": code, "description": desc,
                        "confirmed": confirmed,
                        "question": f"{desc} — please review.",
                        "options": ["Applicable", "Not applicable", "Unable to determine"],
                    })

            ai_data = {
                "decision": ai.decision,
                "confidence": ai.decision_confidence,
                "evidence_coverage": ai.evidence_coverage,
                "gate_outcome": ai.gate_outcome,
                "gate_reason": ai.gate_reason,
                "evidence": evidence,
                "critical_unknowns": unknowns,
                "assumptions": assumptions,
                "contradictions": contradictions,
                "review_items": review_items,
            }

        note_obj = {
            "id": n.note_number,
            "sev": sev,
            "cvss": n.cvss_score or 0.0,
            "cve": n.cvss_vector or "",
            "vector": "",
            "title": n.title or "",
            "component": components[0] if components else "",
            "solution": n.solution_type or "SNOTE correction",
            "released": str(n.release_date) if n.release_date else "",
            "effort": "",
            "target": "ServiceNow",
            "summary": n.description or "",
            "sections": sections,
            "matches": match_list,
            "steps": [],
            "ai": ai_data,
        }

        if not match_list:
            note_obj["noimpact"] = True

        result.append(note_obj)

    return result


def serialize_decisions(matches: list[MatchResult]) -> dict:
    decisions = {}
    for m in matches:
        if m.status in ("approved", "dismissed", "ready_for_approval", "not_applicable", "manual_review", "deferred"):
            existing = decisions.get(m.note_number)
            if not existing:
                decisions[m.note_number] = m.status
    return decisions
