import io
import re
import openpyxl


def parse_sap_landscape_excel(file_content: bytes) -> list[dict]:
    """Parse SAP landscape export Excel into normalized rows.

    Expected columns:
    - SAP System ID
    - Software Component Version According to PPMS (format: "COMP_NAME VERSION (COMP_NAME VERSION)")
    - Support Package (SP) Version
    """
    wb = openpyxl.load_workbook(io.BytesIO(file_content), read_only=True)
    ws = wb.active

    rows_iter = ws.iter_rows(values_only=True)
    headers = [str(h).strip() if h else "" for h in next(rows_iter)]

    col_map = {}
    for idx, h in enumerate(headers):
        hl = h.lower()
        if "system id" in hl or "sid" == hl:
            col_map["sid"] = idx
        elif "software component" in hl or "component version" in hl:
            col_map["component_combined"] = idx
        elif hl == "component" or hl == "comp":
            col_map["component"] = idx
        elif hl == "version" or hl == "release":
            col_map["version"] = idx
        elif "support package" in hl or "sp level" in hl or "sp" == hl:
            col_map["sp"] = idx

    if "sid" not in col_map:
        raise ValueError(f"Could not find SID column. Found headers: {headers}")
    if "component" not in col_map and "component_combined" not in col_map:
        raise ValueError(f"Could not find Component column. Found headers: {headers}")

    entries = []
    for row in rows_iter:
        if not row or not row[col_map["sid"]]:
            continue

        sid = str(row[col_map["sid"]]).strip()
        sp_version = str(row[col_map["sp"]] or "").strip() if "sp" in col_map else ""

        if "component_combined" in col_map:
            comp_raw = str(row[col_map["component_combined"]] or "").strip()
            component_code, version, version_numeric = _parse_component_field(comp_raw)
        else:
            component_code = str(row[col_map["component"]] or "").strip()
            version = str(row[col_map.get("version", col_map["component"])] or "").strip() if "version" in col_map else ""
            version_numeric = _version_to_numeric(version) if version else 0

        if not component_code:
            continue

        entries.append({
            "sid": sid,
            "description": "",
            "product": "",
            "component_code": component_code,
            "version": version,
            "version_numeric": version_numeric,
            "kernel_release": "",
            "tier": "",
            "os": "",
            "db": "",
            "business_unit": "",
            "basis_contact": "",
            "notes": f"SP: {sp_version}" if sp_version else "",
        })

    wb.close()
    return entries


def _parse_component_field(raw: str) -> tuple[str, str, int]:
    """Parse 'SAP_BASIS 757 (SAP_BASIS 757)' into (component_code, version, version_numeric)."""
    # Remove the parenthetical portion if present
    clean = re.sub(r'\s*\(.*?\)\s*$', '', raw).strip()
    if not clean:
        return ("", "", 0)

    parts = clean.split()
    if len(parts) >= 2:
        component_code = parts[0]
        version_str = parts[1]
        # Handle versions like "757", "7.57", "600_700", "2011_1_731"
        version_numeric = _version_to_numeric(version_str)
        return (component_code, version_str, version_numeric)
    else:
        return (clean, "", 0)


def _version_to_numeric(version_str: str) -> int:
    """Convert version string to numeric for matching.

    Examples: "757" -> 757, "7.57" -> 757, "600_700" -> 600, "2011_1_731" -> 731
    """
    # If it's a simple integer
    cleaned = version_str.replace(".", "")
    # Handle underscore-separated versions (take last meaningful part)
    if "_" in cleaned:
        parts = cleaned.split("_")
        # Try the last part as version
        for part in reversed(parts):
            try:
                return int(part)
            except ValueError:
                continue
        return 0
    try:
        return int(cleaned)
    except ValueError:
        return 0


def _infer_tier(sid: str) -> str:
    """Infer system tier from SID naming conventions."""
    sid_upper = sid.upper()
    if sid_upper.endswith("P") or sid_upper.startswith("P") or "PRD" in sid_upper:
        return "Prod"
    elif sid_upper.endswith("Q") or "QAS" in sid_upper or "QA" in sid_upper:
        return "QA"
    elif sid_upper.endswith("D") or "DEV" in sid_upper:
        return "Dev"
    elif sid_upper.endswith("S") or "SBX" in sid_upper or "SAND" in sid_upper:
        return "Sandbox"
    return "Unknown"
