from dataclasses import dataclass, field


@dataclass
class MatchEntry:
    note_number: str
    sid: str
    component: str
    system_version: str
    affected_range: str
    tier: str
    confidence: str
    match_source: str
    match_reason: str
    priority_score: float = 0.0
    recommended_action: str = ""


@dataclass
class AIEvidence:
    claim: str
    source: str
    value: str


@dataclass
class ManualReviewItem:
    reason_code: str
    description: str
    confirmed_facts: list[str]
    question: str
    answer_options: list[str]


MANUAL_REVIEW_CODES = {
    "MR-01": "Critical Data Missing",
    "MR-02": "Evidence Conflict",
    "MR-03": "Conditional Applicability",
    "MR-04": "Dependency Unresolved",
    "MR-05": "Source Parsing Failure",
    "MR-06": "Unsupported Assumption",
    "MR-07": "Contradictory AI Result",
    "MR-08": "Stale Inventory",
    "MR-09": "Unrecognized Product Mapping",
    "MR-10": "Note Revision Impact",
}


class GateOutcome:
    AUTO_APPROVE = "auto_approve"
    AUTO_CLOSE = "auto_close"
    MANUAL_REVIEW = "manual_review"


@dataclass
class AIAnalysisResult:
    decision: str
    decision_confidence: float
    evidence_coverage: float
    critical_unknowns: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    evidence: list[AIEvidence] = field(default_factory=list)
    matches: list[MatchEntry] = field(default_factory=list)
    manual_review_triggers: list[str] = field(default_factory=list)
    exclusion_evidence: str = ""
    raw_response: dict = field(default_factory=dict)


@dataclass
class ReliabilityGateResult:
    outcome: str
    reason: str
    triggered_codes: list[str] = field(default_factory=list)
    manual_review_items: list[ManualReviewItem] = field(default_factory=list)
