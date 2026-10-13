import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.orm import Session
from src.main import create_app
from src.database import get_engine
from src.models import SecurityNote, MatchResult


@pytest.fixture
def app_with_data(tmp_path):
    db_path = str(tmp_path / "test.db")
    app = create_app(db_path=db_path)
    engine = get_engine(db_path)
    with Session(engine) as session:
        note = SecurityNote(
            note_number="3421384", title="RFC Vulnerability",
            cvss_score=8.5, priority="high", components='["SAP_BASIS"]',
            version_ranges='[{"component": "SAP_BASIS", "min": 750, "max": 789}]',
            status="matched",
        )
        session.add(note)
        session.flush()
        match = MatchResult(
            note_id=note.id, note_number="3421384", sid="PRD-ECC",
            component="SAP_BASIS", system_version="757", affected_range="750-789",
            tier="Prod", confidence="HIGH", match_source="rules_engine",
            match_reason="Component match", priority_score=34.0, status="pending",
        )
        session.add(match)
        session.commit()
    return app


@pytest.mark.asyncio
async def test_notes_list(app_with_data):
    transport = ASGITransport(app=app_with_data)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_resp = await client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
        cookies = login_resp.cookies
        response = await client.get("/notes", cookies=cookies)
        assert response.status_code == 200
        assert "3421384" in response.text
        assert "RFC Vulnerability" in response.text


@pytest.mark.asyncio
async def test_note_detail(app_with_data):
    transport = ASGITransport(app=app_with_data)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_resp = await client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
        cookies = login_resp.cookies
        response = await client.get("/notes/3421384", cookies=cookies)
        assert response.status_code == 200
        assert "PRD-ECC" in response.text
        assert "HIGH" in response.text
