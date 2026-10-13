from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
from src.dashboard.auth import AuthManager


def get_auth_manager(request: Request) -> AuthManager:
    return request.app.state.auth_manager


async def get_current_user(request: Request) -> str:
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    auth: AuthManager = request.app.state.auth_manager
    username = auth.validate_session_token(token)
    if not username:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return username
