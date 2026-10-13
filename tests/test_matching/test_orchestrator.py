import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy.orm import Session
from src.matching.orchestrator import run_analysis, AnalysisResult
from src.ingestion.parser import ParsedNote, VersionRange
from src.landscape.indexer import build_component_index
from src.landscape.normalizer import NormalizedEntry
from src.database import init_db, get_engine
from src.models import SecurityNote, MatchResult
from src.shared.config import RulesConfig, VersionMatching, ClaudeConfig


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
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


@pytest.fixture
def component_index():
    entries = [
        NormalizedEntry(sid="PRD-ECC", description="", product="ECC",
                        component_code="SAP_BASIS", version="7.57", version_numeric=757,
                        kernel_release="753", tier="Prod", os="", db="", business_unit="", basis_contact="", notes=""),
    ]
    return build_component_index(entries)


@pytest.fixture
def landscape_entries():
    return [
        NormalizedEntry(sid="PRD-ECC", description="", product="ECC",
                        component_code="SAP_BASIS", version="7.57", version_numeric=757,
                        kernel_release="753", tier="Prod", os="", db="", business_unit="", basis_contact="", notes=""),
    ]


@pytest.mark.asyncio
async def test_run_analysis_stores_results(db_path, rules_config, claude_config, component_index, landscape_entries):
    engine = get_engine(db_path)
    with Session(engine) as session:
        note = SecurityNote(
            note_number="3421384", title="RFC Vulnerability", cvss_score=8.5,
            priority="high", components='["SAP_BASIS"]',
            version_ranges='[{"component": "SAP_BASIS", "min": 750, "max": 789}]',
            status="new",
        )
        session.add(note)
        session.commit()

    with patch("src.matching.orchestrator.AIAnalyzer") as MockAI:
        mock_instance = MockAI.return_value
        mock_instance.analyze = AsyncMock(return_value=[])

        result = await run_analysis(
            db_path=db_path,
            rules_config=rules_config,
            claude_config=claude_config,
            component_index=component_index,
            landscape_entries=landscape_entries,
        )

    assert isinstance(result, AnalysisResult)
    assert result.total_notes == 1
    assert result.total_matches >= 1

    with Session(engine) as session:
        stored = session.query(MatchResult).all()
        assert len(stored) >= 1
        assert stored[0].note_number == "3421384"
        assert stored[0].sid == "PRD-ECC"
