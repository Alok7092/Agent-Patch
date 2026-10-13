import pytest
import io
import csv
from httpx import AsyncClient, ASGITransport
from sqlalchemy.orm import Session
from src.main import create_app
from src.database import get_engine
from src.models import LandscapeSnapshot, LandscapeEntry


@pytest.fixture
def app(tmp_path):
    return create_app(db_path=str(tmp_path / "test.db"))


@pytest.fixture
def csv_file():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["System ID", "Description", "Product", "Component", "Version", "Kernel", "Tier", "OS", "DB", "Business Unit", "Contact", "Notes"])
    writer.writerow(["PRD-ECC", "Prod ECC", "ECC 6.0", "SAP_BASIS", "7.57", "753", "Prod", "Linux", "HANA", "Finance", "admin@corp.com", ""])
    writer.writerow(["QAS-ECC", "QA ECC", "ECC 6.0", "SAP_BASIS", "7.57", "753", "QA", "Linux", "HANA", "Finance", "admin@corp.com", ""])
    return output.getvalue().encode("utf-8")


@pytest.mark.asyncio
async def test_landscape_upload(app, csv_file):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_resp = await client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
        cookies = login_resp.cookies
        response = await client.post(
            "/landscape/upload",
            files={"file": ("landscape.csv", csv_file, "text/csv")},
            cookies=cookies,
            follow_redirects=False,
        )
        assert response.status_code in (200, 303)

    db_path = app.state.db_path
    engine = get_engine(db_path)
    with Session(engine) as session:
        snapshot = session.query(LandscapeSnapshot).first()
        assert snapshot is not None
        assert snapshot.system_count == 2
        entries = session.query(LandscapeEntry).filter_by(snapshot_id=snapshot.id).all()
        assert len(entries) == 2
