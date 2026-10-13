import csv
import io
import json
from src.ingestion.parser import parse_note, ParsedNote


def process_upload(file_content: bytes, filename: str) -> list[ParsedNote]:
    if filename.endswith(".csv"):
        return _parse_csv(file_content)
    elif filename.endswith(".json"):
        return _parse_json(file_content)
    elif filename.endswith(".txt"):
        return _parse_text(file_content)
    else:
        raise ValueError(f"Unsupported file format: {filename}")


def _parse_csv(content: bytes) -> list[ParsedNote]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    notes = []
    for row in reader:
        raw = {
            "note_number": row.get("note_number", row.get("Note Number", "")),
            "title": row.get("title", row.get("Title", "")),
            "cvss_score": float(row.get("cvss_score", row.get("CVSS", "0"))),
            "priority": row.get("priority", row.get("Priority", "medium")),
            "components": _split_list(row.get("components", row.get("Components", ""))),
            "version_ranges_raw": _split_list(row.get("versions", row.get("Affected Versions", ""))),
            "release_date": row.get("release_date", row.get("Release Date", "")),
            "description": row.get("description", row.get("Description", "")),
            "solution_type": row.get("solution_type", row.get("Solution Type", "patch")),
        }
        notes.append(parse_note(raw))
    return notes


def _parse_json(content: bytes) -> list[ParsedNote]:
    data = json.loads(content)
    if isinstance(data, list):
        return [parse_note(raw) for raw in data]
    if "results" in data:
        return [parse_note(raw) for raw in data["results"]]
    return [parse_note(data)]


def _parse_text(content: bytes) -> list[ParsedNote]:
    text = content.decode("utf-8")
    raw = {
        "note_number": "MANUAL",
        "title": text[:100],
        "cvss_score": 0.0,
        "priority": "medium",
        "components": [],
        "version_ranges_raw": [],
        "release_date": "",
        "description": text,
        "solution_type": "unknown",
    }
    return [parse_note(raw)]


def _split_list(value: str) -> list[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]
