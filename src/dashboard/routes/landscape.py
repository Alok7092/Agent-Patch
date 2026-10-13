from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from src.database import get_engine
from src.models import LandscapeSnapshot, LandscapeEntry
from src.landscape.loader import load_spreadsheet
from src.landscape.normalizer import normalize_entry

router = APIRouter()


@router.get("/landscape", response_class=HTMLResponse)
async def landscape_view(request: Request):
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
        snapshot = session.query(LandscapeSnapshot).filter_by(is_active=True).first()
        entries = []
        if snapshot:
            entries = session.query(LandscapeEntry).filter_by(snapshot_id=snapshot.id).all()

    templates = request.app.state.templates
    return templates.TemplateResponse(request, "landscape/view.html", context={
        "username": username, "snapshot": snapshot, "entries": entries,
    })


@router.post("/landscape/upload")
async def landscape_upload(request: Request, file: UploadFile = File(...)):
    token = request.cookies.get("session")
    if not token:
        return RedirectResponse(url="/login", status_code=303)
    auth = request.app.state.auth_manager
    username = auth.validate_session_token(token)
    if not username:
        return RedirectResponse(url="/login", status_code=303)

    content = await file.read()
    rows = load_spreadsheet(content, file.filename, column_mapping=None)

    component_aliases = {"SAP_BASIS": ["SAPBASIS", "SAP BASIS"], "KERNEL": ["SAP_KERNEL"]}

    db_path = request.app.state.db_path
    engine = get_engine(db_path)
    with Session(engine) as session:
        session.query(LandscapeSnapshot).update({"is_active": False})
        snapshot = LandscapeSnapshot(
            filename=file.filename,
            system_count=len(rows),
            component_count=len(set(r.get("component_code", "") for r in rows)),
            is_active=True,
        )
        session.add(snapshot)
        session.flush()

        for row in rows:
            normalized = normalize_entry(row, component_aliases)
            entry = LandscapeEntry(
                snapshot_id=snapshot.id,
                sid=normalized.sid,
                description=normalized.description,
                product=normalized.product,
                component_code=normalized.component_code,
                version=normalized.version,
                version_numeric=normalized.version_numeric,
                kernel_release=normalized.kernel_release,
                tier=normalized.tier,
                os=normalized.os,
                db=normalized.db,
                business_unit=normalized.business_unit,
                basis_contact=normalized.basis_contact,
                notes=normalized.notes,
            )
            session.add(entry)
        session.commit()

    return RedirectResponse(url="/landscape", status_code=303)
