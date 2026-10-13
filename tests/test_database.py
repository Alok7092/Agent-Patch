import pytest
from pathlib import Path
from sqlalchemy import inspect

from src.database import init_db, get_engine
from src.models import SecurityNote, LandscapeSnapshot, LandscapeEntry, MatchResult, ApprovalQueueItem


def test_init_db_creates_tables(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(str(db_path))
    engine = get_engine(str(db_path))
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "security_notes" in tables
    assert "landscape_snapshots" in tables
    assert "landscape_entries" in tables
    assert "match_results" in tables
    assert "approval_queue" in tables


def test_security_note_model(tmp_path):
    from sqlalchemy.orm import Session
    db_path = tmp_path / "test.db"
    init_db(str(db_path))
    engine = get_engine(str(db_path))
    with Session(engine) as session:
        note = SecurityNote(
            note_number="3421384",
            title="Test Note",
            cvss_score=8.5,
            priority="high",
            components='["SAP_BASIS"]',
            version_ranges='[{"component": "SAP_BASIS", "min": 750, "max": 789}]',
            status="new",
        )
        session.add(note)
        session.commit()
        result = session.query(SecurityNote).filter_by(note_number="3421384").first()
        assert result.title == "Test Note"
        assert result.cvss_score == 8.5


def test_landscape_snapshot_with_entries(tmp_path):
    from sqlalchemy.orm import Session
    db_path = tmp_path / "test.db"
    init_db(str(db_path))
    engine = get_engine(str(db_path))
    with Session(engine) as session:
        snapshot = LandscapeSnapshot(
            filename="landscape.xlsx",
            system_count=3,
            component_count=10,
            is_active=True,
        )
        session.add(snapshot)
        session.flush()
        entry = LandscapeEntry(
            snapshot_id=snapshot.id,
            sid="PRD-ECC",
            component_code="SAP_BASIS",
            version="757",
            version_numeric=757,
            tier="Prod",
        )
        session.add(entry)
        session.commit()
        loaded = session.query(LandscapeSnapshot).first()
        assert loaded.system_count == 3
        assert len(loaded.entries) == 1
        assert loaded.entries[0].sid == "PRD-ECC"
