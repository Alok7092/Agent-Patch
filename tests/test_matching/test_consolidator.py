import pytest
from src.matching.consolidator import consolidate, calculate_priority_score
from src.matching.models import MatchEntry


@pytest.fixture
def tier_weights():
    return {"Prod": 4, "QA": 2, "Dev": 1, "Sandbox": 0.5}


@pytest.fixture
def confidence_weights():
    return {"HIGH": 1.0, "MEDIUM": 0.7, "LOW": 0.4}


@pytest.fixture
def pass1_matches():
    return [
        MatchEntry(note_number="3421384", sid="PRD-ECC", component="SAP_BASIS",
                   system_version="757", affected_range="750-789", tier="Prod",
                   confidence="HIGH", match_source="rules_engine",
                   match_reason="Component match"),
        MatchEntry(note_number="3421384", sid="QAS-ECC", component="SAP_BASIS",
                   system_version="757", affected_range="750-789", tier="QA",
                   confidence="HIGH", match_source="rules_engine",
                   match_reason="Component match"),
    ]


@pytest.fixture
def pass2_matches():
    return [
        MatchEntry(note_number="3421384", sid="PRD-PI", component="",
                   system_version="", affected_range="", tier="Prod",
                   confidence="MEDIUM", match_source="ai_analyzer",
                   match_reason="RFC dependency"),
    ]


class TestCalculatePriorityScore:
    def test_high_cvss_prod_high_confidence(self, tier_weights, confidence_weights):
        score = calculate_priority_score(8.5, "HIGH", "Prod", tier_weights, confidence_weights)
        assert score == 8.5 * 1.0 * 4  # 34.0

    def test_medium_confidence_qa(self, tier_weights, confidence_weights):
        score = calculate_priority_score(8.5, "MEDIUM", "QA", tier_weights, confidence_weights)
        assert score == pytest.approx(8.5 * 0.7 * 2)  # 11.9

    def test_low_cvss_sandbox(self, tier_weights, confidence_weights):
        score = calculate_priority_score(3.0, "LOW", "Sandbox", tier_weights, confidence_weights)
        assert score == pytest.approx(3.0 * 0.4 * 0.5)  # 0.6

    def test_unknown_tier_defaults_to_1(self, tier_weights, confidence_weights):
        score = calculate_priority_score(5.0, "HIGH", "Unknown", tier_weights, confidence_weights)
        assert score == 5.0 * 1.0 * 1


class TestConsolidate:
    def test_merges_and_scores(self, pass1_matches, pass2_matches, tier_weights, confidence_weights):
        result = consolidate(pass1_matches, pass2_matches, 8.5, tier_weights, confidence_weights)
        assert len(result) == 3
        assert result[0].priority_score >= result[1].priority_score
        assert result[1].priority_score >= result[2].priority_score

    def test_prod_high_confidence_ranked_first(self, pass1_matches, pass2_matches, tier_weights, confidence_weights):
        result = consolidate(pass1_matches, pass2_matches, 8.5, tier_weights, confidence_weights)
        assert result[0].sid == "PRD-ECC"
        assert result[0].priority_score == 34.0

    def test_deduplicates_same_sid_component(self, tier_weights, confidence_weights):
        dup1 = MatchEntry(note_number="111", sid="PRD-ECC", component="SAP_BASIS",
                          system_version="757", affected_range="750-789", tier="Prod",
                          confidence="HIGH", match_source="rules_engine", match_reason="Rule match")
        dup2 = MatchEntry(note_number="111", sid="PRD-ECC", component="SAP_BASIS",
                          system_version="757", affected_range="750-789", tier="Prod",
                          confidence="MEDIUM", match_source="ai_analyzer", match_reason="AI match")
        result = consolidate([dup1], [dup2], 7.0, tier_weights, confidence_weights)
        assert len(result) == 1
        assert result[0].confidence == "HIGH"
