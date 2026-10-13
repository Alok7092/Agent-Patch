import pytest
from src.matching.rules_engine import RulesEngine
from src.matching.models import MatchEntry
from src.ingestion.parser import ParsedNote, VersionRange
from src.landscape.indexer import ComponentIndex, SystemMatch, build_component_index
from src.landscape.normalizer import NormalizedEntry
from src.shared.config import RulesConfig, VersionMatching


@pytest.fixture
def rules_config():
    return RulesConfig(
        version_matching=VersionMatching(strategies=["exact_range", "prefix_match", "kernel_match"]),
        component_aliases={"BC-SRV-KRN": ["KERNEL", "SAP_KERNEL"], "BC-ABA": ["SAP_ABA"]},
        product_component_map={"ECC": ["SAP_BASIS", "KERNEL"], "S/4HANA": ["SAP_BASIS", "SAP_UI", "KERNEL"]},
        tier_weights={"Prod": 4, "QA": 2, "Dev": 1, "Sandbox": 0.5},
        confidence_weights={"HIGH": 1.0, "MEDIUM": 0.7, "LOW": 0.4},
    )


@pytest.fixture
def component_index():
    entries = [
        NormalizedEntry(sid="PRD-ECC", description="Prod ECC", product="ECC 6.0",
                        component_code="SAP_BASIS", version="7.57", version_numeric=757,
                        kernel_release="753", tier="Prod", os="", db="", business_unit="", basis_contact="", notes=""),
        NormalizedEntry(sid="QAS-ECC", description="QA ECC", product="ECC 6.0",
                        component_code="SAP_BASIS", version="7.57", version_numeric=757,
                        kernel_release="753", tier="QA", os="", db="", business_unit="", basis_contact="", notes=""),
        NormalizedEntry(sid="PRD-S4H", description="Prod S4", product="S/4HANA",
                        component_code="SAP_BASIS", version="7.89", version_numeric=789,
                        kernel_release="789", tier="Prod", os="", db="", business_unit="", basis_contact="", notes=""),
    ]
    return build_component_index(entries)


@pytest.fixture
def sample_note():
    return ParsedNote(
        note_number="3421384",
        title="RFC Vulnerability",
        cvss_score=8.5,
        cvss_vector="",
        priority="high",
        components=["SAP_BASIS"],
        version_ranges=[VersionRange(component="SAP_BASIS", min=750, max=789)],
        release_date="2026-06-10",
        description="Critical vulnerability.",
        solution_type="patch",
    )


class TestRulesEngine:
    def test_exact_range_match(self, rules_config, component_index, sample_note):
        engine = RulesEngine(rules_config)
        matches = engine.match(sample_note, component_index)
        assert len(matches) == 3
        sids = [m.sid for m in matches]
        assert "PRD-ECC" in sids
        assert "QAS-ECC" in sids
        assert "PRD-S4H" in sids

    def test_all_matches_are_high_confidence(self, rules_config, component_index, sample_note):
        engine = RulesEngine(rules_config)
        matches = engine.match(sample_note, component_index)
        for m in matches:
            assert m.confidence == "HIGH"
            assert m.match_source == "rules_engine"

    def test_match_reason_contains_range(self, rules_config, component_index, sample_note):
        engine = RulesEngine(rules_config)
        matches = engine.match(sample_note, component_index)
        for m in matches:
            assert "750-789" in m.match_reason

    def test_no_match_outside_range(self, rules_config, component_index):
        note = ParsedNote(
            note_number="9999999",
            title="Unrelated",
            cvss_score=5.0,
            cvss_vector="",
            priority="medium",
            components=["SAP_BASIS"],
            version_ranges=[VersionRange(component="SAP_BASIS", min=800, max=900)],
            release_date="2026-06-10",
            description="",
            solution_type="patch",
        )
        engine = RulesEngine(rules_config)
        matches = engine.match(note, component_index)
        assert matches == []

    def test_component_alias_resolution(self, rules_config):
        entries = [
            NormalizedEntry(sid="PRD-ECC", description="", product="ECC",
                            component_code="KERNEL", version="753", version_numeric=753,
                            kernel_release="753", tier="Prod", os="", db="", business_unit="", basis_contact="", notes=""),
        ]
        index = build_component_index(entries)
        note = ParsedNote(
            note_number="5555555",
            title="Kernel Note",
            cvss_score=7.0,
            cvss_vector="",
            priority="high",
            components=["BC-SRV-KRN"],
            version_ranges=[VersionRange(component="BC-SRV-KRN", min=750, max=760)],
            release_date="2026-06-10",
            description="",
            solution_type="patch",
        )
        engine = RulesEngine(rules_config)
        matches = engine.match(note, index)
        assert len(matches) == 1
        assert matches[0].sid == "PRD-ECC"
