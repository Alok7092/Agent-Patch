import csv
import io
from typing import Any

import openpyxl


COLUMN_ALIASES = {
    "sid": ["system id", "sid", "system", "sap system"],
    "description": ["description", "desc", "system name", "name"],
    "product": ["product", "sap product", "application"],
    "component_code": ["component", "software component", "comp", "component code"],
    "version": ["version", "release", "component version", "ver"],
    "kernel_release": ["kernel", "kernel release", "kernel version"],
    "tier": ["tier", "environment", "env", "landscape tier"],
    "os": ["os", "operating system", "platform"],
    "db": ["db", "database", "db platform"],
    "business_unit": ["business unit", "bu", "department", "org"],
    "basis_contact": ["contact", "basis contact", "owner", "admin"],
    "notes": ["notes", "comments", "remarks"],
}


def auto_detect_columns(headers: list[str]) -> dict[str, str | None]:
    mapping = {}
    headers_lower = [h.lower().strip() for h in headers]
    for field, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in headers_lower:
                idx = headers_lower.index(alias)
                mapping[field] = headers[idx]
                break
    return mapping


def load_spreadsheet(
    file_content: bytes,
    filename: str,
    column_mapping: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    if filename.endswith(".csv"):
        return _load_csv(file_content, column_mapping)
    elif filename.endswith(".xlsx"):
        return _load_xlsx(file_content, column_mapping)
    else:
        raise ValueError(f"Unsupported file type: {filename}")


def _load_csv(
    content: bytes, column_mapping: dict[str, str] | None
) -> list[dict[str, Any]]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    if column_mapping is None:
        column_mapping = auto_detect_columns(headers)
    reverse_map = {v: k for k, v in column_mapping.items() if v is not None}
    rows = []
    for raw_row in reader:
        row = {}
        for header, value in raw_row.items():
            field = reverse_map.get(header)
            if field:
                row[field] = value.strip() if value else ""
        rows.append(row)
    return rows


def _load_xlsx(
    content: bytes, column_mapping: dict[str, str] | None
) -> list[dict[str, Any]]:
    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True)
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    headers = [str(h) if h else "" for h in next(rows_iter)]
    if column_mapping is None:
        column_mapping = auto_detect_columns(headers)
    reverse_map = {v: k for k, v in column_mapping.items() if v is not None}
    rows = []
    for raw_row in rows_iter:
        row = {}
        for idx, value in enumerate(raw_row):
            if idx < len(headers):
                field = reverse_map.get(headers[idx])
                if field:
                    row[field] = str(value).strip() if value else ""
        rows.append(row)
    return rows
