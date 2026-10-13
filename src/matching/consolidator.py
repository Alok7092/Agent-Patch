from src.matching.models import MatchEntry


CONFIDENCE_RANK = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}


def calculate_priority_score(
    cvss_score: float,
    confidence: str,
    tier: str,
    tier_weights: dict[str, float],
    confidence_weights: dict[str, float],
) -> float:
    cw = confidence_weights.get(confidence, 0.4)
    tw = tier_weights.get(tier, 1.0)
    return cvss_score * cw * tw


def consolidate(
    pass1: list[MatchEntry],
    pass2: list[MatchEntry],
    cvss_score: float,
    tier_weights: dict[str, float],
    confidence_weights: dict[str, float],
) -> list[MatchEntry]:
    all_matches = pass1 + pass2
    deduped: dict[str, MatchEntry] = {}
    for match in all_matches:
        key = f"{match.note_number}:{match.sid}:{match.component}"
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = match
        else:
            if CONFIDENCE_RANK.get(match.confidence, 0) > CONFIDENCE_RANK.get(existing.confidence, 0):
                deduped[key] = match

    scored = []
    for match in deduped.values():
        match.priority_score = calculate_priority_score(
            cvss_score, match.confidence, match.tier, tier_weights, confidence_weights
        )
        scored.append(match)

    scored.sort(key=lambda m: m.priority_score, reverse=True)
    return scored
