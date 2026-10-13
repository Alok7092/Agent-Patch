import json
import sys
from dataclasses import dataclass
from datetime import datetime
from sqlalchemy.orm import Session
from src.database import get_engine
from src.models import SecurityNote, MatchResult, AIAnalysis
from src.ingestion.parser import ParsedNote, VersionRange
from src.matching.rules_engine import RulesEngine
from src.matching.ai_analyzer import AIAnalyzer, should_use_ai, build_landscape_context
from src.matching.consolidator import consolidate
from src.matching.models import (
    MatchEntry,
    AIAnalysisResult,
    GateOutcome,
    ReliabilityGateResult,
)
from src.matching.reliability_gate import evaluate_gate, is_borderline
from src.matching.verification import Verifier, reconcile
from src.landscape.indexer import ComponentIndex
from src.landscape.normalizer import NormalizedEntry
from src.shared.config import RulesConfig, ClaudeConfig, GateConfig


@dataclass
class AnalysisResult:
    total_notes: int
    total_matches: int
    notes_with_matches: int
    notes_without_matches: int
    auto_approved: int = 0
    auto_closed: int = 0
    manual_review: int = 0


def _db_note_to_parsed(note: SecurityNote) -> ParsedNote:
    components = json.loads(note.components) if note.components else []
    version_ranges_raw = json.loads(note.version_ranges) if note.version_ranges else []
    version_ranges = [
        VersionRange(component=vr["component"], min=vr["min"], max=vr["max"], fix_sp=vr.get("fix_sp", 0))
        for vr in version_ranges_raw
    ]
    return ParsedNote(
        note_number=note.note_number,
        title=note.title or "",
        cvss_score=note.cvss_score or 0.0,
        cvss_vector=note.cvss_vector or "",
        priority=note.priority or "medium",
        components=components,
        version_ranges=version_ranges,
        release_date=str(note.release_date) if note.release_date else "",
        description=note.description or "",
        solution_type=note.solution_type or "",
    )


def _determine_match_status(
    match: MatchEntry,
    gate_result: ReliabilityGateResult | None,
) -> str:
    if match.match_source == "rules_engine":
        return "pending"
    if gate_result is None:
        return "pending"
    if gate_result.outcome == GateOutcome.AUTO_APPROVE:
        return "ready_for_approval"
    if gate_result.outcome == GateOutcome.MANUAL_REVIEW:
        return "manual_review"
    return "pending"


def _determine_note_status(
    consolidated: list[MatchEntry],
    gate_result: ReliabilityGateResult | None,
    pass1: list[MatchEntry],
) -> str:
    if pass1:
        return "matched"
    if gate_result is not None:
        if gate_result.outcome == GateOutcome.AUTO_APPROVE:
            return "matched"
        if gate_result.outcome == GateOutcome.AUTO_CLOSE:
            return "not_applicable"
        if gate_result.outcome == GateOutcome.MANUAL_REVIEW:
            return "manual_review"
    if consolidated:
        return "matched"
    return "no_match"


def _get_review_code(
    match: MatchEntry,
    gate_result: ReliabilityGateResult | None,
) -> str | None:
    if gate_result and gate_result.outcome == GateOutcome.MANUAL_REVIEW:
        return gate_result.triggered_codes[0] if gate_result.triggered_codes else None
    return None


def _store_ai_analysis(
    session: Session,
    db_note: SecurityNote,
    ai_result: AIAnalysisResult,
    gate_result: ReliabilityGateResult,
    verification_run: bool = False,
    verification_result: AIAnalysisResult | None = None,
) -> None:
    record = AIAnalysis(
        note_id=db_note.id,
        note_number=db_note.note_number,
        decision=ai_result.decision,
        decision_confidence=ai_result.decision_confidence,
        evidence_coverage=ai_result.evidence_coverage,
        critical_unknowns=json.dumps(ai_result.critical_unknowns),
        assumptions=json.dumps(ai_result.assumptions),
        contradictions=json.dumps(ai_result.contradictions),
        evidence=json.dumps(
            [{"claim": e.claim, "source": e.source, "value": e.value} for e in ai_result.evidence]
        ),
        manual_review_triggers=json.dumps(ai_result.manual_review_triggers),
        exclusion_evidence=ai_result.exclusion_evidence,
        gate_outcome=gate_result.outcome,
        gate_reason=gate_result.reason,
        verification_run=verification_run,
        verification_result=json.dumps(verification_result.raw_response) if verification_result else None,
        raw_response=json.dumps(ai_result.raw_response),
    )
    session.add(record)


async def run_analysis(
    db_path: str,
    rules_config: RulesConfig,
    claude_config: ClaudeConfig,
    component_index: ComponentIndex,
    landscape_entries: list[NormalizedEntry],
) -> AnalysisResult:
    engine = get_engine(db_path)
    rules_engine = RulesEngine(rules_config)
    ai_analyzer = AIAnalyzer(
        default_model=claude_config.default_model,
        complex_model=claude_config.complex_model,
        complex_threshold_cvss=claude_config.complex_threshold_cvss,
        max_tokens=claude_config.max_tokens,
    )
    verifier = Verifier(ai_analyzer)
    gate_config = claude_config.gate
    landscape_context = build_landscape_context(landscape_entries)

    with Session(engine) as session:
        notes = session.query(SecurityNote).filter_by(status="new").all()
        total_notes = len(notes)
        total_matches = 0
        notes_with_matches = 0
        auto_approved = 0
        auto_closed = 0
        manual_review_count = 0

        for db_note in notes:
            parsed = _db_note_to_parsed(db_note)

            # Pass 1: Rules Engine (unchanged)
            pass1 = rules_engine.match(parsed, component_index)

            # Pass 2: AI Analysis (structured response)
            ai_result = None
            gate_result = None
            verification_result = None

            if should_use_ai(parsed, pass1):
                try:
                    ai_result = await ai_analyzer.analyze(parsed, landscape_context)
                except Exception as e:
                    print(f"[AI] Error analyzing {parsed.note_number}: {type(e).__name__}: {e}", file=sys.stderr)
                    ai_result = None

            # Reliability Gate
            if ai_result is not None:
                gate_result = evaluate_gate(ai_result, gate_config)

                # Verification Pass for borderline results
                if (
                    gate_config.enable_verification
                    and is_borderline(ai_result, gate_result, gate_config)
                ):
                    try:
                        verification_result = await verifier.verify(
                            parsed, ai_result, landscape_context
                        )
                        ai_result, gate_result = reconcile(
                            ai_result, verification_result, gate_config
                        )
                    except Exception as e:
                        print(f"[Verify] Error verifying {parsed.note_number}: {type(e).__name__}: {e}", file=sys.stderr)
                        gate_result = ReliabilityGateResult(
                            outcome=GateOutcome.MANUAL_REVIEW,
                            reason="Verification pass failed",
                            triggered_codes=["MR-05"],
                            manual_review_items=[],
                        )

                # Store AI analysis audit record
                _store_ai_analysis(
                    session, db_note, ai_result, gate_result,
                    verification_run=verification_result is not None,
                    verification_result=verification_result,
                )

                # Track gate outcome counts
                if gate_result.outcome == GateOutcome.AUTO_APPROVE:
                    auto_approved += 1
                elif gate_result.outcome == GateOutcome.AUTO_CLOSE:
                    auto_closed += 1
                elif gate_result.outcome == GateOutcome.MANUAL_REVIEW:
                    manual_review_count += 1

            # Consolidate
            pass2 = ai_result.matches if ai_result else []
            consolidated = consolidate(
                pass1, pass2, parsed.cvss_score,
                rules_config.tier_weights, rules_config.confidence_weights,
            )

            # Persist match results
            for match in consolidated:
                status = _determine_match_status(match, gate_result)
                review_code = _get_review_code(match, gate_result)
                result = MatchResult(
                    note_id=db_note.id,
                    note_number=match.note_number,
                    sid=match.sid,
                    component=match.component,
                    system_version=match.system_version,
                    affected_range=match.affected_range,
                    tier=match.tier,
                    confidence=match.confidence,
                    match_source=match.match_source,
                    match_reason=match.match_reason,
                    priority_score=match.priority_score,
                    status=status,
                    gate_outcome=gate_result.outcome if gate_result else None,
                    manual_review_code=review_code,
                )
                session.add(result)

            db_note.status = _determine_note_status(consolidated, gate_result, pass1)
            total_matches += len(consolidated)
            if consolidated:
                notes_with_matches += 1

        session.commit()

    return AnalysisResult(
        total_notes=total_notes,
        total_matches=total_matches,
        notes_with_matches=notes_with_matches,
        notes_without_matches=total_notes - notes_with_matches,
        auto_approved=auto_approved,
        auto_closed=auto_closed,
        manual_review=manual_review_count,
    )
