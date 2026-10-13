import io
import re
from datetime import datetime
import openpyxl
from src.ingestion.parser import ParsedNote, VersionRange


PRIORITY_MAP = {
    "hotnews": "hot_news",
    "correction with high priority": "high",
    "correction with medium priority": "medium",
    "correction with low priority": "low",
}


def _normalize_priority(raw: str) -> str:
    return PRIORITY_MAP.get(raw.strip().lower(), "medium")


def _extract_cve(title: str) -> str:
    match = re.search(r'\[CVE-\d{4}-\d+\]', title)
    if match:
        return match.group(0).strip("[]")
    matches = re.findall(r'CVE-\d{4}-\d+', title)
    return matches[0] if matches else ""


def _clean_title(title: str) -> str:
    return re.sub(r'\[(?:CVE-\d{4}-\d+|Multiple CVEs)\]\s*', '', title).strip()


def _parse_date(val) -> str:
    if val is None:
        return ""
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    return str(val).split(" ")[0] if val else ""


def parse_sap_excel(file_content: bytes) -> list[ParsedNote]:
    wb = openpyxl.load_workbook(io.BytesIO(file_content), read_only=True)
    ws = wb.active

    rows_iter = ws.iter_rows(values_only=True)
    headers = [str(h).strip() if h else "" for h in next(rows_iter)]

    col_map = {}
    for idx, h in enumerate(headers):
        hl = h.lower()
        if "number" == hl or "note number" in hl:
            col_map["number"] = idx
        elif "title" == hl:
            col_map["title"] = idx
        elif "cvss score" in hl:
            col_map["cvss_score"] = idx
        elif "cvss vector" in hl:
            col_map["cvss_vector"] = idx
        elif "component" in hl:
            col_map["component"] = idx
        elif "priority" == hl:
            col_map["priority"] = idx
        elif "released on" == hl:
            col_map["released_on"] = idx
        elif "category" == hl:
            col_map["category"] = idx
        elif "link" == hl:
            col_map["link"] = idx

    notes = []
    for row in rows_iter:
        if not row or not row[col_map.get("number", 0)]:
            continue

        note_number = str(int(row[col_map["number"]])) if isinstance(row[col_map["number"]], (int, float)) else str(row[col_map["number"]]).strip()
        raw_title = str(row[col_map.get("title", 1)] or "")
        cve = _extract_cve(raw_title)
        title = _clean_title(raw_title)

        cvss_score = 0.0
        if "cvss_score" in col_map and row[col_map["cvss_score"]]:
            try:
                cvss_score = float(row[col_map["cvss_score"]])
            except (ValueError, TypeError):
                pass

        cvss_vector = str(row[col_map.get("cvss_vector", 4)] or "")
        component = str(row[col_map.get("component", 0)] or "").strip()
        priority = _normalize_priority(str(row[col_map.get("priority", 6)] or "medium"))
        released_on = _parse_date(row[col_map.get("released_on", 7)])
        category = str(row[col_map.get("category", 5)] or "")
        link = str(row[col_map.get("link", 9)] or "")

        parsed = ParsedNote(
            note_number=note_number,
            title=title,
            cvss_score=cvss_score,
            cvss_vector=cve if cve else cvss_vector,
            priority=priority,
            components=[component] if component else [],
            version_ranges=[],
            release_date=released_on,
            description=title,
            solution_type=category,
            raw_content=link,
        )
        notes.append(parsed)

    wb.close()
    return notes
