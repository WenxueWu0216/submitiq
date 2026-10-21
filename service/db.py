"""Persistence: Postgres when DATABASE_URL is set (postgresql+psycopg://...), else a local SQLite file."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

DEFAULT_URL = f"sqlite:///{Path(__file__).with_name('submitiq.db')}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class SubmissionRow(Base):
    __tablename__ = "submissions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), index=True)       # needs_review | auto_cleared | approved | failed
    package_dir: Mapped[str] = mapped_column(Text)
    result: Mapped[dict] = mapped_column(JSON)                         # PipelineResult as JSON (current state)
    original_result: Mapped[dict] = mapped_column(JSON)                # as the pipeline produced it
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)


class CorrectionRow(Base):
    """One human correction. These become new eval cases (scripts/export_corrections.py)."""
    __tablename__ = "corrections"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.id"), index=True)
    field_path: Mapped[str] = mapped_column(String(256))
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_status: Mapped[str] = mapped_column(String(32))              # status before the correction
    extractor: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewer: Mapped[str] = mapped_column(String(128))
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


def make_session_factory(url: str | None = None) -> sessionmaker[Session]:
    url = url or os.environ.get("DATABASE_URL", DEFAULT_URL)
    engine = create_engine(url, future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


__all__ = ["SubmissionRow", "CorrectionRow", "make_session_factory", "select"]
