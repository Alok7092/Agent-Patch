import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class VersionRange:
    component: str
    min: int
    max: int
    fix_sp: int = 0


@dataclass
class ParsedNote:
    note_number: str
    title: str
    cvss_score: float
    cvss_vector: str
    priority: str
    components: list[str]
    version_ranges: list[VersionRange]
    release_date: str
    description: str
    solution_type: str
    related_notes: list[str] = field(default_factory=list)
    raw_content: str = ""


def normalize_component_code(code: str) -> str:
    return code.strip().upper().replace(" ", "_")


def _version_to_int(version_str: str) -> int:
    cleaned = version_str.strip().replace(".", "")
    return int(cleaned)


def parse_version_range(range_str: str, component: str) -> VersionRange:
    range_str = range_str.strip()

    if range_str.endswith("x"):
        prefix = range_str[:-1].replace(".", "")
        return VersionRange(
            component=component,
            min=int(prefix + "0"),
            max=int(prefix + "9"),
        )

    if "-" in range_str:
        parts = range_str.split("-")
        return VersionRange(
            component=component,
            min=_version_to_int(parts[0]),
            max=_version_to_int(parts[1]),
        )

    v = _version_to_int(range_str)
    return VersionRange(component=component, min=v, max=v)


def _normalize_priority(priority: str) -> str:
    p = priority.strip().lower()
    if p in ("hot news", "hotnews", "hot_news"):
        return "hot_news"
    if p in ("high", "medium", "low"):
        return p
    return p


def parse_note(raw: dict) -> ParsedNote:
    components = [normalize_component_code(c) for c in raw.get("components", [])]

    version_ranges = []
    for range_str in raw.get("version_ranges_raw", []):
        comp = components[0] if components else "UNKNOWN"
        version_ranges.append(parse_version_range(range_str, comp))

    return ParsedNote(
        note_number=raw["note_number"],
        title=raw.get("title", ""),
        cvss_score=raw.get("cvss_score", 0.0),
        cvss_vector=raw.get("cvss_vector", ""),
        priority=_normalize_priority(raw.get("priority", "medium")),
        components=components,
        version_ranges=version_ranges,
        release_date=raw.get("release_date", ""),
        description=raw.get("description", ""),
        solution_type=raw.get("solution_type", ""),
        related_notes=raw.get("related_notes", []),
        raw_content=raw.get("raw_content", ""),
    )
