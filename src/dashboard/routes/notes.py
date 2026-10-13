from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from src.database import get_engine
from src.models import SecurityNote, MatchResult

router = APIRouter()


@router.get("/notes", response_class=HTMLResponse)
async def notes_list(request: Request):
    token = request.cookies.get("session")
    if not token:
        return RedirectResponse(url="/login", status_code=303)
    auth = request.app.state.auth_manager
    username = auth.validate_session_token(token)
    if not username:
        return RedirectResponse(url="/login", status_code=303)

    db_path = request.app.state.db_path
    engine = get_engine(db_path)
    with Session(engine) as session:
        notes = session.query(SecurityNote).order_by(SecurityNote.cvss_score.desc()).all()
        notes_data = []
        for n in notes:
            match_count = session.query(MatchResult).filter_by(note_number=n.note_number).count()
            notes_data.append({"note": n, "match_count": match_count})

    templates = request.app.state.templates
    return templates.TemplateResponse(request, "notes/list.html", context={
        "username": username, "notes_data": notes_data
    })


@router.get("/notes/{note_number}", response_class=HTMLResponse)
async def note_detail(request: Request, note_number: str):
    token = request.cookies.get("session")
    if not token:
        return RedirectResponse(url="/login", status_code=303)
    auth = request.app.state.auth_manager
    username = auth.validate_session_token(token)
    if not username:
        return RedirectResponse(url="/login", status_code=303)

    db_path = request.app.state.db_path
    engine = get_engine(db_path)
    with Session(engine) as session:
        note = session.query(SecurityNote).filter_by(note_number=note_number).first()
        matches = session.query(MatchResult).filter_by(note_number=note_number)\
            .order_by(MatchResult.priority_score.desc()).all()

    templates = request.app.state.templates
    return templates.TemplateResponse(request, "notes/detail.html", context={
        "username": username, "note": note, "matches": matches
    })


@router.post("/notes/{note_number}/approve/{match_id}")
async def approve_match(request: Request, note_number: str, match_id: int):
    token = request.cookies.get("session")
    if not token:
        return RedirectResponse(url="/login", status_code=303)
    auth = request.app.state.auth_manager
    username = auth.validate_session_token(token)
    if not username:
        return RedirectResponse(url="/login", status_code=303)

    db_path = request.app.state.db_path
    engine = get_engine(db_path)
    with Session(engine) as session:
        match = session.get(MatchResult, match_id)
        if match:
            match.status = "approved"
            session.commit()
    return RedirectResponse(url=f"/notes/{note_number}", status_code=303)


@router.post("/notes/{note_number}/dismiss/{match_id}")
async def dismiss_match(request: Request, note_number: str, match_id: int):
    token = request.cookies.get("session")
    if not token:
        return RedirectResponse(url="/login", status_code=303)
    auth = request.app.state.auth_manager
    username = auth.validate_session_token(token)
    if not username:
        return RedirectResponse(url="/login", status_code=303)

    db_path = request.app.state.db_path
    engine = get_engine(db_path)
    from datetime import datetime
    with Session(engine) as session:
        match = session.get(MatchResult, match_id)
        if match:
            match.status = "dismissed"
            match.dismissed_by = username
            match.dismissed_at = datetime.utcnow()
            session.commit()
    return RedirectResponse(url=f"/notes/{note_number}", status_code=303)
