import json
from pathlib import Path
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from src.database import init_db, get_engine
from src.dashboard.auth import AuthManager
from src.shared.config import load_config, load_rules
from src.models import SecurityNote, MatchResult, LandscapeSnapshot, LandscapeEntry, AIAnalysis
from src.dashboard.serializers import serialize_landscape, serialize_notes, serialize_decisions

BASE_DIR = Path(__file__).parent.parent


def create_app(db_path: str | None = None, config_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="SNAP")

    if config_dir is None:
        config_dir = BASE_DIR / "config"

    settings_path = config_dir / "settings.yaml"
    if settings_path.exists():
        settings = load_config(settings_path)
    else:
        from src.shared.config import Settings, AppConfig, DatabaseConfig, IngestionConfig, ClaudeConfig, AzureConfig
        settings = Settings(
            app=AppConfig(name="SNAP", mode="local", secret_key="dev-secret", debug=True),
            database=DatabaseConfig(path=db_path or "data/snap.db"),
            ingestion=IngestionConfig(schedule_cron="", retry_attempts=3, retry_backoff_seconds=5, sap_api_base_url=""),
            claude=ClaudeConfig(default_model="", complex_model="", complex_threshold_cvss=9.0, max_tokens=4096),
            azure=AzureConfig(tenant_id="", client_id="", client_secret=""),
        )

    if db_path is None:
        db_path = settings.database.path
    init_db(db_path)

    users_yaml = config_dir / "users.yaml"
    if users_yaml.exists():
        import yaml
        with open(users_yaml) as f:
            user_data = yaml.safe_load(f)
        users = user_data.get("users", [])
    else:
        users = [{"username": "admin", "password_hash": "", "role": "admin"}]

    app.state.auth_manager = AuthManager(settings.app.secret_key, users)
    app.state.settings = settings
    app.state.db_path = db_path

    templates_dir = BASE_DIR / "templates"
    templates_dir.mkdir(exist_ok=True)
    templates = Jinja2Templates(directory=str(templates_dir))
    app.state.templates = templates

    static_dir = BASE_DIR / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/login", response_class=HTMLResponse)
    async def login_page(request: Request):
        return templates.TemplateResponse(request, "login.html")

    @app.post("/login")
    async def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
        auth: AuthManager = app.state.auth_manager
        if auth.verify_password(username, password):
            token = auth.create_session_token(username)
            response = RedirectResponse(url="/", status_code=303)
            response.set_cookie("session", token, httponly=True)
            return response
        return templates.TemplateResponse(request, "login.html", context={"error": "Invalid credentials"})

    @app.post("/api/login")
    async def api_login(request: Request):
        body = await request.json()
        username = body.get("username", "")
        password = body.get("password", "")
        auth: AuthManager = app.state.auth_manager
        if auth.verify_password(username, password):
            token = auth.create_session_token(username)
            response = JSONResponse({"status": "ok", "username": username})
            response.set_cookie("session", token, httponly=True)
            return response
        return JSONResponse({"status": "error", "message": "Invalid credentials"}, status_code=401)

    @app.get("/logout")
    async def logout():
        response = RedirectResponse(url="/", status_code=303)
        response.delete_cookie("session")
        return response

    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request):
        engine = get_engine(db_path)
        with Session(engine) as session:
            notes = session.query(SecurityNote).all()
            matches = session.query(MatchResult).all()
            snapshot = session.query(LandscapeSnapshot).filter_by(is_active=True).first()
            entries = []
            if snapshot:
                entries = session.query(LandscapeEntry).filter_by(snapshot_id=snapshot.id).all()

            ai_analyses = session.query(AIAnalysis).all()

            landscape_data = serialize_landscape(entries)
            notes_data = serialize_notes(notes, matches, entries, ai_analyses)
            decisions_data = serialize_decisions(matches)

            from sqlalchemy import func
            latest_ingested = session.query(func.max(SecurityNote.ingested_at)).scalar()
            notes_loaded_at = latest_ingested.strftime("%d %b %Y · %H:%M").upper() if latest_ingested else ""
            notes_loaded_at_iso = latest_ingested.isoformat() if latest_ingested else ""

        return templates.TemplateResponse(request, "app.html", context={
            "landscape_json": json.dumps(landscape_data),
            "notes_json": json.dumps(notes_data),
            "released_total": len(notes),
            "decisions_json": json.dumps(decisions_data),
            "notes_loaded_at": notes_loaded_at,
            "notes_loaded_at_iso": notes_loaded_at_iso,
        })

    from src.dashboard.routes.notes import router as notes_router
    app.include_router(notes_router)

    from src.dashboard.routes.landscape import router as landscape_router
    app.include_router(landscape_router)

    from src.dashboard.routes.api import router as api_router
    app.include_router(api_router)

    @app.post("/run-analysis")
    async def trigger_analysis(request: Request):
        token = request.cookies.get("session")
        if not token:
            return RedirectResponse(url="/login", status_code=303)
        auth: AuthManager = app.state.auth_manager
        username = auth.validate_session_token(token)
        if not username:
            return RedirectResponse(url="/login", status_code=303)

        from src.shared.scheduling import _scheduled_analysis
        await _scheduled_analysis(app)
        return RedirectResponse(url="/", status_code=303)

    return app
