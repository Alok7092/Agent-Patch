from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from src.models import Base

_engines: dict[str, any] = {}


def get_engine(db_path: str):
    if db_path not in _engines:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        _engines[db_path] = create_engine(f"sqlite:///{db_path}", echo=False)
    return _engines[db_path]


def _migrate_match_results(engine):
    new_cols = [
        ("gate_outcome", "TEXT"),
        ("manual_review_code", "TEXT"),
        ("review_response", "TEXT"),
        ("reviewed_by", "TEXT"),
        ("reviewed_at", "DATETIME"),
    ]
    with engine.connect() as conn:
        for col_name, col_type in new_cols:
            try:
                conn.execute(text(
                    f"ALTER TABLE match_results ADD COLUMN {col_name} {col_type}"
                ))
            except Exception:
                pass
        conn.commit()


def init_db(db_path: str) -> None:
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    _migrate_match_results(engine)


def get_session(db_path: str) -> Session:
    engine = get_engine(db_path)
    return Session(engine)
