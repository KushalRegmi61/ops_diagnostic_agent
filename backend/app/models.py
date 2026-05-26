"""SQLAlchemy ORM models for the diagnostic agent's persistence layer.

Five tables back the pipeline outputs: `runs`, `files`, `file_summaries`,
`intake_bundles`, and `blueprints`. Large agent payloads (FileSummary,
IntakeBundle, Blueprint) are serialized to JSON strings in `payload_json`
columns rather than normalized — they are append-only artifacts keyed by
run_id or file_id.
"""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utc_now() -> datetime:
    """Return the current UTC time as a tz-aware datetime."""
    return datetime.now(timezone.utc)


class TZDateTime(TypeDecorator):
    """DateTime column that always returns tz-aware UTC datetimes.

    Stores as a naive UTC timestamp (SQLite-compatible); re-attaches
    ``timezone.utc`` on load so consumers always see tz-aware objects.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> datetime | None:
        """Strip tzinfo before writing; value is already UTC from _utc_now."""
        if value is not None and value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value: Any, dialect: Dialect) -> datetime | None:
        """Re-attach UTC tzinfo on read-back."""
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class Run(Base):
    """A single diagnostic run — its status, creation time, and optional Langfuse trace id."""

    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, default="created")
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=_utc_now)
    langfuse_trace_id: Mapped[str | None] = mapped_column(String, nullable=True)

    files: Mapped[list["FileRecord"]] = relationship(back_populates="run")


class FileRecord(Base):
    """An uploaded file: name, mime, blob path on disk, parser status, and optional run linkage."""

    __tablename__ = "files"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id"), nullable=True)
    file_name: Mapped[str] = mapped_column(String)
    mime_type: Mapped[str] = mapped_column(String)
    blob_path: Mapped[str] = mapped_column(String)
    parser_status: Mapped[str] = mapped_column(String, default="pending")
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=_utc_now)

    run: Mapped[Run | None] = relationship(back_populates="files")


class FileSummaryRecord(Base):
    """Persisted per-file agent output (FileSummary) stored as JSON keyed by file_id."""

    __tablename__ = "file_summaries"

    file_id: Mapped[str] = mapped_column(
        ForeignKey("files.id", ondelete="CASCADE"), primary_key=True
    )
    payload_json: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=_utc_now)


class IntakeBundleRecord(Base):
    """Persisted synthesis output (IntakeBundle) stored as JSON keyed by run_id."""

    __tablename__ = "intake_bundles"

    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), primary_key=True
    )
    payload_json: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=_utc_now)


class BlueprintRecord(Base):
    """Persisted final automation Blueprint stored as JSON keyed by run_id."""

    __tablename__ = "blueprints"

    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), primary_key=True
    )
    payload_json: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=_utc_now)
