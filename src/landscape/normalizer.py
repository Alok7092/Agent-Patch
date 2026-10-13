from dataclasses import dataclass


@dataclass
class NormalizedEntry:
    sid: str
    description: str
    product: str
    component_code: str
    version: str
    version_numeric: int
    kernel_release: str
    tier: str
    os: str
    db: str
    business_unit: str
    basis_contact: str
    notes: str


def normalize_component(code: str, aliases: dict[str, list[str]]) -> str:
    upper = code.strip().upper()
    if upper in aliases:
        return upper
    for canonical, alias_list in aliases.items():
        if upper in [a.upper() for a in alias_list]:
            return canonical
    return upper.replace(" ", "_")


def normalize_version(version: str | None) -> int:
    if not version:
        return 0
    cleaned = str(version).strip().replace(".", "")
    try:
        return int(cleaned)
    except ValueError:
        return 0


def normalize_entry(row: dict, component_aliases: dict[str, list[str]]) -> NormalizedEntry:
    return NormalizedEntry(
        sid=row.get("sid", "").strip(),
        description=row.get("description", ""),
        product=row.get("product", ""),
        component_code=normalize_component(row.get("component_code", ""), component_aliases),
        version=row.get("version", ""),
        version_numeric=normalize_version(row.get("version", "")),
        kernel_release=row.get("kernel_release", ""),
        tier=row.get("tier", "").strip(),
        os=row.get("os", ""),
        db=row.get("db", ""),
        business_unit=row.get("business_unit", ""),
        basis_contact=row.get("basis_contact", ""),
        notes=row.get("notes", ""),
    )
