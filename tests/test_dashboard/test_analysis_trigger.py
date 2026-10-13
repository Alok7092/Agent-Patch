import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from src.main import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(db_path=str(tmp_path / "test.db"))


@pytest.mark.asyncio
async def test_run_analysis_endpoint(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_resp = await client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
        cookies = login_resp.cookies

        with patch("src.shared.scheduling._scheduled_analysis", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = None
            response = await client.post("/run-analysis", cookies=cookies, follow_redirects=False)
            assert response.status_code in (200, 303)
