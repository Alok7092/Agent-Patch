import json
from datetime import datetime
from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from src.database import get_engine
from src.models import SecurityNote, MatchResult, AIAnalysis

router = APIRouter(prefix="/api")


@router.post("/notes/{note_number}/approve")
async def approve_note(request: Request, note_number: str):
    token = request.cookies.get("session")
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    auth = request.app.state.auth_manager
    username = auth.validate_session_token(token)
    if not username:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    db_path = request.app.state.db_path
    engine = get_engine(db_path)
    with Session(engine) as session:
        matches = session.query(MatchResult).filter(
            MatchResult.note_number == note_number,
            MatchResult.status.in_(["pending", "ready_for_approval", "manual_review"]),
        ).all()
        for m in matches:
            m.status = "approved"
        session.commit()
    return JSONResponse({"status": "approved", "note_number": note_number})


@router.post("/notes/{note_number}/dismiss")
async def dismiss_note(request: Request, note_number: str):
    token = request.cookies.get("session")
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    auth = request.app.state.auth_manager
    username = auth.validate_session_token(token)
    if not username:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    db_path = request.app.state.db_path
    engine = get_engine(db_path)
    with Session(engine) as session:
        matches = session.query(MatchResult).filter(
            MatchResult.note_number == note_number,
            MatchResult.status.in_(["pending", "ready_for_approval", "manual_review"]),
        ).all()
        for m in matches:
            m.status = "dismissed"
            m.dismissed_by = username
            m.dismissed_at = datetime.utcnow()
        session.commit()
    return JSONResponse({"status": "dismissed", "note_number": note_number})


@router.post("/notes/{note_number}/defer")
async def defer_note(request: Request, note_number: str):
    token = request.cookies.get("session")
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    auth = request.app.state.auth_manager
    username = auth.validate_session_token(token)
    if not username:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    db_path = request.app.state.db_path
    engine = get_engine(db_path)
    with Session(engine) as session:
        matches = session.query(MatchResult).filter(
            MatchResult.note_number == note_number,
            MatchResult.status.in_(["pending", "ready_for_approval", "manual_review"]),
        ).all()
        for m in matches:
            m.status = "deferred"
        session.commit()
    return JSONResponse({"status": "deferred", "note_number": note_number})


@router.get("/status")
async def get_status(request: Request):
    token = request.cookies.get("session")
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    auth = request.app.state.auth_manager
    username = auth.validate_session_token(token)
    if not username:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    db_path = request.app.state.db_path
    engine = get_engine(db_path)
    with Session(engine) as session:
        total_notes = session.query(SecurityNote).count()
        total_matches = session.query(MatchResult).count()
        pending = session.query(MatchResult).filter_by(status="pending").count()
        approved = session.query(MatchResult).filter_by(status="approved").count()
        dismissed = session.query(MatchResult).filter_by(status="dismissed").count()
        ready_for_approval = session.query(MatchResult).filter_by(status="ready_for_approval").count()
        not_applicable = session.query(MatchResult).filter_by(status="not_applicable").count()
        manual_review = session.query(MatchResult).filter_by(status="manual_review").count()

    return JSONResponse({
        "total_notes": total_notes,
        "total_matches": total_matches,
        "pending": pending,
        "approved": approved,
        "dismissed": dismissed,
        "ready_for_approval": ready_for_approval,
        "not_applicable": not_applicable,
        "manual_review": manual_review,
    })


@router.post("/notes/upload")
async def upload_notes(request: Request, file: UploadFile = File(...)):
    token = request.cookies.get("session")
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    auth = request.app.state.auth_manager
    username = auth.validate_session_token(token)
    if not username:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    content = await file.read()

    from src.ingestion.sap_excel import parse_sap_excel
    try:
        parsed_notes = parse_sap_excel(content)
    except Exception as e:
        return JSONResponse({"error": f"Failed to parse file: {str(e)}"}, status_code=400)

    db_path = request.app.state.db_path
    engine = get_engine(db_path)
    imported = 0
    skipped = 0

    with Session(engine) as session:
        for pn in parsed_notes:
            existing = session.query(SecurityNote).filter_by(note_number=pn.note_number).first()
            if existing:
                skipped += 1
                continue
            note = SecurityNote(
                note_number=pn.note_number,
                title=pn.title,
                cvss_score=pn.cvss_score,
                cvss_vector=pn.cvss_vector,
                priority=pn.priority,
                components=json.dumps(pn.components),
                version_ranges=json.dumps([]),
                release_date=datetime.strptime(pn.release_date, "%Y-%m-%d").date() if pn.release_date else None,
                description=pn.description,
                solution_type=pn.solution_type,
                raw_content=pn.raw_content,
                status="new",
            )
            session.add(note)
            imported += 1
        session.commit()

    # Auto-run analysis if landscape exists
    if imported > 0:
        try:
            from src.shared.scheduling import _scheduled_analysis
            import asyncio
            await _scheduled_analysis(request.app)
        except Exception:
            pass

    return JSONResponse({
        "status": "ok",
        "imported": imported,
        "skipped": skipped,
        "total": len(parsed_notes),
    })


@router.post("/notes/fetch-latest")
async def fetch_latest_notes(request: Request):
    token = request.cookies.get("session")
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    auth = request.app.state.auth_manager
    username = auth.validate_session_token(token)
    if not username:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    import os
    sap_username = os.environ.get("SAP_USERNAME", "")
    sap_password = os.environ.get("SAP_PASSWORD", "")
    if not sap_username or not sap_password:
        return JSONResponse({"error": "SAP credentials not configured. Set SAP_USERNAME and SAP_PASSWORD environment variables."}, status_code=400)

    # Use Playwright-based SAP MCP to fetch notes from me.sap.com/securitynotes
    # Must run in a separate thread with its own event loop (Playwright subprocess issue on Windows)
    os.environ["SAP_USERNAME"] = sap_username
    os.environ["SAP_PASSWORD"] = sap_password

    import asyncio

    def _run_playwright_fetch():
        """Run Playwright fetch in a new event loop (required for Windows uvicorn)."""
        import asyncio as _asyncio
        loop = _asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_do_fetch())
        finally:
            loop.close()

    async def _do_fetch():
        from src.mcp_sap_notes.server import fetch_security_notes
        result_json = await fetch_security_notes()
        result = json.loads(result_json)
        return result

    try:
        result = await asyncio.to_thread(_run_playwright_fetch)
        if result.get("status") != "ok":
            return JSONResponse({"error": f"Failed to fetch: {result.get('error', 'unknown')}"}, status_code=500)
        fetched_notes = result.get("notes", [])
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        return JSONResponse({"error": f"Failed to fetch from SAP: {type(e).__name__}: {str(e) or tb[-300:]}"}, status_code=500)

    # Store in DB
    db_path = request.app.state.db_path
    engine = get_engine(db_path)
    imported = 0
    skipped = 0

    with Session(engine) as session:
        for n in fetched_notes:
            note_number = n.get("number", "")
            if not note_number:
                continue
            existing = session.query(SecurityNote).filter_by(note_number=note_number).first()
            if existing:
                skipped += 1
                continue

            # Normalize priority
            priority_raw = n.get("priority", "medium")
            priority_map = {"hotnews": "hot_news", "correction with high priority": "high",
                           "correction with medium priority": "medium", "correction with low priority": "low"}
            priority = priority_map.get(priority_raw.lower(), "medium")

            # Parse release date (DD.MM.YYYY format)
            release_date = None
            rd = n.get("released_on", "")
            if rd:
                import re as _re
                dm = _re.match(r'(\d{2})\.(\d{2})\.(\d{4})', rd)
                if dm:
                    release_date = datetime(int(dm.group(3)), int(dm.group(2)), int(dm.group(1))).date()

            # Build components list and version ranges from support_packages (SP-level matching)
            components = [n.get("component", "")]
            sw_comps = n.get("software_components", [])
            sp_patches = n.get("support_packages", [])
            version_ranges = []

            # Add component names from software_components section
            for sc in sw_comps:
                comp = sc.get("component", sc.get("raw", ""))
                if not comp or len(comp) > 30 or "|" in comp or "\t" in comp:
                    continue
                if comp not in components:
                    components.append(comp)

            # Extract version ranges ONLY from support_packages (has SP level for precise matching)
            # Entries like: "SAP KERNEL 7.53 64-BIT UNICODE" with sp_level "001538"
            import re as _re
            sp_name_map = {
                "SAP KERNEL": "KRNL64UC",
                "SAPROUTER": "SAP_ROUTER",
                "LM CONFIGURATION WIZARD": "LMCTC",
                "EP RUNTIME": "EP-RUNTIME",
                "J2EE ENGINE CORE TOOLS": "CORE-TOOLS",
                "J2EE ENGINE SERVER CORE": "SERVERCORE",
                "J2EE ENGINE APPS": "J2EE-APPS",
                "SAP HANA DATABASE": "HDB",
            }
            seen_ranges = set()
            for sp in sp_patches:
                sp_name = sp.get("software_component", sp.get("raw", ""))
                sp_level_str = sp.get("sp_level", sp.get("patch_level", ""))
                if not sp_name or not sp_level_str:
                    continue
                # Extract SP level as integer
                sp_num = _re.sub(r'[^0-9]', '', sp_level_str)
                if not sp_num:
                    continue
                fix_sp = int(sp_num)
                if fix_sp == 0:
                    continue
                # Extract version from SP name
                ver_match = _re.search(r'(\d+\.?\d+)', sp_name)
                if not ver_match:
                    continue
                ver_str = ver_match.group(1)
                try:
                    v_int = int(ver_str.replace(".", ""))
                except ValueError:
                    continue
                # Determine component code
                matched_comp = None
                sp_upper = sp_name.upper()
                for display_name, comp_code in sp_name_map.items():
                    if display_name.upper() in sp_upper:
                        matched_comp = comp_code
                        break
                if not matched_comp:
                    prefix = sp_name[:sp_name.find(ver_str)].strip().rstrip()
                    if prefix and len(prefix) <= 30 and _re.match(r'^[A-Z0-9_\- ]+$', prefix, _re.IGNORECASE):
                        simple = prefix.split()[0] if " " in prefix else prefix
                        if simple and len(simple) <= 20:
                            matched_comp = simple.upper()
                if matched_comp:
                    range_key = f"{matched_comp}:{v_int}:{fix_sp}"
                    if range_key not in seen_ranges:
                        seen_ranges.add(range_key)
                        version_ranges.append({"component": matched_comp, "min": v_int, "max": v_int, "fix_sp": fix_sp})
                    if matched_comp not in components:
                        components.append(matched_comp)

            cvss_score = 0.0
            try:
                cvss_score = float(n.get("cvss_score", 0))
            except (ValueError, TypeError):
                pass

            note = SecurityNote(
                note_number=note_number,
                title=n.get("title", ""),
                cvss_score=cvss_score,
                cvss_vector=n.get("cvss_vector", ""),
                priority=priority,
                components=json.dumps([c for c in components if c]),
                version_ranges=json.dumps(version_ranges),
                release_date=release_date,
                description=n.get("title", ""),
                solution_type=n.get("category", ""),
                raw_content=json.dumps({
                    "support_packages": n.get("support_packages", []),
                    "software_components": n.get("software_components", []),
                    "sections": n.get("sections", []),
                }),
                status="new",
            )
            session.add(note)
            imported += 1
        session.commit()

    if imported > 0:
        try:
            from src.shared.scheduling import _scheduled_analysis
            await _scheduled_analysis(request.app)
        except Exception as e:
            import traceback
            print(f"[Analysis error] {type(e).__name__}: {e}")
            traceback.print_exc()

    return JSONResponse({
        "status": "ok",
        "fetched": len(fetched_notes),
        "imported": imported,
        "skipped": skipped,
    })


@router.get("/landscape/data")
async def get_landscape_data(request: Request):
    from src.models import LandscapeSnapshot, LandscapeEntry
    db_path = request.app.state.db_path
    engine = get_engine(db_path)
    with Session(engine) as session:
        snapshot = session.query(LandscapeSnapshot).filter_by(is_active=True).first()
        if not snapshot:
            return JSONResponse({"snapshot": None, "entries": [], "columns": []})

        entries = session.query(LandscapeEntry).filter_by(snapshot_id=snapshot.id).all()
        rows = []
        for e in entries:
            rows.append({
                "sid": e.sid or "",
                "component_code": e.component_code or "",
                "version": e.version or "",
                "tier": e.tier or "",
                "sp": e.notes.replace("SP: ", "") if e.notes and e.notes.startswith("SP:") else "",
                "description": e.description or "",
                "product": e.product or "",
            })

        # Determine which columns have data
        columns = []
        col_defs = [
            {"key": "sid", "label": "System ID"},
            {"key": "component_code", "label": "Component"},
            {"key": "version", "label": "Version"},
            {"key": "sp", "label": "SP Level"},
            {"key": "tier", "label": "Tier"},
            {"key": "description", "label": "Description"},
            {"key": "product", "label": "Product"},
        ]
        for col in col_defs:
            if any(row.get(col["key"]) for row in rows):
                columns.append(col)

        unique_sids = len(set(r["sid"] for r in rows))
        unique_comps = len(set(r["component_code"] for r in rows))

    return JSONResponse({
        "snapshot": {
            "filename": snapshot.filename,
            "system_count": unique_sids,
            "component_count": unique_comps,
            "entry_count": len(rows),
            "uploaded_at": str(snapshot.uploaded_at) if snapshot.uploaded_at else "",
        },
        "columns": columns,
        "entries": rows,
    })


@router.get("/notes/{note_number}/review")
async def get_review_details(request: Request, note_number: str):
    token = request.cookies.get("session")
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    auth = request.app.state.auth_manager
    username = auth.validate_session_token(token)
    if not username:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    db_path = request.app.state.db_path
    engine = get_engine(db_path)
    with Session(engine) as session:
        ai_analysis = (
            session.query(AIAnalysis)
            .filter_by(note_number=note_number)
            .order_by(AIAnalysis.created_at.desc())
            .first()
        )
        if not ai_analysis:
            return JSONResponse({"error": "No AI analysis found"}, status_code=404)

        review_items = []
        triggers = json.loads(ai_analysis.manual_review_triggers) if ai_analysis.manual_review_triggers else []
        evidence = json.loads(ai_analysis.evidence) if ai_analysis.evidence else []
        unknowns = json.loads(ai_analysis.critical_unknowns) if ai_analysis.critical_unknowns else []
        assumptions = json.loads(ai_analysis.assumptions) if ai_analysis.assumptions else []
        contradictions = json.loads(ai_analysis.contradictions) if ai_analysis.contradictions else []

        from src.matching.models import MANUAL_REVIEW_CODES
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
                    "question": f"{desc} — please review and confirm applicability.",
                    "options": ["Applicable", "Not applicable", "Unable to determine"],
                })

    return JSONResponse({
        "note_number": note_number,
        "decision": ai_analysis.decision,
        "decision_confidence": ai_analysis.decision_confidence,
        "evidence_coverage": ai_analysis.evidence_coverage,
        "gate_outcome": ai_analysis.gate_outcome,
        "gate_reason": ai_analysis.gate_reason,
        "evidence": evidence,
        "critical_unknowns": unknowns,
        "assumptions": assumptions,
        "contradictions": contradictions,
        "review_items": review_items,
    })


@router.post("/notes/{note_number}/review")
async def submit_review(request: Request, note_number: str):
    token = request.cookies.get("session")
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    auth = request.app.state.auth_manager
    username = auth.validate_session_token(token)
    if not username:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    body = await request.json()
    review_code = body.get("review_code", "")
    answer = body.get("answer", "")
    action = body.get("action", "approve")

    db_path = request.app.state.db_path
    engine = get_engine(db_path)
    with Session(engine) as session:
        matches = session.query(MatchResult).filter(
            MatchResult.note_number == note_number,
            MatchResult.status == "manual_review",
        ).all()

        status_map = {"approve": "approved", "dismiss": "dismissed", "escalate": "deferred"}
        new_status = status_map.get(action, "approved")

        for m in matches:
            m.status = new_status
            m.review_response = json.dumps({"code": review_code, "answer": answer})
            m.reviewed_by = username
            m.reviewed_at = datetime.utcnow()
            if new_status == "dismissed":
                m.dismissed_by = username
                m.dismissed_at = datetime.utcnow()
        session.commit()

    return JSONResponse({
        "status": new_status,
        "note_number": note_number,
        "reviewed_by": username,
    })


@router.post("/landscape/upload")
async def upload_landscape(request: Request, file: UploadFile = File(...)):
    token = request.cookies.get("session")
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    auth = request.app.state.auth_manager
    username = auth.validate_session_token(token)
    if not username:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    content = await file.read()

    from src.ingestion.sap_landscape_excel import parse_sap_landscape_excel
    try:
        entries = parse_sap_landscape_excel(content)
    except Exception as e:
        return JSONResponse({"error": f"Failed to parse file: {str(e)}"}, status_code=400)

    from src.models import LandscapeSnapshot, LandscapeEntry
    db_path = request.app.state.db_path
    engine = get_engine(db_path)

    with Session(engine) as session:
        session.query(LandscapeSnapshot).update({"is_active": False})
        unique_sids = set(e["sid"] for e in entries)
        unique_comps = set(e["component_code"] for e in entries)

        snapshot = LandscapeSnapshot(
            filename=file.filename,
            system_count=len(unique_sids),
            component_count=len(unique_comps),
            is_active=True,
        )
        session.add(snapshot)
        session.flush()

        for e in entries:
            entry = LandscapeEntry(
                snapshot_id=snapshot.id,
                sid=e["sid"],
                description=e["description"],
                product=e["product"],
                component_code=e["component_code"],
                version=e["version"],
                version_numeric=e["version_numeric"],
                kernel_release=e["kernel_release"],
                tier=e["tier"],
                os=e["os"],
                db=e["db"],
                business_unit=e["business_unit"],
                basis_contact=e["basis_contact"],
                notes=e["notes"],
            )
            session.add(entry)
        session.commit()

    return JSONResponse({
        "status": "ok",
        "systems": len(unique_sids),
        "components": len(unique_comps),
        "entries": len(entries),
    })
