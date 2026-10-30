from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Meeting(Base):
    __tablename__ = "meetings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(20), default="meeting")  # meeting | handover
    agenda: Mapped[str] = mapped_column(Text, default="")
    date: Mapped[date] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="planned")  # planned | held | closed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    participants = relationship("Participant", cascade="all, delete-orphan", back_populates="meeting")
    decisions = relationship("Decision", cascade="all, delete-orphan", back_populates="meeting")
    action_items = relationship("ActionItem", cascade="all, delete-orphan", back_populates="meeting",
                                foreign_keys="ActionItem.meeting_id")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(20), default="member")  # admin | member
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    session_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Participant(Base):
    __tablename__ = "participants"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id"))
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(200), default="")
    rsvp: Mapped[str] = mapped_column(String(20), default="pending")  # pending | accepted | declined
    attended: Mapped[bool] = mapped_column(Boolean, default=False)
    meeting = relationship("Meeting", back_populates="participants")


class Decision(Base):
    __tablename__ = "decisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id"))
    text: Mapped[str] = mapped_column(Text)
    meeting = relationship("Meeting", back_populates="decisions")


class ActionItem(Base):
    __tablename__ = "action_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id"))
    original_meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id"))
    parent_item_id: Mapped[int | None] = mapped_column(ForeignKey("action_items.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    owner: Mapped[str] = mapped_column(String(100), default="")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    blocker: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open|in_progress|done|dropped|carried
    outcome: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    meeting = relationship("Meeting", back_populates="action_items", foreign_keys=[meeting_id])
    history = relationship("ActionItemHistory", cascade="all, delete-orphan",
                           order_by="ActionItemHistory.id", back_populates="item")
    links = relationship("Link", cascade="all, delete-orphan", back_populates="item")


class ActionItemHistory(Base):
    __tablename__ = "action_item_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("action_items.id"))
    event: Mapped[str] = mapped_column(String(40))
    old_value: Mapped[str] = mapped_column(Text, default="")
    new_value: Mapped[str] = mapped_column(Text, default="")
    note: Mapped[str] = mapped_column(Text, default="")
    at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    item = relationship("ActionItem", back_populates="history")


class KBDocument(Base):
    __tablename__ = "kb_documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(20), default="doc")  # doc | past_meeting
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class KBChunk(Base):
    __tablename__ = "kb_chunks"
    __table_args__ = (UniqueConstraint("kb_doc_id", "chunk_index", name="uq_kb_chunk_doc_index"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kb_doc_id: Mapped[int] = mapped_column(ForeignKey("kb_documents.id"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64))
    content: Mapped[str] = mapped_column(Text)
    embedding_model: Mapped[str] = mapped_column(String(100))
    embedding: Mapped[list[float]] = mapped_column(JSON)


class Link(Base):
    __tablename__ = "links"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("action_items.id"))
    kb_doc_id: Mapped[int] = mapped_column(ForeignKey("kb_documents.id"))
    score: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(10), default="ai")  # ai | tfidf
    item = relationship("ActionItem", back_populates="links")
    kb_doc = relationship("KBDocument")
