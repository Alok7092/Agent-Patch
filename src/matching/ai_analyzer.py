import json
import os
import ssl
import httpx
from src.ingestion.parser import ParsedNote
from src.matching.models import (
    MatchEntry,
    AIAnalysisResult,
    AIEvidence,
    MANUAL_REVIEW_CODES,
)
from src.landscape.normalizer import NormalizedEntry


def should_use_ai(note: ParsedNote, pass1_matches: list[MatchEntry]) -> bool:
    """AI analysis triggers when rules engine found no SP-level matches
    AND the note has no SP fix data (otherwise rules engine already handled it)."""
    if pass1_matches:
        return False
    has_sp_data = any(vr.fix_sp > 0 for vr in note.version_ranges)
    if has_sp_data:
        return False
    return True


def build_landscape_context(entries: list[NormalizedEntry]) -> str:
    lines = ["SAP Landscape Inventory:"]
    lines.append("SID | Component | Version | SP Level")
    lines.append("--- | --- | --- | ---")
    seen = set()
    for e in entries:
        key = f"{e.sid}|{e.component_code}|{e.version}"
        if key in seen:
            continue
        seen.add(key)
        sp = e.notes.replace("SP: ", "") if e.notes and e.notes.startswith("SP:") else ""
        lines.append(f"{e.sid} | {e.component_code} | {e.version} | {sp}")
    return "\n".join(lines)


ANALYSIS_PROMPT = """You are an SAP security analyst performing a structured applicability assessment of an SAP Security Note against an organization's SAP landscape.

## Your task

Determine whether this Security Note is APPLICABLE, NOT_APPLICABLE, or INCONCLUSIVE for the systems in the landscape below.

## Decision framework

- **APPLICABLE**: The note affects one or more systems in the landscape. You have evidence that the affected component is installed at an affected version/SP level.
- **NOT_APPLICABLE**: The note does NOT affect any system. You have explicit exclusion evidence (e.g., affected component is not installed, or installed version is outside the affected range, or the fix is already applied).
- **INCONCLUSIVE**: You cannot determine applicability with certainty because decision-critical information is missing or conflicting.

## Evidence rules

Every claim in your response MUST have supporting evidence with a specific source and value. Do not state conclusions without citing the data that supports them.

## Critical unknown identification

For each piece of missing information, apply the counterfactual test:
- "If this unknown value were Yes versus No, would the applicability result change?"
- If YES → it is a decision-critical unknown (include in critical_unknowns)
- If NO → ignore it (e.g., missing system owner does not affect applicability)

## Assumption disclosure

If you assume something not explicitly stated in the data (e.g., "feature is likely active because the component is installed"), you MUST list it under assumptions. Do not present assumptions as facts.

## Manual review trigger codes

Self-identify which of these apply. Include the code in manual_review_triggers:

- MR-01: A required decision-critical fact cannot be retrieved from the data provided
- MR-02: Two pieces of evidence contradict each other
- MR-03: Applicability depends on business configuration that cannot be observed (e.g., whether a specific integration scenario is used)
- MR-04: The note depends on another note whose implementation status is unknown
- MR-05: You cannot reliably extract the affected range from the note description
- MR-06: Your conclusion depends on an assumption rather than evidence
- MR-07: Reserved for verification pass disagreements
- MR-08: The landscape data appears outdated relative to the note
- MR-09: Component aliases or release mapping cannot be normalized
- MR-10: Reserved for note revision impact

## Exclusion evidence (NOT_APPLICABLE only)

If your decision is NOT_APPLICABLE, you MUST provide specific exclusion evidence. The following reasoning is NOT sufficient: "The note does not appear relevant." You must cite a concrete fact, such as:
- "Installed release is outside affected range"
- "Required component is not installed"
- "Required feature is confirmed inactive"
- "Correction is already included in installed Support Package"

## Asymmetric policy

It is easier to conclude APPLICABLE (route forward for human approval) than NOT_APPLICABLE (auto-close). When in doubt, lean toward APPLICABLE or INCONCLUSIVE rather than NOT_APPLICABLE.

## Response format

Return ONLY a JSON object (no text before/after, no markdown fences):

{{
  "decision": "APPLICABLE" or "NOT_APPLICABLE" or "INCONCLUSIVE",
  "decision_confidence": 0.0 to 1.0,
  "evidence_coverage": 0.0 to 1.0,
  "critical_unknowns": ["list of missing decision-critical facts"],
  "assumptions": ["list of assumptions made"],
  "contradictions": ["list of evidence conflicts found"],
  "evidence": [
    {{"claim": "what is established", "source": "where this comes from", "value": "the specific data point"}}
  ],
  "matches": [
    {{"sid": "system ID from landscape", "component": "matched component", "version": "system version", "confidence": "HIGH or MEDIUM or LOW", "reasoning": "short reason (max 15 words)"}}
  ],
  "manual_review_triggers": ["MR-XX codes that apply"],
  "exclusion_evidence": "explanation of why not applicable (only for NOT_APPLICABLE, empty string otherwise)"
}}

## Constraints
- Return max 20 unique SIDs in matches
- Keep each reasoning under 15 words
- Only return SIDs that appear in the landscape table below
- If no systems are affected: decision=NOT_APPLICABLE with exclusion_evidence, or INCONCLUSIVE if uncertain
- evidence_coverage = fraction of decision-relevant facts you could verify (0.0 = nothing verified, 1.0 = all facts verified)

## Security Note
- Number: {note_number}
- Title: {title}
- CVSS: {cvss_score}
- Priority: {priority}
- Affected Components: {components}
- Description: {description}
- Fix SP Levels: {fix_sp_info}

## Organization SAP Landscape
{landscape_context}
"""


class AIAnalyzer:
    def __init__(
        self,
        default_model: str = "",
        complex_model: str = "",
        complex_threshold_cvss: float = 9.0,
        max_tokens: int = 4096,
    ):
        self.default_model = default_model or os.environ.get(
            "AI_MODEL", "bedrock.anthropic.claude-sonnet-4-5"
        )
        self.complex_model = complex_model or os.environ.get(
            "AI_COMPLEX_MODEL", "bedrock.anthropic.claude-sonnet-4-5"
        )
        self.complex_threshold_cvss = complex_threshold_cvss
        self.max_tokens = max_tokens

    def _get_base_url(self) -> str:
        url = os.environ.get("AI_BASE_URL", "")
        if not url:
            raise RuntimeError(
                "AI_BASE_URL environment variable is not set. "
                "Set it to your LiteLLM/OpenAI-compatible endpoint (e.g. https://your-gateway.com)."
            )
        return url

    def _get_api_key(self) -> str:
        key = os.environ.get("AI_API_KEY", "")
        if not key:
            raise RuntimeError(
                "AI_API_KEY environment variable is not set. "
                "Set it to the API key for your AI gateway."
            )
        return key

    def _select_model(self, note: ParsedNote) -> str:
        if note.cvss_score >= self.complex_threshold_cvss:
            return self.complex_model
        return self.default_model

    def _filter_landscape_for_note(self, note: ParsedNote, full_context: str) -> str:
        note_comps = set(c.upper() for c in note.components if c and len(c) <= 30)
        if not note_comps:
            return full_context

        lines = full_context.split("\n")
        filtered = lines[:3]
        for line in lines[3:]:
            parts = line.split(" | ")
            if len(parts) >= 2:
                comp = parts[1].strip().upper()
                if comp in note_comps:
                    filtered.append(line)
        if len(filtered) <= 3:
            return full_context
        return "\n".join(filtered)

    async def _call_ai(self, messages: list[dict], model: str) -> dict:
        base_url = self._get_base_url()
        api_key = self._get_api_key()

        ssl_ctx = ssl.create_default_context()
        ssl_ctx.load_default_certs()

        async with httpx.AsyncClient(verify=ssl_ctx, timeout=60.0) as client:
            response = await client.post(
                f"{base_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": self.max_tokens,
                    "messages": messages,
                },
            )
            if response.status_code != 200:
                raise RuntimeError(f"AI API error {response.status_code}: {response.text[:200]}")

            resp_data = response.json()
            text = resp_data["choices"][0]["message"]["content"].strip()

            if text.startswith("```"):
                lines = text.split("\n")
                lines = [l for l in lines[1:] if not l.strip().startswith("```")]
                text = "\n".join(lines)

            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                text = text[start:end]

            return json.loads(text)

    def _parse_ai_response(
        self, parsed: dict, note_number: str
    ) -> AIAnalysisResult:
        evidence = [
            AIEvidence(
                claim=e.get("claim", ""),
                source=e.get("source", ""),
                value=e.get("value", ""),
            )
            for e in parsed.get("evidence", [])
        ]

        matches = []
        for m in parsed.get("matches", []):
            sid = m.get("sid", "")
            if not sid:
                continue
            matches.append(MatchEntry(
                note_number=note_number,
                sid=sid,
                component=m.get("component", ""),
                system_version=m.get("version", ""),
                affected_range="",
                tier="",
                confidence=m.get("confidence", "MEDIUM"),
                match_source="ai_analyzer",
                match_reason=m.get("reasoning", ""),
                recommended_action="",
            ))

        decision = parsed.get("decision", "INCONCLUSIVE")
        if decision not in ("APPLICABLE", "NOT_APPLICABLE", "INCONCLUSIVE"):
            decision = "INCONCLUSIVE"

        return AIAnalysisResult(
            decision=decision,
            decision_confidence=float(parsed.get("decision_confidence", 0.0)),
            evidence_coverage=float(parsed.get("evidence_coverage", 0.0)),
            critical_unknowns=parsed.get("critical_unknowns", []),
            assumptions=parsed.get("assumptions", []),
            contradictions=parsed.get("contradictions", []),
            evidence=evidence,
            matches=matches,
            manual_review_triggers=parsed.get("manual_review_triggers", []),
            exclusion_evidence=parsed.get("exclusion_evidence", ""),
            raw_response=parsed,
        )

    async def analyze(
        self, note: ParsedNote, landscape_context: str
    ) -> AIAnalysisResult:
        model = self._select_model(note)
        relevant_context = self._filter_landscape_for_note(note, landscape_context)

        fix_sp_parts = []
        for vr in note.version_ranges:
            if vr.fix_sp:
                fix_sp_parts.append(
                    f"{vr.component} v{vr.min}: systems need SP{vr.fix_sp} or higher to be patched"
                )
        fix_sp_info = (
            "; ".join(fix_sp_parts)
            if fix_sp_parts
            else "No SP fix data available for this note"
        )

        prompt = ANALYSIS_PROMPT.format(
            note_number=note.note_number,
            title=note.title,
            cvss_score=note.cvss_score,
            priority=note.priority,
            components=", ".join(note.components) if note.components else "None specified",
            description=note.description,
            fix_sp_info=fix_sp_info,
            landscape_context=relevant_context,
        )

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
            parsed = await self._call_ai(messages, model)
        except json.JSONDecodeError:
            return AIAnalysisResult(
                decision="INCONCLUSIVE",
                decision_confidence=0.0,
                evidence_coverage=0.0,
                manual_review_triggers=["MR-05"],
                raw_response={},
            )

        return self._parse_ai_response(parsed, note.note_number)
