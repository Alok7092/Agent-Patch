import pytest
import json
from unittest.mock import patch, AsyncMock
from sqlalchemy.orm import Session
from src.database import init_db, get_engine
from src.models import SecurityNote, LandscapeSnapshot, LandscapeEntry, MatchResult
from src.ingestion.parser import parse_note
from src.landscape.loader import load_spreadsheet
from src.landscape.normalizer import normalize_entry
from src.landscape.indexer import build_component_index
from src.matching.orchestrator import run_analysis
from src.shared.config import RulesConfig, VersionMatching, ClaudeConfig


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "integration.db")
    init_db(path)
    return path


@pytest.fixture
def rules_config():
    return RulesConfig(
        version_matching=VersionMatching(strategies=["exact_range"]),
        component_aliases={"BC-SRV-KRN": ["KERNEL"]},
        product_component_map={"ECC": ["SAP_BASIS", "KERNEL"]},
        tier_weights={"Prod": 4, "QA": 2, "Dev": 1, "Sandbox": 0.5},
        confidence_weights={"HIGH": 1.0, "MEDIUM": 0.7, "LOW": 0.4},
    )


@pytest.fixture
def claude_config():
    return ClaudeConfig(
        default_model="us.anthropic.claude-sonnet-4-6-20250514",
        complex_model="us.anthropic.claude-opus-4-6-20250514",
        complex_threshold_cvss=9.0,
        max_tokens=4096,
    )


@pytest.mark.asyncio
async def test_full_pipeline(db_path, rules_config, claude_config):
    engine = get_engine(db_path)

    # Step 1: Ingest a security note
    raw_note = {
        "note_number": "3421384",
        "title": "RFC Vulnerability in SAP BASIS",
        "cvss_score": 8.5,
        "priority": "high",
        "components": ["SAP_BASIS"],
        "version_ranges_raw": ["7.50-7.89"],
        "release_date": "2026-06-10",
        "description": "Critical RFC vulnerability allows remote code execution.",
        "solution_type": "patch",
    }
    parsed = parse_note(raw_note)
    with Session(engine) as session:
        db_note = SecurityNote(
            note_number=parsed.note_number,
            title=parsed.title,
            cvss_score=parsed.cvss_score,
            priority=parsed.priority,
            components=json.dumps(parsed.components),
            version_ranges=json.dumps([{"component": vr.component, "min": vr.min, "max": vr.max} for vr in parsed.version_ranges]),
            description=parsed.description,
            solution_type=parsed.solution_type,
            status="new",
        )
        session.add(db_note)
        session.commit()

    # Step 2: Upload landscape
    import io, csv
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["System ID", "Description", "Product", "Component", "Version", "Kernel", "Tier", "OS", "DB", "Business Unit", "Contact", "Notes"])
    writer.writerow(["PRD-ECC", "Prod ECC", "ECC 6.0", "SAP_BASIS", "7.57", "753", "Prod", "Linux", "HANA", "Finance", "admin@corp.com", ""])
    writer.writerow(["DEV-ECC", "Dev ECC", "ECC 6.0", "SAP_BASIS", "7.57", "753", "Dev", "Linux", "HANA", "Finance", "admin@corp.com", ""])
    csv_bytes = output.getvalue().encode("utf-8")

    rows = load_spreadsheet(csv_bytes, "landscape.csv", column_mapping=None)
    aliases = {"SAP_BASIS": ["SAPBASIS", "SAP BASIS"], "KERNEL": ["SAP_KERNEL"]}
    entries = [normalize_entry(row, aliases) for row in rows]
    index = build_component_index(entries)

    # Step 3: Run analysis (mock AI to avoid real API call)
    with patch("src.matching.orchestrator.AIAnalyzer") as MockAI:
        mock_instance = MockAI.return_value
        mock_instance.analyze = AsyncMock(return_value=[])

        result = await run_analysis(
            db_path=db_path,
            rules_config=rules_config,
            claude_config=claude_config,
            component_index=index,
            landscape_entries=entries,
        )

    # Step 4: Verify results
    assert result.total_notes == 1
    assert result.total_matches == 2  # PRD-ECC and DEV-ECC both match

    with Session(engine) as session:
        matches = session.query(MatchResult).order_by(MatchResult.priority_score.desc()).all()
        assert len(matches) == 2
        assert matches[0].sid == "PRD-ECC"  # Prod ranked first (higher tier weight)
        assert matches[0].confidence == "HIGH"
        assert matches[0].priority_score == 8.5 * 1.0 * 4  # 34.0
        assert matches[1].sid == "DEV-ECC"
        assert matches[1].priority_score == 8.5 * 1.0 * 1  # 8.5

        note = session.query(SecurityNote).filter_by(note_number="3421384").first()
        assert note.status == "matched"
