import pytest
from src.ingestion.parser import (
    parse_note,
    normalize_component_code,
    parse_version_range,
    ParsedNote,
    VersionRange,
)


class TestNormalizeComponentCode:
    def test_already_normalized(self):
        assert normalize_component_code("SAP_BASIS") == "SAP_BASIS"

    def test_spaces_to_underscores(self):
        assert normalize_component_code("SAP BASIS") == "SAP_BASIS"

    def test_no_separator(self):
        assert normalize_component_code("SAPBASIS") == "SAPBASIS"

    def test_lowercase_to_upper(self):
        assert normalize_component_code("sap_basis") == "SAP_BASIS"

    def test_strips_whitespace(self):
        assert normalize_component_code("  SAP_BASIS  ") == "SAP_BASIS"


class TestParseVersionRange:
    def test_dash_separated(self):
        result = parse_version_range("7.50-7.89", "SAP_BASIS")
        assert result == VersionRange(component="SAP_BASIS", min=750, max=789)

    def test_single_version(self):
        result = parse_version_range("7.57", "SAP_BASIS")
        assert result == VersionRange(component="SAP_BASIS", min=757, max=757)

    def test_three_digit_version(self):
        result = parse_version_range("753-789", "KERNEL")
        assert result == VersionRange(component="KERNEL", min=753, max=789)

    def test_prefix_match_x(self):
        result = parse_version_range("7.5x", "SAP_BASIS")
        assert result == VersionRange(component="SAP_BASIS", min=750, max=759)


class TestParseNote:
    def test_parse_complete_note(self):
        raw = {
            "note_number": "3421384",
            "title": "RFC Vulnerability in SAP BASIS",
            "cvss_score": 8.5,
            "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
            "priority": "high",
            "components": ["SAP_BASIS", "BC-MID"],
            "version_ranges_raw": ["7.50-7.89"],
            "release_date": "2026-06-10",
            "description": "Critical RFC vulnerability.",
            "solution_type": "patch",
            "related_notes": ["3421000"],
        }
        result = parse_note(raw)
        assert isinstance(result, ParsedNote)
        assert result.note_number == "3421384"
        assert result.cvss_score == 8.5
        assert result.priority == "high"
        assert "SAP_BASIS" in result.components
        assert "BC-MID" in result.components
        assert len(result.version_ranges) >= 1
        assert result.version_ranges[0].min == 750

    def test_parse_note_missing_components_returns_empty_list(self):
        raw = {
            "note_number": "3421385",
            "title": "Misc note",
            "cvss_score": 5.0,
            "priority": "medium",
            "components": [],
            "version_ranges_raw": [],
            "release_date": "2026-06-10",
            "description": "Some description.",
            "solution_type": "workaround",
        }
        result = parse_note(raw)
        assert result.components == []
        assert result.version_ranges == []

    def test_parse_note_normalizes_priority(self):
        raw = {
            "note_number": "3421386",
            "title": "Hot news note",
            "cvss_score": 10.0,
            "priority": "Hot News",
            "components": ["KERNEL"],
            "version_ranges_raw": ["753-789"],
            "release_date": "2026-06-10",
            "description": "Critical.",
            "solution_type": "patch",
        }
        result = parse_note(raw)
        assert result.priority == "hot_news"
