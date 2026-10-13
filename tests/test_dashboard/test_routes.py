import pytest
from httpx import AsyncClient, ASGITransport
from src.main import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(db_path=str(tmp_path / "test.db"), config_dir=None)


@pytest.mark.asyncio
async def test_app_starts(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/login")
        assert response.status_code == 200
        assert "SNAP" in response.text


@pytest.mark.asyncio
async def test_unauthenticated_gets_app_page(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/", follow_redirects=False)
        assert response.status_code == 200
        assert "SNAP" in response.text


@pytest.mark.asyncio
async def test_login_with_valid_credentials(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/login", data={
            "username": "admin",
            "password": "admin",
        }, follow_redirects=False)
        assert response.status_code in (302, 303)
