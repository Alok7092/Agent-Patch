from src.matching.models import (
    AIAnalysisResult,
    GateOutcome,
    ReliabilityGateResult,
    ManualReviewItem,
    MANUAL_REVIEW_CODES,
)
from src.shared.config import GateConfig


def evaluate_gate(
    analysis: AIAnalysisResult,
    config: GateConfig | None = None,
) -> ReliabilityGateResult:
    if config is None:
        config = GateConfig()

    # Hard triggers: any MR code forces manual review regardless of confidence
    if analysis.manual_review_triggers:
        valid_codes = [
            c for c in analysis.manual_review_triggers if c in MANUAL_REVIEW_CODES
        ]
        if valid_codes:
            items = build_manual_review_items(analysis, valid_codes)
            return ReliabilityGateResult(
                outcome=GateOutcome.MANUAL_REVIEW,
                reason=f"Hard trigger: {', '.join(valid_codes)}",
                triggered_codes=valid_codes,
                manual_review_items=items,
            )

    has_unknowns = len(analysis.critical_unknowns) > 0
    has_contradictions = len(analysis.contradictions) > 0
    has_assumptions = len(analysis.assumptions) > 0

    if analysis.decision == "APPLICABLE":
        if (
            analysis.decision_confidence >= config.applicable_confidence_threshold
            and analysis.evidence_coverage >= config.applicable_evidence_threshold
            and not has_unknowns
            and not has_contradictions
            and not has_assumptions
        ):
            return ReliabilityGateResult(
                outcome=GateOutcome.AUTO_APPROVE,
                reason="Applicable with full evidence coverage and no unknowns",
            )

    if analysis.decision == "NOT_APPLICABLE":
        if (
            analysis.decision_confidence >= config.not_applicable_confidence_threshold
            and analysis.evidence_coverage >= config.not_applicable_evidence_threshold
            and analysis.exclusion_evidence
            and not has_unknowns
            and not has_contradictions
        ):
            return ReliabilityGateResult(
                outcome=GateOutcome.AUTO_CLOSE,
                reason=f"Not applicable: {analysis.exclusion_evidence}",
            )

    # Everything else: manual review
    reasons = []
    codes = []
    if has_unknowns:
        reasons.append("critical unknowns present")
        codes.append("MR-01")
    if has_contradictions:
        reasons.append("evidence conflicts")
        codes.append("MR-02")
    if has_assumptions:
        reasons.append("unsupported assumptions")
        codes.append("MR-06")
    if analysis.decision == "NOT_APPLICABLE" and not analysis.exclusion_evidence:
        reasons.append("no explicit exclusion evidence")
    if analysis.decision == "INCONCLUSIVE":
        reasons.append("AI assessment inconclusive")
    if not reasons:
        reasons.append("thresholds not met")

    items = build_manual_review_items(analysis, codes)
    return ReliabilityGateResult(
        outcome=GateOutcome.MANUAL_REVIEW,
        reason="; ".join(reasons),
        triggered_codes=codes,
        manual_review_items=items,
    )


def is_borderline(
    analysis: AIAnalysisResult,
    gate_result: ReliabilityGateResult,
    config: GateConfig | None = None,
) -> bool:
    if config is None:
        config = GateConfig()
    if gate_result.outcome != GateOutcome.MANUAL_REVIEW:
        return False
    # Hard MR triggers are never borderline
    if gate_result.triggered_codes and any(
        c in analysis.manual_review_triggers for c in gate_result.triggered_codes
    ):
        return False

    margin = config.borderline_margin
    conf = analysis.decision_confidence

    if analysis.decision == "APPLICABLE":
        threshold = config.applicable_confidence_threshold
        if threshold - margin <= conf < threshold:
            return True
        ev_threshold = config.applicable_evidence_threshold
        if ev_threshold - margin <= analysis.evidence_coverage < ev_threshold:
            return True

    if analysis.decision == "NOT_APPLICABLE":
        threshold = config.not_applicable_confidence_threshold
        if threshold - margin <= conf < threshold:
            return True
        ev_threshold = config.not_applicable_evidence_threshold
        if ev_threshold - margin <= analysis.evidence_coverage < ev_threshold:
            return True

    return False


def build_manual_review_items(
    analysis: AIAnalysisResult,
    triggered_codes: list[str],
) -> list[ManualReviewItem]:
    confirmed = [f"{e.claim}: {e.value}" for e in analysis.evidence]
    items = []

    for code in triggered_codes:
        desc = MANUAL_REVIEW_CODES.get(code, "Unknown")

        if code == "MR-01" and analysis.critical_unknowns:
            for unknown in analysis.critical_unknowns:
                items.append(ManualReviewItem(
                    reason_code=code,
                    description=desc,
                    confirmed_facts=confirmed,
                    question=f"Can you confirm: {unknown}",
                    answer_options=["Yes", "No", "Unable to determine"],
                ))
        elif code == "MR-02":
            for contradiction in analysis.contradictions:
                items.append(ManualReviewItem(
                    reason_code=code,
                    description=desc,
                    confirmed_facts=confirmed,
                    question=f"Evidence conflict: {contradiction}. Which is correct?",
                    answer_options=[
                        "First source is correct",
                        "Second source is correct",
                        "Unable to determine",
                    ],
                ))
        elif code == "MR-06":
            for assumption in analysis.assumptions:
                items.append(ManualReviewItem(
                    reason_code=code,
                    description=desc,
                    confirmed_facts=confirmed,
                    question=f"Assumption: {assumption}. Is this correct?",
                    answer_options=["Yes, confirmed", "No, incorrect", "Unable to determine"],
                ))
        else:
            items.append(ManualReviewItem(
                reason_code=code,
                description=desc,
                confirmed_facts=confirmed,
                question=f"{desc} — please review and confirm applicability.",
                answer_options=["Applicable", "Not applicable", "Unable to determine"],
            ))

    if not items and analysis.critical_unknowns:
        for unknown in analysis.critical_unknowns:
            items.append(ManualReviewItem(
                reason_code="MR-01",
                description=MANUAL_REVIEW_CODES["MR-01"],
                confirmed_facts=confirmed,
                question=f"Can you confirm: {unknown}",
                answer_options=["Yes", "No", "Unable to determine"],
            ))

    return items
