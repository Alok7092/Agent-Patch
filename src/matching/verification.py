import json
from src.ingestion.parser import ParsedNote
from src.matching.models import (
    AIAnalysisResult,
    GateOutcome,
    ReliabilityGateResult,
)
from src.matching.ai_analyzer import AIAnalyzer
from src.matching.reliability_gate import evaluate_gate
from src.shared.config import GateConfig


VERIFICATION_PROMPT = """You are an independent SAP security reviewer. A prior analysis has been performed on the Security Note below. Your job is to CHALLENGE the original conclusion by looking for weaknesses.

## Original analysis result
- Decision: {original_decision}
- Confidence: {original_confidence}
- Evidence coverage: {original_evidence_coverage}

## Original evidence summary
{evidence_summary}

## Original assumptions
{assumptions_summary}

## Original critical unknowns
{unknowns_summary}

## Your task

Independently verify the original conclusion. Specifically check:

1. Does every claim in the original evidence have a verifiable source in the landscape data?
2. Are any assumptions being presented as established facts?
3. Is there a valid reason to EXCLUDE this system that was overlooked?
4. Could any unknown value REVERSE the original decision?
5. Does the component and release mapping use correct SAP nomenclature?
6. If the original says NOT_APPLICABLE, is there explicit exclusion evidence, or just absence of evidence?

## Important

- You must form your OWN independent assessment, not simply agree with the original.
- If you find problems with the original analysis, your decision should reflect that.
- Apply the same asymmetric policy: lean toward APPLICABLE when uncertain.

## Security Note
- Number: {note_number}
- Title: {title}
- CVSS: {cvss_score}
- Priority: {priority}
- Affected Components: {components}
- Description: {description}

## Organization SAP Landscape
{landscape_context}

## Response format

Return ONLY a JSON object (no text before/after, no markdown fences):

{{
  "decision": "APPLICABLE" or "NOT_APPLICABLE" or "INCONCLUSIVE",
  "decision_confidence": 0.0 to 1.0,
  "evidence_coverage": 0.0 to 1.0,
  "critical_unknowns": [],
  "assumptions": [],
  "contradictions": [],
  "evidence": [{{"claim": "...", "source": "...", "value": "..."}}],
  "matches": [{{"sid": "...", "component": "...", "version": "...", "confidence": "...", "reasoning": "..."}}],
  "manual_review_triggers": [],
  "exclusion_evidence": ""
}}
"""


class Verifier:
    def __init__(self, ai_analyzer: AIAnalyzer):
        self.ai_analyzer = ai_analyzer

    async def verify(
        self,
        note: ParsedNote,
        original: AIAnalysisResult,
        landscape_context: str,
    ) -> AIAnalysisResult:
        evidence_lines = [
            f"- {e.claim}: {e.value} (source: {e.source})"
            for e in original.evidence
        ]
        evidence_summary = "\n".join(evidence_lines) if evidence_lines else "No evidence provided."

        assumptions_summary = (
            "\n".join(f"- {a}" for a in original.assumptions)
            if original.assumptions
            else "None stated."
        )
        unknowns_summary = (
            "\n".join(f"- {u}" for u in original.critical_unknowns)
            if original.critical_unknowns
            else "None identified."
        )

        prompt = VERIFICATION_PROMPT.format(
            original_decision=original.decision,
            original_confidence=original.decision_confidence,
            original_evidence_coverage=original.evidence_coverage,
            evidence_summary=evidence_summary,
            assumptions_summary=assumptions_summary,
            unknowns_summary=unknowns_summary,
            note_number=note.note_number,
            title=note.title,
            cvss_score=note.cvss_score,
            priority=note.priority,
            components=", ".join(note.components) if note.components else "None specified",
            description=note.description,
            landscape_context=landscape_context,
        )

        model = self.ai_analyzer._select_model(note)
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a JSON API. Respond with ONLY a valid JSON object. "
                    "No text before or after."
                ),
            },
            {"role": "user", "content": prompt},
        ]

        try:
            parsed = await self.ai_analyzer._call_ai(messages, model)
        except (json.JSONDecodeError, RuntimeError):
            return AIAnalysisResult(
                decision="INCONCLUSIVE",
                decision_confidence=0.0,
                evidence_coverage=0.0,
                manual_review_triggers=["MR-05"],
                raw_response={},
            )

        return self.ai_analyzer._parse_ai_response(parsed, note.note_number)


def reconcile(
    original: AIAnalysisResult,
    verification: AIAnalysisResult,
    gate_config: GateConfig | None = None,
) -> tuple[AIAnalysisResult, ReliabilityGateResult]:
    if original.decision == verification.decision:
        gate_result = evaluate_gate(original, gate_config)
        return original, gate_result

    # Disagreement: force manual review with MR-07
    original.manual_review_triggers = list(
        set(original.manual_review_triggers) | {"MR-07"}
    )
    original.contradictions = list(original.contradictions) + [
        f"Primary analysis: {original.decision} (confidence {original.decision_confidence}); "
        f"Verification: {verification.decision} (confidence {verification.decision_confidence})"
    ]

    gate_result = ReliabilityGateResult(
        outcome=GateOutcome.MANUAL_REVIEW,
        reason=f"Verification disagreement: primary={original.decision}, verification={verification.decision}",
        triggered_codes=["MR-07"],
        manual_review_items=[],
    )
    return original, gate_result
