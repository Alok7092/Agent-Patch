from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger


def setup_scheduler(app, cron_expression: str):
    scheduler = AsyncIOScheduler()

    if cron_expression:
        parts = cron_expression.split()
        if len(parts) == 5:
            trigger = CronTrigger(
                minute=parts[0], hour=parts[1], day=parts[2],
                month=parts[3], day_of_week=parts[4]
            )
            scheduler.add_job(
                _scheduled_analysis, trigger, args=[app], id="monthly_analysis"
            )

    scheduler.start()
    app.state.scheduler = scheduler
    return scheduler


async def _scheduled_analysis(app):
    from src.matching.orchestrator import run_analysis
    from src.landscape.indexer import build_component_index
    from src.landscape.normalizer import NormalizedEntry
    from src.models import LandscapeSnapshot, LandscapeEntry
    from src.database import get_engine
    from sqlalchemy.orm import Session

    db_path = app.state.db_path
    settings = app.state.settings
    engine = get_engine(db_path)

    with Session(engine) as session:
        snapshot = session.query(LandscapeSnapshot).filter_by(is_active=True).first()
        if not snapshot:
            return
        db_entries = session.query(LandscapeEntry).filter_by(snapshot_id=snapshot.id).all()
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
    from src.shared.config import load_rules
    from pathlib import Path
    rules_path = Path("config/rules.yaml")
    if rules_path.exists():
        rules_config = load_rules(rules_path)
    else:
        from src.shared.config import RulesConfig, VersionMatching
        rules_config = RulesConfig(
            version_matching=VersionMatching(strategies=["exact_range"]),
            component_aliases={},
            product_component_map={},
            tier_weights={"Prod": 4, "QA": 2, "Dev": 1, "Sandbox": 0.5},
            confidence_weights={"HIGH": 1.0, "MEDIUM": 0.7, "LOW": 0.4},
        )

    await run_analysis(
        db_path=db_path,
        rules_config=rules_config,
        claude_config=settings.claude,
        component_index=index,
        landscape_entries=entries,
    )
