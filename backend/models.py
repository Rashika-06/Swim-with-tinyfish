from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.database import Base

class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(512), unique=True, index=True, nullable=False)
    title = Column(String(255), default="")
    snippet = Column(Text, default="")
    text = Column(Text, default="")
    fetched_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    fetch_status = Column(String(50), default="SUCCESS")  # SUCCESS, FAILED, EMPTY, BLOCKED
    error_msg = Column(Text, default="")
    is_synthetic = Column(Boolean, default=False)

    facts = relationship("ExtractedFact", back_populates="source", cascade="all, delete-orphan")


class ExtractedFact(Base):
    __tablename__ = "extracted_facts"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=True)
    location = Column(String(100), nullable=False, index=True)
    district = Column(String(100), nullable=False, index=True)  # e.g., Ganjam, Gajapati
    item = Column(String(100), nullable=False, index=True)      # e.g., Drinking Water, Food Rations, Tarpaulins
    record_type = Column(String(50), nullable=False)            # NEED, SUPPLY, DAMAGE, RESTORATION, RESCUE
    quantity = Column(Float, nullable=True)
    unit = Column(String(50), nullable=True)
    urgency = Column(String(50), default="UNKNOWN")             # CRITICAL, HIGH, MEDIUM, LOW, UNKNOWN
    report_date = Column(String(50), nullable=True)
    evidence_quote = Column(Text, nullable=False)
    is_verified = Column(Boolean, default=False)
    verification_notes = Column(Text, default="")
    is_synthetic = Column(Boolean, default=False)

    source = relationship("Source", back_populates="facts")


class Finding(Base):
    __tablename__ = "findings"

    id = Column(Integer, primary_key=True, index=True)
    district = Column(String(100), nullable=False, index=True)
    location = Column(String(100), nullable=False, index=True)
    item = Column(String(100), nullable=False, index=True)
    classification = Column(String(50), nullable=False, index=True)  # GAP, CONFLICT, UNKNOWN, COVERED
    priority = Column(String(20), default="MEDIUM", index=True)      # HIGH, MEDIUM, LOW
    reasoning = Column(Text, nullable=False)

    need_fact_id = Column(Integer, ForeignKey("extracted_facts.id"), nullable=True)
    supply_fact_id = Column(Integer, ForeignKey("extracted_facts.id"), nullable=True)
    conflict_fact_id = Column(Integer, ForeignKey("extracted_facts.id"), nullable=True)

    partial_percentage = Column(Float, nullable=True)

    review_status = Column(String(50), default="PENDING")  # PENDING, APPROVED, REJECTED, INVESTIGATING
    reviewer_notes = Column(Text, default="")
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_synthetic = Column(Boolean, default=False)

    need_fact = relationship("ExtractedFact", foreign_keys=[need_fact_id])
    supply_fact = relationship("ExtractedFact", foreign_keys=[supply_fact_id])
    conflict_fact = relationship("ExtractedFact", foreign_keys=[conflict_fact_id])
    reviews = relationship("ReviewAction", back_populates="finding", cascade="all, delete-orphan")


class ReviewAction(Base):
    __tablename__ = "review_actions"

    id = Column(Integer, primary_key=True, index=True)
    finding_id = Column(Integer, ForeignKey("findings.id"), nullable=False)
    action = Column(String(50), nullable=False)  # APPROVE, REJECT, INVESTIGATE
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    finding = relationship("Finding", back_populates="reviews")
