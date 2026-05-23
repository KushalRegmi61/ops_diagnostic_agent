from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, default="created")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    langfuse_trace_id: Mapped[str | None] = mapped_column(String, nullable=True)

    files: Mapped[list["FileRecord"]] = relationship(back_populates="run")


class FileRecord(Base):
    __tablename__ = "files"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id"), nullable=True)
    file_name: Mapped[str] = mapped_column(String)
    mime_type: Mapped[str] = mapped_column(String)
    blob_path: Mapped[str] = mapped_column(String)
    parser_status: Mapped[str] = mapped_column(String, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    run: Mapped[Run | None] = relationship(back_populates="files")


class FileSummaryRecord(Base):
    __tablename__ = "file_summaries"

    file_id: Mapped[str] = mapped_column(ForeignKey("files.id"), primary_key=True)
    payload_json: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class IntakeBundleRecord(Base):
    __tablename__ = "intake_bundles"

    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), primary_key=True)
    payload_json: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BlueprintRecord(Base):
    __tablename__ = "blueprints"

    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), primary_key=True)
    payload_json: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
