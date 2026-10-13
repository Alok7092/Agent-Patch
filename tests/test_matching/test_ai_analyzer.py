import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from src.matching.ai_analyzer import AIAnalyzer, should_use_ai, build_landscape_context
from src.matching.models import MatchEntry
from src.ingestion.parser import ParsedNote, VersionRange
from src.landscape.normalizer import NormalizedEntry


@pytest.fixture
def ai_analyzer():
    return AIAnalyzer(
        default_model="us.anthropic.claude-sonnet-4-6-20250514",
        complex_model="us.anthropic.claude-opus-4-6-20250514",
        complex_threshold_cvss=9.0,
        max_tokens=4096,
    )


@pytest.fixture
def hot_news_note():
    return ParsedNote(
        note_number="3500000",
        title="Critical Zero-Day",
        cvss_score=10.0,
        cvss_vector="",
        priority="hot_news",
        components=[],
        version_ranges=[],
        release_date="2026-06-10",
        description="Critical zero-day affecting all SAP systems with RFC enabled.",
        solution_type="patch",
    )


@pytest.fixture
def normal_note():
    return ParsedNote(
        note_number="3421384",
        title="Minor Fix",
        cvss_score=5.0,
        cvss_vector="",
        priority="medium",
        components=["SAP_BASIS"],
        version_ranges=[VersionRange(component="SAP_BASIS", min=750, max=789)],
        release_date="2026-06-10",
        description="Minor issue.",
        solution_type="patch",
    )


class TestShouldUseAI:
    def test_hot_news_always_uses_ai(self, hot_news_note):
        assert should_use_ai(hot_news_note, pass1_matches=[]) is True

    def test_hot_news_with_matches_still_uses_ai(self, hot_news_note):
        fake_match = MatchEntry(
            note_number="3500000", sid="PRD", component="X",
            system_version="1", affected_range="1-2", tier="Prod",
            confidence="HIGH", match_source="rules", match_reason="test"
        )
        assert should_use_ai(hot_news_note, pass1_matches=[fake_match]) is True

    def test_no_components_triggers_ai(self):
        note = ParsedNote(
            note_number="111", title="No comp", cvss_score=6.0,
            cvss_vector="", priority="medium", components=[],
            version_ranges=[], release_date="", description="Desc",
            solution_type="patch",
        )
        assert should_use_ai(note, pass1_matches=[]) is True

    def test_normal_note_with_matches_skips_ai(self, normal_note):
        fake_match = MatchEntry(
            note_number="3421384", sid="PRD-ECC", component="SAP_BASIS",
            system_version="757", affected_range="750-789", tier="Prod",
            confidence="HIGH", match_source="rules", match_reason="test"
        )
        assert should_use_ai(normal_note, pass1_matches=[fake_match]) is False


class TestBuildLandscapeContext:
    def test_produces_summary(self):
        entries = [
            NormalizedEntry(sid="PRD-ECC", description="Prod ECC", product="ECC 6.0",
                            component_code="SAP_BASIS", version="7.57", version_numeric=757,
                            kernel_release="753", tier="Prod", os="Linux", db="HANA",
                            business_unit="", basis_contact="", notes=""),
        ]
        context = build_landscape_context(entries)
        assert "PRD-ECC" in context
        assert "SAP_BASIS" in context
        assert "7.57" in context


class TestAIAnalyzer:
    @pytest.mark.asyncio
    async def test_analyze_returns_match_entries(self, ai_analyzer, hot_news_note):
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps({
            "matches": [
                {
                    "sid": "PRD-PI",
                    "confidence": "MEDIUM",
                    "reasoning": "RFC dependency detected",
                    "recommended_action": "Verify RFC destinations",
                }
            ]
        })

        with patch("anthropic.AsyncAnthropicBedrock") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            mock_client.messages.create = AsyncMock(return_value=mock_response)

            results = await ai_analyzer.analyze(hot_news_note, "Landscape: PRD-PI has RFC")
            assert len(results) == 1
            assert results[0].sid == "PRD-PI"
            assert results[0].confidence == "MEDIUM"
            assert results[0].match_source == "ai_analyzer"
