"""Seed the database with demo data matching the mockup UI."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import init_db, get_engine
from src.models import SecurityNote, LandscapeSnapshot, LandscapeEntry, MatchResult
from sqlalchemy.orm import Session


LANDSCAPE = [
    {"sid": "PRD-ECC", "desc": "ECC production", "product": "ECC 6.0", "comp": "SAP_BASIS", "ver": "757", "ver_num": 757, "tier": "Prod", "owner": "K. Smith"},
    {"sid": "PRD-S4H", "desc": "S/4HANA production", "product": "S/4HANA 2023", "comp": "SAP_BASIS", "ver": "789", "ver_num": 789, "tier": "Prod", "owner": "K. Smith"},
    {"sid": "PRD-BW", "desc": "BW/4HANA reporting", "product": "BW/4HANA", "comp": "SAP_BW", "ver": "757", "ver_num": 757, "tier": "Prod", "owner": "J. Mueller"},
    {"sid": "QAS-ECC", "desc": "ECC quality", "product": "ECC 6.0", "comp": "SAP_BASIS", "ver": "757", "ver_num": 757, "tier": "QA", "owner": "J. Mueller"},
    {"sid": "QAS-S4H", "desc": "S/4HANA quality", "product": "S/4HANA 2023", "comp": "SAP_BASIS", "ver": "789", "ver_num": 789, "tier": "QA", "owner": "J. Mueller"},
    {"sid": "DEV-ECC", "desc": "ECC development", "product": "ECC 6.0", "comp": "SAP_BASIS", "ver": "757", "ver_num": 757, "tier": "Dev", "owner": "J. Mueller"},
    {"sid": "PRD-WDP", "desc": "Web Dispatcher", "product": "Web Dispatcher", "comp": "WEBDISP", "ver": "7.99", "ver_num": 799, "tier": "Prod", "owner": "L. Wang"},
    {"sid": "PRD-PI", "desc": "PI / PO integration", "product": "PI/PO", "comp": "SAP_XI", "ver": "7.50", "ver_num": 750, "tier": "Prod", "owner": "L. Wang"},
]

NOTES = [
    {"num": "3501122", "title": "Code injection in NetWeaver AS ABAP (Internet Communication Framework)", "cvss": 9.8, "prio": "hot_news", "comp": "SAP_BASIS", "vr_min": 750, "vr_max": 789, "desc": "An unauthenticated attacker can run arbitrary ABAP through a crafted ICF request.", "sol": "SNOTE correction"},
    {"num": "3498640", "title": "Missing authorization check in BW/4HANA query runtime", "cvss": 9.1, "prio": "hot_news", "comp": "SAP_BW", "vr_min": 750, "vr_max": 789, "desc": "A low-privileged user can read any InfoProvider including HR and finance data.", "sol": "SNOTE correction"},
    {"num": "3502310", "title": "Server-side request forgery in SAP Web Dispatcher", "cvss": 8.6, "prio": "high", "comp": "WEBDISP", "vr_min": 790, "vr_max": 800, "desc": "A crafted request to the Web Dispatcher can be relayed to internal hosts behind your DMZ.", "sol": "Kernel patch"},
    {"num": "3500988", "title": "Information disclosure in SAP Fiori Launchpad", "cvss": 7.4, "prio": "high", "comp": "SAP_BASIS", "vr_min": 750, "vr_max": 789, "desc": "Tile target mappings leak backend service paths to authenticated users.", "sol": "SNOTE correction"},
    {"num": "3501455", "title": "Stored XSS in Solution Manager work centers", "cvss": 6.1, "prio": "medium", "comp": "SAP_BASIS", "vr_min": 780, "vr_max": 790, "desc": "A stored cross-site scripting issue in the SolMan work-center UI.", "sol": "SNOTE correction"},
    {"num": "3499270", "title": "Improper session handling in SAP GUI for Windows", "cvss": 5.3, "prio": "medium", "comp": "SAP_GUI", "vr_min": 800, "vr_max": 800, "desc": "Client-side fix for SAP GUI on user desktops.", "sol": "Client rollout"},
]


def seed():
    db_path = "data/snap.db"
    Path("data").mkdir(exist_ok=True)
    init_db(db_path)
    engine = get_engine(db_path)

    with Session(engine) as session:
        existing = session.query(SecurityNote).first()
        if existing:
            print("Database already has data. Skipping seed.")
            return

        snapshot = LandscapeSnapshot(
            filename="demo_landscape.xlsx",
            system_count=len(LANDSCAPE),
            component_count=len(set(s["comp"] for s in LANDSCAPE)),
            is_active=True,
        )
        session.add(snapshot)
        session.flush()

        for s in LANDSCAPE:
            entry = LandscapeEntry(
                snapshot_id=snapshot.id,
                sid=s["sid"],
                description=s["desc"],
                product=s["product"],
                component_code=s["comp"],
                version=s["ver"],
                version_numeric=s["ver_num"],
                tier=s["tier"],
                basis_contact=s["owner"],
            )
            session.add(entry)

        for n in NOTES:
            note = SecurityNote(
                note_number=n["num"],
                title=n["title"],
                cvss_score=n["cvss"],
                priority=n["prio"],
                components=json.dumps([n["comp"]]),
                version_ranges=json.dumps([{"component": n["comp"], "min": n["vr_min"], "max": n["vr_max"]}]),
                description=n["desc"],
                solution_type=n["sol"],
                status="new",
            )
            session.add(note)

        session.commit()
        print(f"Seeded {len(NOTES)} notes and {len(LANDSCAPE)} landscape entries.")

    # Now run the matching engine against seeded data
    print("Running analysis pipeline...")
    import asyncio
    from src.landscape.indexer import build_component_index
    from src.landscape.normalizer import NormalizedEntry
    from src.matching.orchestrator import run_analysis
    from src.shared.config import RulesConfig, VersionMatching, ClaudeConfig

    with Session(engine) as session:
        db_entries = session.query(LandscapeEntry).all()
        entries = [
            NormalizedEntry(
                sid=e.sid, description=e.description or "", product=e.product or "",
                component_code=e.component_code, version=e.version or "",
                version_numeric=e.version_numeric or 0, kernel_release=e.kernel_release or "",
                tier=e.tier or "", os=e.os or "", db=e.db or "",
                business_unit=e.business_unit or "", basis_contact=e.basis_contact or "", notes=e.notes or "",
            )
            for e in db_entries
        ]

    index = build_component_index(entries)
    rules_config = RulesConfig(
        version_matching=VersionMatching(strategies=["exact_range"]),
        component_aliases={"BC-SRV-KRN": ["KERNEL", "SAP_KERNEL"], "BC-ABA": ["SAP_ABA"]},
        product_component_map={"ECC": ["SAP_BASIS", "KERNEL"], "S/4HANA": ["SAP_BASIS", "SAP_UI", "KERNEL"]},
        tier_weights={"Prod": 4, "QA": 2, "Dev": 1, "Sandbox": 0.5},
        confidence_weights={"HIGH": 1.0, "MEDIUM": 0.7, "LOW": 0.4},
    )
    claude_config = ClaudeConfig(
        default_model="", complex_model="", complex_threshold_cvss=9.0, max_tokens=4096,
    )

    async def _run():
        from unittest.mock import AsyncMock, patch
        with patch("src.matching.orchestrator.AIAnalyzer") as MockAI:
            mock_instance = MockAI.return_value
            mock_instance.analyze = AsyncMock(return_value=[])
            return await run_analysis(
                db_path=db_path, rules_config=rules_config,
                claude_config=claude_config, component_index=index,
                landscape_entries=entries,
            )

    result = asyncio.run(_run())
    print(f"Analysis complete: {result.total_matches} matches found across {result.notes_with_matches} notes.")


if __name__ == "__main__":
    seed()
