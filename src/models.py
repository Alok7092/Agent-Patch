from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, Text, Float, Boolean, DateTime, Date,
    ForeignKey, String,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class SecurityNote(Base):
    __tablename__ = "security_notes"

    id = Column(Integer, primary_key=True)
    note_number = Column(Text, unique=True, nullable=False)
    title = Column(Text)
    cvss_score = Column(Float)
    cvss_vector = Column(Text)
    priority = Column(Text)
    components = Column(Text)
    version_ranges = Column(Text)
    release_date = Column(Date)
    description = Column(Text)
    solution_type = Column(Text)
    related_notes = Column(Text)
    raw_content = Column(Text)
    ingested_at = Column(DateTime, default=datetime.utcnow)
    status = Column(Text, default="new")

    match_results = relationship("MatchResult", back_populates="note")
    ai_analyses = relationship("AIAnalysis", back_populates="note")


class LandscapeSnapshot(Base):
    __tablename__ = "landscape_snapshots"

    id = Column(Integer, primary_key=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    filename = Column(Text)
    system_count = Column(Integer)
    component_count = Column(Integer)
    is_active = Column(Boolean, default=True)

    entries = relationship("LandscapeEntry", back_populates="snapshot")


class LandscapeEntry(Base):
    __tablename__ = "landscape_entries"

    id = Column(Integer, primary_key=True)
    snapshot_id = Column(Integer, ForeignKey("landscape_snapshots.id"))
    sid = Column(Text)
    description = Column(Text)
    product = Column(Text)
    component_code = Column(Text)
    version = Column(Text)
    version_numeric = Column(Integer)
    kernel_release = Column(Text)
    tier = Column(Text)
    os = Column(Text)
    db = Column(Text)
    business_unit = Column(Text)
    basis_contact = Column(Text)
    notes = Column(Text)

    snapshot = relationship("LandscapeSnapshot", back_populates="entries")


class MatchResult(Base):
    __tablename__ = "match_results"

    id = Column(Integer, primary_key=True)
    note_id = Column(Integer, ForeignKey("security_notes.id"))
    note_number = Column(Text)
    sid = Column(Text)
    component = Column(Text)
    system_version = Column(Text)
    affected_range = Column(Text)
    tier = Column(Text)
    confidence = Column(Text)
    match_source = Column(Text)
    match_reason = Column(Text)
    priority_score = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(Text, default="pending")
    dismissed_by = Column(Text)
    dismissed_at = Column(DateTime)
    gate_outcome = Column(Text)
    manual_review_code = Column(Text)
    review_response = Column(Text)
    reviewed_by = Column(Text)
    reviewed_at = Column(DateTime)

    note = relationship("SecurityNote", back_populates="match_results")


class AIAnalysis(Base):
    __tablename__ = "ai_analyses"

    id = Column(Integer, primary_key=True)
    note_id = Column(Integer, ForeignKey("security_notes.id"))
    note_number = Column(Text)
    decision = Column(Text)
    decision_confidence = Column(Float)
    evidence_coverage = Column(Float)
    critical_unknowns = Column(Text)
    assumptions = Column(Text)
    contradictions = Column(Text)
    evidence = Column(Text)
    manual_review_triggers = Column(Text)
    exclusion_evidence = Column(Text)
    gate_outcome = Column(Text)
    gate_reason = Column(Text)
    verification_run = Column(Boolean, default=False)
    verification_result = Column(Text)
    raw_response = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    note = relationship("SecurityNote", back_populates="ai_analyses")


class ApprovalQueueItem(Base):
    __tablename__ = "approval_queue"

    id = Column(Integer, primary_key=True)
    note_number = Column(Text)
    sid = Column(Text)
    confidence = Column(Text)
    approved_by = Column(Text)
    approved_at = Column(DateTime)
    status = Column(Text, default="approved")
    cr_number = Column(Text)
    cr_created_at = Column(DateTime)
