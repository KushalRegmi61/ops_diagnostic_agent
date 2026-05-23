# Backend Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the FastAPI backend foundation, file ingestion + parsing layer (10 file types with locator anchors), and LLM provider layer (Ollama / OpenAI / Groq / OpenAI-compatible — no mock). After this plan, the backend can accept uploads, parse them into anchored content, return source excerpts at any locator, and call a real LLM to return schema-valid JSON.

**Architecture:** FastAPI app with typed Pydantic-settings config, SQLAlchemy 2.x with create-all-on-startup persistence (SQLite default for dev), an on-disk blob store, a parser registry routed by MIME type, and a provider-agnostic LLM interface with a single `generate_json` method that returns parsed JSON plus generation metadata. Every parser exports `parse(path) -> ParsedFile` and `excerpt(parsed, locator) -> str` so citations stay roundtrip-able. Every LLM call is testable against a real local Ollama model with `temperature=0`.

**Tech Stack:** Python 3.11, FastAPI, Uvicorn, SQLAlchemy 2.x, Pydantic v2, pydantic-settings, httpx, PyMuPDF (`pymupdf`), python-docx, pandas, openpyxl, webvtt-py, srt, openai (SDK), pytest, pytest-asyncio.

**Source spec:** [`docs/superpowers/specs/2026-05-23-real-files-diagnostic-redesign-design.md`](../specs/2026-05-23-real-files-diagnostic-redesign-design.md)

---

## File Structure

```
backend/
  pyproject.toml
  .env.example
  app/
    __init__.py
    main.py                  # FastAPI app + route registration
    config.py                # typed settings
    database.py              # engine, session, get_db
    models.py                # runs, files tables (Plan 1 scope only)
    schemas.py               # Source, Locator union, ParsedFile, FileRef, ExtractionError
    blob_store.py            # on-disk blob save/load
    parsers/
      __init__.py            # parse(path, mime_type) registry + ParsedFile type
      pdf.py
      docx.py
      md.py
      txt.py
      vtt.py
      srt.py
      csv.py
      xlsx.py
      mbox.py
      json.py                # inside package, does not shadow stdlib
    services/
      __init__.py
      files.py               # upload + parse orchestration
    llm/
      __init__.py            # generate_json + GenerateMetadata + provider factory
      base.py                # LLMProvider protocol + GenerateMetadata
      ollama.py
      openai.py
      groq.py
      openai_compat.py
  tests/
    conftest.py              # fixture path helpers, FastAPI TestClient
    fixtures/
      make_fixtures.py       # script to generate binary fixtures
      sop.pdf
      sop.docx
      notes.md
      notes.txt
      call.vtt
      call.srt
      leads.csv
      leads.xlsx
      inbox.mbox
      crm.json
    test_health.py
    test_blob_store.py
    test_parsers_pdf.py
    test_parsers_docx.py
    test_parsers_md.py
    test_parsers_txt.py
    test_parsers_vtt.py
    test_parsers_srt.py
    test_parsers_csv.py
    test_parsers_xlsx.py
    test_parsers_mbox.py
    test_parsers_json.py
    test_parsers_registry.py
    test_files_api.py
    test_excerpt_api.py
    test_llm_ollama.py
    test_llm_openai_smoke.py  # skipped unless OPENAI_API_KEY set
Makefile
```

**Out of scope for this plan (handled in Plan 2 and Plan 3):** all LLM agents, LangGraph parent workflow, Redis checkpointer, Langfuse observability, persistence for `file_summaries`/`intake_bundles`/`blueprints`, Next.js frontend, `/samples` realistic dataset, `make demo`.

---

## Task 1: Repo Scaffolding

**Files:**
- Create: `Makefile`
- Create: `backend/pyproject.toml`
- Create: `backend/.env.example`
- Create: `backend/app/__init__.py` (empty)
- Modify: `.gitignore`

- [ ] **Step 1: Create `Makefile`**

```makefile
.PHONY: install dev test fixtures

install:
	cd backend && python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"

dev:
	cd backend && . .venv/bin/activate && uvicorn app.main:app --reload

test:
	cd backend && . .venv/bin/activate && pytest -v

fixtures:
	cd backend && . .venv/bin/activate && python tests/fixtures/make_fixtures.py
```

- [ ] **Step 2: Create `backend/pyproject.toml`**

```toml
[project]
name = "ops-diagnostic-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "sqlalchemy>=2.0",
  "pydantic>=2.7",
  "pydantic-settings>=2.3",
  "httpx>=0.27",
  "python-multipart>=0.0.9",
  "pymupdf>=1.24",
  "python-docx>=1.1",
  "pandas>=2.2",
  "openpyxl>=3.1",
  "webvtt-py>=0.5",
  "srt>=3.5",
  "openai>=1.40",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2",
  "pytest-asyncio>=0.23",
  "httpx>=0.27",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 3: Create `backend/.env.example`**

```bash
# Database
DATABASE_URL=sqlite:///./ops_diagnostic.db

# Blob store
BLOB_STORE_DIR=./blobs

# LLM provider — choose one of: ollama, openai, groq, openai_compatible
LLM_PROVIDER=ollama

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b

# OpenAI
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini

# Groq Cloud
GROQ_API_KEY=
GROQ_BASE_URL=https://api.groq.com/openai/v1
GROQ_MODEL=llama-3.3-70b-versatile

# OpenAI-compatible
OPENAI_COMPATIBLE_API_KEY=
OPENAI_COMPATIBLE_BASE_URL=
OPENAI_COMPATIBLE_MODEL=
```

- [ ] **Step 4: Create `backend/app/__init__.py`** (empty file)

- [ ] **Step 5: Append to `.gitignore`**

```
backend/.venv/
backend/blobs/
backend/*.db
backend/.env
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 6: Install dependencies**

Run: `make install`
Expected: clean install, no errors. Activate venv with `cd backend && source .venv/bin/activate` for subsequent tasks.

- [ ] **Step 7: Commit**

```bash
git add Makefile backend/pyproject.toml backend/.env.example backend/app/__init__.py .gitignore
git commit -m "feat: scaffold backend project with deps and Makefile"
```

---

## Task 2: Typed Settings (`config.py`)

**Files:**
- Create: `backend/app/config.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_config.py`

- [ ] **Step 1: Write the failing test** in `backend/tests/test_config.py`

```python
import os
from app.config import Settings

def test_settings_loads_defaults(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("BLOB_STORE_DIR", "./test_blobs")
    s = Settings()
    assert s.llm_provider == "ollama"
    assert s.database_url == "sqlite:///./test.db"
    assert s.ollama_base_url == "http://localhost:11434"
    assert s.ollama_model == "llama3.1:8b"

def test_settings_rejects_unknown_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("BLOB_STORE_DIR", "./test_blobs")
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Settings()
```

- [ ] **Step 2: Create `backend/tests/conftest.py`**

```python
import sys
from pathlib import Path

# Make the `app` package importable when running pytest from backend/
sys.path.insert(0, str(Path(__file__).parent.parent))
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.config'`

- [ ] **Step 4: Implement `backend/app/config.py`**

```python
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    database_url: str
    blob_store_dir: str

    llm_provider: Literal["ollama", "openai", "groq", "openai_compatible"] = "ollama"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"

    groq_api_key: str | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "llama-3.3-70b-versatile"

    openai_compatible_api_key: str | None = None
    openai_compatible_base_url: str | None = None
    openai_compatible_model: str | None = None


def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS (both tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/config.py backend/tests/conftest.py backend/tests/test_config.py
git commit -m "feat: typed settings with provider validation"
```

---

## Task 3: FastAPI Shell + Health Endpoint

**Files:**
- Create: `backend/app/main.py`
- Create: `backend/tests/test_health.py`

- [ ] **Step 1: Write the failing test** in `backend/tests/test_health.py`

```python
from fastapi.testclient import TestClient
from app.main import app

def test_health_returns_ok():
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_health.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 3: Implement `backend/app/main.py`**

```python
from fastapi import FastAPI

app = FastAPI(title="Ops Diagnostic Agent", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_health.py -v`
Expected: PASS

- [ ] **Step 5: Manual sanity check**

Run: `make dev` then in another terminal `curl http://localhost:8000/health`
Expected: `{"status":"ok"}`. Stop the server.

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py backend/tests/test_health.py
git commit -m "feat: FastAPI shell with /health endpoint"
```

---

## Task 4: Database Engine and Session

**Files:**
- Create: `backend/app/database.py`
- Create: `backend/tests/test_database.py`

- [ ] **Step 1: Write the failing test** in `backend/tests/test_database.py`

```python
from sqlalchemy import text
from app.database import engine, SessionLocal


def test_engine_connects():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
        assert result == 1


def test_session_factory_yields_session():
    with SessionLocal() as session:
        assert session.is_active
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_database.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `backend/app/database.py`**

```python
from typing import Iterator
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


_settings = get_settings()

engine = create_engine(
    _settings.database_url,
    connect_args={"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 4: Set up test env**

Create `backend/.env` (do NOT commit) with:

```bash
DATABASE_URL=sqlite:///./test.db
BLOB_STORE_DIR=./test_blobs
LLM_PROVIDER=ollama
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_database.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/database.py backend/tests/test_database.py
git commit -m "feat: SQLAlchemy engine and session factory"
```

---

## Task 5: Database Models (`runs`, `files`)

**Files:**
- Create: `backend/app/models.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_models.py`

- [ ] **Step 1: Write the failing test** in `backend/tests/test_models.py`

```python
from datetime import datetime
from app.database import Base, engine, SessionLocal
from app.models import Run, FileRecord


def setup_module():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_insert_and_retrieve_run():
    with SessionLocal() as s:
        run = Run(id="run_test_1", status="created")
        s.add(run)
        s.commit()
        loaded = s.get(Run, "run_test_1")
        assert loaded is not None
        assert loaded.status == "created"
        assert isinstance(loaded.created_at, datetime)


def test_insert_file_with_locator_metadata():
    with SessionLocal() as s:
        f = FileRecord(
            id="f_test_1",
            run_id=None,
            file_name="hello.pdf",
            mime_type="application/pdf",
            blob_path="/tmp/hello.pdf",
            parser_status="ok",
        )
        s.add(f)
        s.commit()
        loaded = s.get(FileRecord, "f_test_1")
        assert loaded.file_name == "hello.pdf"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models'`.

- [ ] **Step 3: Implement `backend/app/models.py`**

```python
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey
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
```

- [ ] **Step 4: Update `backend/app/main.py` to create tables on startup**

```python
from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.database import Base, engine
from app import models  # noqa: F401  (register tables with metadata)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="Ops Diagnostic Agent", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 6: Re-run all tests**

Run: `pytest -v`
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/models.py backend/app/main.py backend/tests/test_models.py
git commit -m "feat: Run and FileRecord SQLAlchemy models with create-all-on-startup"
```

---

## Task 6: Pydantic Schemas — Source, Locators, ParsedFile

**Files:**
- Create: `backend/app/schemas.py`
- Create: `backend/tests/test_schemas.py`

- [ ] **Step 1: Write the failing test** in `backend/tests/test_schemas.py`

```python
import pytest
from pydantic import ValidationError
from app.schemas import (
    Source,
    PdfLocator,
    TextLocator,
    TranscriptLocator,
    TableLocator,
    XlsxLocator,
    MboxLocator,
    JsonLocator,
    DocxLocator,
    ParsedFile,
    ParsedSegment,
    ExtractionError,
)


def test_pdf_locator_validates():
    loc = PdfLocator(page=2, span_start=10, span_end=40)
    assert loc.type == "pdf"
    assert loc.model_dump()["page"] == 2


def test_source_attaches_locator():
    src = Source(
        file_id="f1",
        file_name="sop.pdf",
        type="pdf",
        locator={"type": "pdf", "page": 2, "span_start": 10, "span_end": 40},
    )
    assert src.locator["page"] == 2


def test_transcript_locator_requires_timestamps():
    with pytest.raises(ValidationError):
        TranscriptLocator(line_start=1, line_end=2)  # missing ts_start, ts_end


def test_parsed_file_has_segments_with_locators():
    pf = ParsedFile(
        file_id="f1",
        file_name="x.pdf",
        type="pdf",
        segments=[
            ParsedSegment(text="hello", locator={"type": "pdf", "page": 1, "span_start": 0, "span_end": 5}),
        ],
    )
    assert pf.segments[0].text == "hello"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_schemas.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `backend/app/schemas.py`**

```python
from typing import Literal, Annotated, Union
from pydantic import BaseModel, Field


class PdfLocator(BaseModel):
    type: Literal["pdf"] = "pdf"
    page: int
    span_start: int
    span_end: int


class DocxLocator(BaseModel):
    type: Literal["docx"] = "docx"
    paragraph_index: int
    span_start: int
    span_end: int


class TextLocator(BaseModel):
    type: Literal["text"] = "text"
    line_start: int
    line_end: int


class TranscriptLocator(BaseModel):
    type: Literal["transcript"] = "transcript"
    line_start: int
    line_end: int
    ts_start: str
    ts_end: str


class TableLocator(BaseModel):
    type: Literal["table"] = "table"
    row_index: int


class XlsxLocator(BaseModel):
    type: Literal["xlsx"] = "xlsx"
    sheet: str
    row_index: int


class MboxLocator(BaseModel):
    type: Literal["mbox"] = "mbox"
    message_id: str
    section: Literal["header", "body"] = "body"


class JsonLocator(BaseModel):
    type: Literal["json"] = "json"
    pointer: str  # RFC 6901


AnyLocator = Annotated[
    Union[
        PdfLocator, DocxLocator, TextLocator, TranscriptLocator,
        TableLocator, XlsxLocator, MboxLocator, JsonLocator,
    ],
    Field(discriminator="type"),
]


FileType = Literal[
    "pdf", "docx", "md", "txt",
    "transcript_vtt", "transcript_srt",
    "csv", "xlsx", "mbox", "json",
]


class Source(BaseModel):
    file_id: str
    file_name: str
    type: FileType
    locator: dict


class ParsedSegment(BaseModel):
    text: str
    locator: dict


class ParsedFile(BaseModel):
    file_id: str
    file_name: str
    type: FileType
    segments: list[ParsedSegment]


class ExtractionError(BaseModel):
    file_id: str
    stage: Literal["parse", "agent", "review"]
    message: str


class FileRef(BaseModel):
    file_id: str
    file_name: str
    mime_type: str
    blob_path: str
    parser_status: Literal["ok", "error", "pending"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_schemas.py -v`
Expected: PASS (all four tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas.py backend/tests/test_schemas.py
git commit -m "feat: typed Source, locator union, ParsedFile, ExtractionError schemas"
```

---

## Task 7: Blob Store

**Files:**
- Create: `backend/app/blob_store.py`
- Create: `backend/tests/test_blob_store.py`

- [ ] **Step 1: Write the failing test** in `backend/tests/test_blob_store.py`

```python
from pathlib import Path
from app.blob_store import save_blob, load_blob, blob_path_for


def test_save_and_load_blob(tmp_path, monkeypatch):
    monkeypatch.setattr("app.blob_store.BLOB_DIR", tmp_path)
    path = save_blob("f_abc", "hello.pdf", b"binary-data")
    assert Path(path).exists()
    assert load_blob("f_abc", "hello.pdf") == b"binary-data"


def test_blob_path_includes_file_id(tmp_path, monkeypatch):
    monkeypatch.setattr("app.blob_store.BLOB_DIR", tmp_path)
    p = blob_path_for("f_xyz", "doc.txt")
    assert "f_xyz" in str(p)
    assert p.name == "doc.txt"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_blob_store.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `backend/app/blob_store.py`**

```python
from pathlib import Path
from app.config import get_settings


BLOB_DIR = Path(get_settings().blob_store_dir)


def blob_path_for(file_id: str, file_name: str) -> Path:
    return BLOB_DIR / file_id / file_name


def save_blob(file_id: str, file_name: str, content: bytes) -> str:
    path = blob_path_for(file_id, file_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return str(path)


def load_blob(file_id: str, file_name: str) -> bytes:
    return blob_path_for(file_id, file_name).read_bytes()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_blob_store.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/blob_store.py backend/tests/test_blob_store.py
git commit -m "feat: on-disk blob store keyed by file_id"
```

---

## Task 8: Fixture Generation Script

**Files:**
- Create: `backend/tests/fixtures/__init__.py` (empty)
- Create: `backend/tests/fixtures/make_fixtures.py`

This task creates all binary/text fixtures used by parser tests. Running it is idempotent — re-running overwrites.

- [ ] **Step 1: Create `backend/tests/fixtures/__init__.py`** (empty file)

- [ ] **Step 2: Implement `backend/tests/fixtures/make_fixtures.py`**

```python
"""Generate all parser test fixtures. Idempotent."""
import json
import mailbox
from pathlib import Path

import fitz  # PyMuPDF
from docx import Document
import pandas as pd
import openpyxl


FIXTURE_DIR = Path(__file__).parent


def make_pdf() -> None:
    doc = fitz.open()
    page1 = doc.new_page()
    page1.insert_text((72, 72), "Inbound Lead SOP\nStep 1: collect contact info.\nStep 2: send document request.")
    page2 = doc.new_page()
    page2.insert_text((72, 72), "Renewal SOP\nStep 1: pull declarations page.\nStep 2: email renewal quote.")
    doc.save(FIXTURE_DIR / "sop.pdf")
    doc.close()


def make_docx() -> None:
    doc = Document()
    doc.add_paragraph("Onboarding SOP")
    doc.add_paragraph("Step 1: verify lead identity.")
    doc.add_paragraph("Step 2: open file in Applied Epic.")
    doc.save(FIXTURE_DIR / "sop.docx")


def make_md() -> None:
    (FIXTURE_DIR / "notes.md").write_text(
        "# Producer Notes\n\nLeads waiting > 24h before first response.\nCSR manually copies CRM notes.\n"
    )


def make_txt() -> None:
    (FIXTURE_DIR / "notes.txt").write_text(
        "Discovery call summary.\nClient mentioned slow document collection.\nProducer follow-up inconsistent.\n"
    )


def make_vtt() -> None:
    (FIXTURE_DIR / "call.vtt").write_text(
        "WEBVTT\n\n"
        "00:00:01.000 --> 00:00:05.000\n"
        "Founder: our biggest issue is lead response time.\n\n"
        "00:00:06.000 --> 00:00:10.000\n"
        "CSR: we copy notes from email to HubSpot manually.\n"
    )


def make_srt() -> None:
    (FIXTURE_DIR / "call.srt").write_text(
        "1\n00:00:01,000 --> 00:00:05,000\nFounder: our biggest issue is lead response time.\n\n"
        "2\n00:00:06,000 --> 00:00:10,000\nCSR: we copy notes from email to HubSpot manually.\n"
    )


def make_csv() -> None:
    df = pd.DataFrame(
        [
            {"name": "Acme Corp", "email": "ops@acme.com", "stage": "awaiting_docs", "days_in_stage": 12},
            {"name": "Beta LLC", "email": "hi@beta.com", "stage": "new", "days_in_stage": 1},
            {"name": "Gamma Inc", "email": "info@gamma.com", "stage": "awaiting_docs", "days_in_stage": 30},
        ]
    )
    df.to_csv(FIXTURE_DIR / "leads.csv", index=False)


def make_xlsx() -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Leads"
    ws.append(["name", "email", "stage", "days_in_stage"])
    ws.append(["Acme Corp", "ops@acme.com", "awaiting_docs", 12])
    ws.append(["Beta LLC", "hi@beta.com", "new", 1])
    wb.save(FIXTURE_DIR / "leads.xlsx")


def make_mbox() -> None:
    path = FIXTURE_DIR / "inbox.mbox"
    if path.exists():
        path.unlink()
    mbox = mailbox.mbox(str(path))
    msg = mailbox.mboxMessage()
    msg["From"] = "lead@acme.com"
    msg["To"] = "csr@agency.com"
    msg["Subject"] = "Need a quote"
    msg["Message-ID"] = "<msg-001@acme.com>"
    msg.set_payload("Hi, we need a commercial liability quote ASAP. Please send the document list.")
    mbox.add(msg)
    mbox.close()


def make_json() -> None:
    payload = {
        "contacts": [
            {"id": "c1", "name": "Acme Corp", "last_touch_days": 12, "stage": "awaiting_docs"},
            {"id": "c2", "name": "Beta LLC", "last_touch_days": 1, "stage": "new"},
        ]
    }
    (FIXTURE_DIR / "crm.json").write_text(json.dumps(payload, indent=2))


def main() -> None:
    make_pdf()
    make_docx()
    make_md()
    make_txt()
    make_vtt()
    make_srt()
    make_csv()
    make_xlsx()
    make_mbox()
    make_json()
    print(f"Fixtures written to {FIXTURE_DIR}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the script**

Run: `make fixtures`
Expected: `Fixtures written to .../tests/fixtures` and 10 fixture files present in `backend/tests/fixtures/`.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/fixtures/__init__.py backend/tests/fixtures/make_fixtures.py \
        backend/tests/fixtures/sop.pdf backend/tests/fixtures/sop.docx \
        backend/tests/fixtures/notes.md backend/tests/fixtures/notes.txt \
        backend/tests/fixtures/call.vtt backend/tests/fixtures/call.srt \
        backend/tests/fixtures/leads.csv backend/tests/fixtures/leads.xlsx \
        backend/tests/fixtures/inbox.mbox backend/tests/fixtures/crm.json
git commit -m "test: parser fixtures (PDF, DOCX, MD, TXT, VTT, SRT, CSV, XLSX, MBOX, JSON)"
```

---

## Task 9: PDF Parser

**Files:**
- Create: `backend/app/parsers/__init__.py`
- Create: `backend/app/parsers/pdf.py`
- Create: `backend/tests/test_parsers_pdf.py`

- [ ] **Step 1: Write the failing test** in `backend/tests/test_parsers_pdf.py`

```python
from pathlib import Path
from app.parsers.pdf import parse, excerpt
from app.schemas import PdfLocator

FIXTURE = Path(__file__).parent / "fixtures" / "sop.pdf"


def test_parse_pdf_emits_segments_per_page():
    pf = parse(file_id="f1", file_name="sop.pdf", path=FIXTURE)
    assert pf.type == "pdf"
    assert len(pf.segments) >= 2
    assert pf.segments[0].locator["page"] == 1
    assert pf.segments[1].locator["page"] == 2
    assert "Inbound Lead SOP" in pf.segments[0].text


def test_excerpt_returns_text_at_locator():
    pf = parse(file_id="f1", file_name="sop.pdf", path=FIXTURE)
    seg = pf.segments[0]
    loc = PdfLocator(page=1, span_start=0, span_end=len(seg.text))
    text = excerpt(pf, loc.model_dump())
    assert text.startswith("Inbound Lead SOP")


def test_excerpt_invalid_page_raises():
    pf = parse(file_id="f1", file_name="sop.pdf", path=FIXTURE)
    import pytest
    with pytest.raises(ValueError):
        excerpt(pf, {"type": "pdf", "page": 999, "span_start": 0, "span_end": 5})
```

- [ ] **Step 2: Create `backend/app/parsers/__init__.py`**

```python
"""Parser registry. Each parser module exposes parse() and excerpt()."""
from pathlib import Path
from app.schemas import ParsedFile


def parse(file_id: str, file_name: str, path: Path, mime_type: str) -> ParsedFile:
    if mime_type == "application/pdf":
        from app.parsers import pdf
        return pdf.parse(file_id=file_id, file_name=file_name, path=path)
    raise ValueError(f"No parser registered for mime_type={mime_type}")
```

Note: the registry will be extended in later tasks as more parsers are added.

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_parsers_pdf.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.parsers.pdf'`.

- [ ] **Step 4: Implement `backend/app/parsers/pdf.py`**

```python
from pathlib import Path
import fitz

from app.schemas import ParsedFile, ParsedSegment


def parse(*, file_id: str, file_name: str, path: Path) -> ParsedFile:
    doc = fitz.open(path)
    segments: list[ParsedSegment] = []
    for page_num, page in enumerate(doc, start=1):
        text = page.get_text()
        segments.append(ParsedSegment(
            text=text,
            locator={"type": "pdf", "page": page_num, "span_start": 0, "span_end": len(text)},
        ))
    doc.close()
    return ParsedFile(file_id=file_id, file_name=file_name, type="pdf", segments=segments)


def excerpt(parsed: ParsedFile, locator: dict) -> str:
    page = locator["page"]
    span_start = locator["span_start"]
    span_end = locator["span_end"]
    for seg in parsed.segments:
        if seg.locator["page"] == page:
            return seg.text[span_start:span_end]
    raise ValueError(f"Page {page} not found in parsed file")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_parsers_pdf.py -v`
Expected: PASS (all three tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/parsers/__init__.py backend/app/parsers/pdf.py backend/tests/test_parsers_pdf.py
git commit -m "feat: PDF parser with page+span locators"
```

---

## Task 10: DOCX Parser

**Files:**
- Create: `backend/app/parsers/docx.py`
- Modify: `backend/app/parsers/__init__.py` — add docx route
- Create: `backend/tests/test_parsers_docx.py`

- [ ] **Step 1: Write the failing test** in `backend/tests/test_parsers_docx.py`

```python
from pathlib import Path
from app.parsers.docx import parse, excerpt

FIXTURE = Path(__file__).parent / "fixtures" / "sop.docx"


def test_parse_docx_emits_segments_per_paragraph():
    pf = parse(file_id="f1", file_name="sop.docx", path=FIXTURE)
    assert pf.type == "docx"
    assert len(pf.segments) == 3
    assert pf.segments[0].text == "Onboarding SOP"
    assert pf.segments[0].locator["paragraph_index"] == 0


def test_excerpt_returns_paragraph_slice():
    pf = parse(file_id="f1", file_name="sop.docx", path=FIXTURE)
    seg = pf.segments[1]
    text = excerpt(pf, {
        "type": "docx",
        "paragraph_index": 1,
        "span_start": 0,
        "span_end": len(seg.text),
    })
    assert text.startswith("Step 1")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_parsers_docx.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `backend/app/parsers/docx.py`**

```python
from pathlib import Path
from docx import Document

from app.schemas import ParsedFile, ParsedSegment


def parse(*, file_id: str, file_name: str, path: Path) -> ParsedFile:
    doc = Document(str(path))
    segments: list[ParsedSegment] = []
    for idx, para in enumerate(doc.paragraphs):
        text = para.text
        segments.append(ParsedSegment(
            text=text,
            locator={"type": "docx", "paragraph_index": idx, "span_start": 0, "span_end": len(text)},
        ))
    return ParsedFile(file_id=file_id, file_name=file_name, type="docx", segments=segments)


def excerpt(parsed: ParsedFile, locator: dict) -> str:
    idx = locator["paragraph_index"]
    span_start = locator["span_start"]
    span_end = locator["span_end"]
    for seg in parsed.segments:
        if seg.locator["paragraph_index"] == idx:
            return seg.text[span_start:span_end]
    raise ValueError(f"Paragraph {idx} not found")
```

- [ ] **Step 4: Update `backend/app/parsers/__init__.py`** to register docx

```python
"""Parser registry. Each parser module exposes parse() and excerpt()."""
from pathlib import Path
from app.schemas import ParsedFile


_MIME_ROUTES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}


def parse(file_id: str, file_name: str, path: Path, mime_type: str) -> ParsedFile:
    module_name = _MIME_ROUTES.get(mime_type)
    if module_name is None:
        raise ValueError(f"No parser registered for mime_type={mime_type}")
    mod = __import__(f"app.parsers.{module_name}", fromlist=["parse"])
    return mod.parse(file_id=file_id, file_name=file_name, path=path)
```

- [ ] **Step 5: Run tests to verify pass**

Run: `pytest tests/test_parsers_docx.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/parsers/docx.py backend/app/parsers/__init__.py backend/tests/test_parsers_docx.py
git commit -m "feat: DOCX parser with paragraph+span locators"
```

---

## Task 11: MD Parser

**Files:**
- Create: `backend/app/parsers/md.py`
- Modify: `backend/app/parsers/__init__.py` — add `text/markdown`
- Create: `backend/tests/test_parsers_md.py`

- [ ] **Step 1: Write the failing test** in `backend/tests/test_parsers_md.py`

```python
from pathlib import Path
from app.parsers.md import parse, excerpt

FIXTURE = Path(__file__).parent / "fixtures" / "notes.md"


def test_parse_md_emits_one_segment_per_line():
    pf = parse(file_id="f1", file_name="notes.md", path=FIXTURE)
    assert pf.type == "md"
    assert pf.segments[0].locator["line_start"] == 1
    assert "Producer Notes" in pf.segments[0].text


def test_excerpt_returns_lines_in_range():
    pf = parse(file_id="f1", file_name="notes.md", path=FIXTURE)
    text = excerpt(pf, {"type": "text", "line_start": 3, "line_end": 3})
    assert "Leads waiting" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_parsers_md.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `backend/app/parsers/md.py`**

```python
from pathlib import Path

from app.schemas import ParsedFile, ParsedSegment


def _parse_lines(path: Path, file_id: str, file_name: str, file_type: str) -> ParsedFile:
    raw = path.read_text()
    lines = raw.splitlines()
    segments = [
        ParsedSegment(
            text=line,
            locator={"type": "text", "line_start": i + 1, "line_end": i + 1},
        )
        for i, line in enumerate(lines)
    ]
    return ParsedFile(file_id=file_id, file_name=file_name, type=file_type, segments=segments)


def parse(*, file_id: str, file_name: str, path: Path) -> ParsedFile:
    return _parse_lines(path, file_id, file_name, "md")


def excerpt(parsed: ParsedFile, locator: dict) -> str:
    start = locator["line_start"]
    end = locator["line_end"]
    lines = [
        seg.text for seg in parsed.segments
        if start <= seg.locator["line_start"] <= end
    ]
    if not lines:
        raise ValueError(f"No lines in range [{start},{end}]")
    return "\n".join(lines)
```

- [ ] **Step 4: Update `backend/app/parsers/__init__.py`** to register md

```python
"""Parser registry. Each parser module exposes parse() and excerpt()."""
from pathlib import Path
from app.schemas import ParsedFile


_MIME_ROUTES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/markdown": "md",
}


def parse(file_id: str, file_name: str, path: Path, mime_type: str) -> ParsedFile:
    module_name = _MIME_ROUTES.get(mime_type)
    if module_name is None:
        raise ValueError(f"No parser registered for mime_type={mime_type}")
    mod = __import__(f"app.parsers.{module_name}", fromlist=["parse"])
    return mod.parse(file_id=file_id, file_name=file_name, path=path)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_parsers_md.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/parsers/md.py backend/app/parsers/__init__.py backend/tests/test_parsers_md.py
git commit -m "feat: Markdown parser with line locators"
```

---

## Task 12: TXT Parser

**Files:**
- Create: `backend/app/parsers/txt.py`
- Modify: `backend/app/parsers/__init__.py` — add `text/plain`
- Create: `backend/tests/test_parsers_txt.py`

- [ ] **Step 1: Write the failing test** in `backend/tests/test_parsers_txt.py`

```python
from pathlib import Path
from app.parsers.txt import parse, excerpt

FIXTURE = Path(__file__).parent / "fixtures" / "notes.txt"


def test_parse_txt_emits_lines():
    pf = parse(file_id="f1", file_name="notes.txt", path=FIXTURE)
    assert pf.type == "txt"
    assert len(pf.segments) == 3
    assert pf.segments[0].locator == {"type": "text", "line_start": 1, "line_end": 1}


def test_excerpt_returns_line_range():
    pf = parse(file_id="f1", file_name="notes.txt", path=FIXTURE)
    text = excerpt(pf, {"type": "text", "line_start": 2, "line_end": 3})
    assert "document collection" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_parsers_txt.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `backend/app/parsers/txt.py`**

```python
from pathlib import Path
from app.parsers.md import _parse_lines, excerpt as _md_excerpt
from app.schemas import ParsedFile


def parse(*, file_id: str, file_name: str, path: Path) -> ParsedFile:
    return _parse_lines(path, file_id, file_name, "txt")


def excerpt(parsed: ParsedFile, locator: dict) -> str:
    return _md_excerpt(parsed, locator)
```

- [ ] **Step 4: Update `backend/app/parsers/__init__.py`** to register txt

Add to `_MIME_ROUTES`: `"text/plain": "txt"`.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_parsers_txt.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/parsers/txt.py backend/app/parsers/__init__.py backend/tests/test_parsers_txt.py
git commit -m "feat: TXT parser with line locators"
```

---

## Task 13: VTT Parser

**Files:**
- Create: `backend/app/parsers/vtt.py`
- Modify: `backend/app/parsers/__init__.py` — add `text/vtt`
- Create: `backend/tests/test_parsers_vtt.py`

- [ ] **Step 1: Write the failing test** in `backend/tests/test_parsers_vtt.py`

```python
from pathlib import Path
from app.parsers.vtt import parse, excerpt

FIXTURE = Path(__file__).parent / "fixtures" / "call.vtt"


def test_parse_vtt_emits_cues_with_timestamps():
    pf = parse(file_id="f1", file_name="call.vtt", path=FIXTURE)
    assert pf.type == "transcript_vtt"
    assert len(pf.segments) == 2
    loc0 = pf.segments[0].locator
    assert loc0["type"] == "transcript"
    assert loc0["ts_start"] == "00:00:01.000"
    assert "lead response time" in pf.segments[0].text


def test_excerpt_returns_cue_text():
    pf = parse(file_id="f1", file_name="call.vtt", path=FIXTURE)
    loc = pf.segments[1].locator
    text = excerpt(pf, loc)
    assert "manually" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_parsers_vtt.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `backend/app/parsers/vtt.py`**

```python
from pathlib import Path
import webvtt

from app.schemas import ParsedFile, ParsedSegment


def parse(*, file_id: str, file_name: str, path: Path) -> ParsedFile:
    segments: list[ParsedSegment] = []
    for idx, caption in enumerate(webvtt.read(str(path)), start=1):
        segments.append(ParsedSegment(
            text=caption.text,
            locator={
                "type": "transcript",
                "line_start": idx,
                "line_end": idx,
                "ts_start": caption.start,
                "ts_end": caption.end,
            },
        ))
    return ParsedFile(file_id=file_id, file_name=file_name, type="transcript_vtt", segments=segments)


def excerpt(parsed: ParsedFile, locator: dict) -> str:
    line = locator["line_start"]
    for seg in parsed.segments:
        if seg.locator["line_start"] == line:
            return seg.text
    raise ValueError(f"Cue {line} not found")
```

- [ ] **Step 4: Update `backend/app/parsers/__init__.py`** — add `"text/vtt": "vtt"` to `_MIME_ROUTES`.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_parsers_vtt.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/parsers/vtt.py backend/app/parsers/__init__.py backend/tests/test_parsers_vtt.py
git commit -m "feat: VTT transcript parser with timestamp locators"
```

---

## Task 14: SRT Parser

**Files:**
- Create: `backend/app/parsers/srt.py`
- Modify: `backend/app/parsers/__init__.py` — add `application/x-subrip`
- Create: `backend/tests/test_parsers_srt.py`

- [ ] **Step 1: Write the failing test** in `backend/tests/test_parsers_srt.py`

```python
from pathlib import Path
from app.parsers.srt import parse, excerpt

FIXTURE = Path(__file__).parent / "fixtures" / "call.srt"


def test_parse_srt_emits_cues_with_timestamps():
    pf = parse(file_id="f1", file_name="call.srt", path=FIXTURE)
    assert pf.type == "transcript_srt"
    assert len(pf.segments) == 2
    loc = pf.segments[0].locator
    assert loc["type"] == "transcript"
    assert "00:00:01" in loc["ts_start"]


def test_excerpt_returns_cue_text():
    pf = parse(file_id="f1", file_name="call.srt", path=FIXTURE)
    text = excerpt(pf, pf.segments[1].locator)
    assert "manually" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_parsers_srt.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `backend/app/parsers/srt.py`**

```python
from pathlib import Path
import srt as srtlib

from app.schemas import ParsedFile, ParsedSegment


def parse(*, file_id: str, file_name: str, path: Path) -> ParsedFile:
    raw = path.read_text()
    segments: list[ParsedSegment] = []
    for idx, sub in enumerate(srtlib.parse(raw), start=1):
        segments.append(ParsedSegment(
            text=sub.content,
            locator={
                "type": "transcript",
                "line_start": idx,
                "line_end": idx,
                "ts_start": str(sub.start),
                "ts_end": str(sub.end),
            },
        ))
    return ParsedFile(file_id=file_id, file_name=file_name, type="transcript_srt", segments=segments)


def excerpt(parsed: ParsedFile, locator: dict) -> str:
    line = locator["line_start"]
    for seg in parsed.segments:
        if seg.locator["line_start"] == line:
            return seg.text
    raise ValueError(f"Cue {line} not found")
```

- [ ] **Step 4: Update `backend/app/parsers/__init__.py`** — add `"application/x-subrip": "srt"`.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_parsers_srt.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/parsers/srt.py backend/app/parsers/__init__.py backend/tests/test_parsers_srt.py
git commit -m "feat: SRT transcript parser with timestamp locators"
```

---

## Task 15: CSV Parser

**Files:**
- Create: `backend/app/parsers/csv.py`
- Modify: `backend/app/parsers/__init__.py` — add `text/csv`
- Create: `backend/tests/test_parsers_csv.py`

- [ ] **Step 1: Write the failing test** in `backend/tests/test_parsers_csv.py`

```python
from pathlib import Path
from app.parsers.csv import parse, excerpt

FIXTURE = Path(__file__).parent / "fixtures" / "leads.csv"


def test_parse_csv_emits_one_segment_per_row():
    pf = parse(file_id="f1", file_name="leads.csv", path=FIXTURE)
    assert pf.type == "csv"
    assert len(pf.segments) == 3
    loc = pf.segments[0].locator
    assert loc["type"] == "table"
    assert loc["row_index"] == 0
    assert "Acme" in pf.segments[0].text


def test_excerpt_returns_row_text():
    pf = parse(file_id="f1", file_name="leads.csv", path=FIXTURE)
    text = excerpt(pf, {"type": "table", "row_index": 2})
    assert "Gamma" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_parsers_csv.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `backend/app/parsers/csv.py`**

```python
from pathlib import Path
import pandas as pd

from app.schemas import ParsedFile, ParsedSegment


def parse(*, file_id: str, file_name: str, path: Path) -> ParsedFile:
    df = pd.read_csv(path)
    segments: list[ParsedSegment] = []
    for idx, row in df.iterrows():
        text = " | ".join(f"{c}={row[c]}" for c in df.columns)
        segments.append(ParsedSegment(
            text=text,
            locator={"type": "table", "row_index": int(idx)},
        ))
    return ParsedFile(file_id=file_id, file_name=file_name, type="csv", segments=segments)


def excerpt(parsed: ParsedFile, locator: dict) -> str:
    idx = locator["row_index"]
    for seg in parsed.segments:
        if seg.locator["row_index"] == idx:
            return seg.text
    raise ValueError(f"Row {idx} not found")
```

- [ ] **Step 4: Update `backend/app/parsers/__init__.py`** — add `"text/csv": "csv"`.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_parsers_csv.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/parsers/csv.py backend/app/parsers/__init__.py backend/tests/test_parsers_csv.py
git commit -m "feat: CSV parser with row locators"
```

---

## Task 16: XLSX Parser

**Files:**
- Create: `backend/app/parsers/xlsx.py`
- Modify: `backend/app/parsers/__init__.py` — add xlsx mime
- Create: `backend/tests/test_parsers_xlsx.py`

- [ ] **Step 1: Write the failing test** in `backend/tests/test_parsers_xlsx.py`

```python
from pathlib import Path
from app.parsers.xlsx import parse, excerpt

FIXTURE = Path(__file__).parent / "fixtures" / "leads.xlsx"


def test_parse_xlsx_emits_one_segment_per_row_per_sheet():
    pf = parse(file_id="f1", file_name="leads.xlsx", path=FIXTURE)
    assert pf.type == "xlsx"
    assert len(pf.segments) == 2
    loc = pf.segments[0].locator
    assert loc["type"] == "xlsx"
    assert loc["sheet"] == "Leads"
    assert loc["row_index"] == 0


def test_excerpt_returns_row_text():
    pf = parse(file_id="f1", file_name="leads.xlsx", path=FIXTURE)
    text = excerpt(pf, {"type": "xlsx", "sheet": "Leads", "row_index": 1})
    assert "Beta" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_parsers_xlsx.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `backend/app/parsers/xlsx.py`**

```python
from pathlib import Path
import openpyxl

from app.schemas import ParsedFile, ParsedSegment


def parse(*, file_id: str, file_name: str, path: Path) -> ParsedFile:
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    segments: list[ParsedSegment] = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            continue
        headers = [str(c) if c is not None else "" for c in rows[0]]
        for r_idx, row in enumerate(rows[1:]):
            cells = [f"{headers[i] if i < len(headers) else ''}={v}" for i, v in enumerate(row)]
            text = " | ".join(cells)
            segments.append(ParsedSegment(
                text=text,
                locator={"type": "xlsx", "sheet": sheet_name, "row_index": r_idx},
            ))
    wb.close()
    return ParsedFile(file_id=file_id, file_name=file_name, type="xlsx", segments=segments)


def excerpt(parsed: ParsedFile, locator: dict) -> str:
    sheet = locator["sheet"]
    idx = locator["row_index"]
    for seg in parsed.segments:
        if seg.locator["sheet"] == sheet and seg.locator["row_index"] == idx:
            return seg.text
    raise ValueError(f"Sheet={sheet!r} row={idx} not found")
```

- [ ] **Step 4: Update `backend/app/parsers/__init__.py`** — add `"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx"`.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_parsers_xlsx.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/parsers/xlsx.py backend/app/parsers/__init__.py backend/tests/test_parsers_xlsx.py
git commit -m "feat: XLSX parser with sheet+row locators"
```

---

## Task 17: MBOX Parser

**Files:**
- Create: `backend/app/parsers/mbox.py`
- Modify: `backend/app/parsers/__init__.py` — add `application/mbox`
- Create: `backend/tests/test_parsers_mbox.py`

- [ ] **Step 1: Write the failing test** in `backend/tests/test_parsers_mbox.py`

```python
from pathlib import Path
from app.parsers.mbox import parse, excerpt

FIXTURE = Path(__file__).parent / "fixtures" / "inbox.mbox"


def test_parse_mbox_emits_one_segment_per_message():
    pf = parse(file_id="f1", file_name="inbox.mbox", path=FIXTURE)
    assert pf.type == "mbox"
    assert len(pf.segments) >= 1
    loc = pf.segments[0].locator
    assert loc["type"] == "mbox"
    assert "msg-001" in loc["message_id"]
    assert "commercial liability" in pf.segments[0].text.lower()


def test_excerpt_returns_body_for_message_id():
    pf = parse(file_id="f1", file_name="inbox.mbox", path=FIXTURE)
    text = excerpt(pf, {"type": "mbox", "message_id": "<msg-001@acme.com>", "section": "body"})
    assert "quote" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_parsers_mbox.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `backend/app/parsers/mbox.py`**

```python
from pathlib import Path
import mailbox

from app.schemas import ParsedFile, ParsedSegment


def parse(*, file_id: str, file_name: str, path: Path) -> ParsedFile:
    mbox = mailbox.mbox(str(path))
    segments: list[ParsedSegment] = []
    try:
        for msg in mbox:
            msg_id = msg.get("Message-ID", "<unknown>")
            payload = msg.get_payload()
            if isinstance(payload, list):
                payload = "".join(p.get_payload() if hasattr(p, "get_payload") else str(p) for p in payload)
            body = payload if isinstance(payload, str) else str(payload)
            segments.append(ParsedSegment(
                text=body,
                locator={"type": "mbox", "message_id": msg_id, "section": "body"},
            ))
    finally:
        mbox.close()
    return ParsedFile(file_id=file_id, file_name=file_name, type="mbox", segments=segments)


def excerpt(parsed: ParsedFile, locator: dict) -> str:
    msg_id = locator["message_id"]
    section = locator.get("section", "body")
    for seg in parsed.segments:
        if seg.locator["message_id"] == msg_id and seg.locator["section"] == section:
            return seg.text
    raise ValueError(f"Message {msg_id} ({section}) not found")
```

- [ ] **Step 4: Update `backend/app/parsers/__init__.py`** — add `"application/mbox": "mbox"`.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_parsers_mbox.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/parsers/mbox.py backend/app/parsers/__init__.py backend/tests/test_parsers_mbox.py
git commit -m "feat: MBOX parser with message-id locators"
```

---

## Task 18: JSON Parser

**Files:**
- Create: `backend/app/parsers/json.py`
- Modify: `backend/app/parsers/__init__.py` — add `application/json`
- Create: `backend/tests/test_parsers_json.py`

- [ ] **Step 1: Write the failing test** in `backend/tests/test_parsers_json.py`

```python
from pathlib import Path
from app.parsers.json import parse, excerpt

FIXTURE = Path(__file__).parent / "fixtures" / "crm.json"


def test_parse_json_emits_leaf_segments_with_pointers():
    pf = parse(file_id="f1", file_name="crm.json", path=FIXTURE)
    assert pf.type == "json"
    pointers = [seg.locator["pointer"] for seg in pf.segments]
    assert any(p.startswith("/contacts/0") for p in pointers)
    assert any("name" in p for p in pointers)


def test_excerpt_returns_leaf_value():
    pf = parse(file_id="f1", file_name="crm.json", path=FIXTURE)
    text = excerpt(pf, {"type": "json", "pointer": "/contacts/0/name"})
    assert text == "Acme Corp"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_parsers_json.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `backend/app/parsers/json.py`**

```python
from pathlib import Path
import json as _json

from app.schemas import ParsedFile, ParsedSegment


def _flatten(obj, prefix: str = "") -> list[tuple[str, str]]:
    """Walk JSON, emit (pointer, leaf_text) pairs using RFC 6901 pointers."""
    out: list[tuple[str, str]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = str(k).replace("~", "~0").replace("/", "~1")
            out.extend(_flatten(v, f"{prefix}/{key}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.extend(_flatten(v, f"{prefix}/{i}"))
    else:
        out.append((prefix or "/", str(obj)))
    return out


def parse(*, file_id: str, file_name: str, path: Path) -> ParsedFile:
    data = _json.loads(path.read_text())
    pairs = _flatten(data)
    segments = [
        ParsedSegment(text=val, locator={"type": "json", "pointer": ptr})
        for ptr, val in pairs
    ]
    return ParsedFile(file_id=file_id, file_name=file_name, type="json", segments=segments)


def excerpt(parsed: ParsedFile, locator: dict) -> str:
    ptr = locator["pointer"]
    for seg in parsed.segments:
        if seg.locator["pointer"] == ptr:
            return seg.text
    raise ValueError(f"Pointer {ptr} not found")
```

- [ ] **Step 4: Update `backend/app/parsers/__init__.py`** — add `"application/json": "json"`.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_parsers_json.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/parsers/json.py backend/app/parsers/__init__.py backend/tests/test_parsers_json.py
git commit -m "feat: JSON parser with RFC 6901 pointer locators"
```

---

## Task 19: Parser Registry Integration Test

**Files:**
- Create: `backend/tests/test_parsers_registry.py`

- [ ] **Step 1: Write the test** in `backend/tests/test_parsers_registry.py`

```python
from pathlib import Path
import pytest
from app.parsers import parse

FIX = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    "file_name,mime_type,expected_type",
    [
        ("sop.pdf", "application/pdf", "pdf"),
        ("sop.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"),
        ("notes.md", "text/markdown", "md"),
        ("notes.txt", "text/plain", "txt"),
        ("call.vtt", "text/vtt", "transcript_vtt"),
        ("call.srt", "application/x-subrip", "transcript_srt"),
        ("leads.csv", "text/csv", "csv"),
        ("leads.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"),
        ("inbox.mbox", "application/mbox", "mbox"),
        ("crm.json", "application/json", "json"),
    ],
)
def test_registry_routes_to_correct_parser(file_name, mime_type, expected_type):
    pf = parse(file_id="f1", file_name=file_name, path=FIX / file_name, mime_type=mime_type)
    assert pf.type == expected_type
    assert len(pf.segments) > 0


def test_registry_raises_on_unknown_mime():
    with pytest.raises(ValueError, match="No parser registered"):
        parse(file_id="f1", file_name="x.bin", path=FIX / "sop.pdf", mime_type="application/octet-stream")
```

- [ ] **Step 2: Run test**

Run: `pytest tests/test_parsers_registry.py -v`
Expected: all 10 routing tests PASS + unknown-mime test PASS.

- [ ] **Step 3: Run full test suite**

Run: `pytest -v`
Expected: every test from Tasks 2-18 still PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_parsers_registry.py
git commit -m "test: end-to-end parser registry routing for all 10 file types"
```

---

## Task 20: Files Service (`services/files.py`)

**Files:**
- Create: `backend/app/services/__init__.py` (empty)
- Create: `backend/app/services/files.py`
- Create: `backend/tests/test_files_service.py`

- [ ] **Step 1: Create `backend/app/services/__init__.py`** (empty file)

- [ ] **Step 2: Write the failing test** in `backend/tests/test_files_service.py`

```python
from pathlib import Path
from app.database import Base, engine, SessionLocal
from app.services.files import upload_file
from app.models import FileRecord


def setup_module():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_upload_file_persists_record_and_parses(tmp_path, monkeypatch):
    monkeypatch.setattr("app.blob_store.BLOB_DIR", tmp_path)
    fixture = Path(__file__).parent / "fixtures" / "notes.md"
    content = fixture.read_bytes()

    with SessionLocal() as s:
        ref = upload_file(s, file_name="notes.md", mime_type="text/markdown", content=content)
        s.commit()

    assert ref.parser_status == "ok"
    with SessionLocal() as s:
        rec = s.get(FileRecord, ref.file_id)
        assert rec is not None
        assert rec.parser_status == "ok"
        assert rec.file_name == "notes.md"


def test_upload_file_marks_error_for_unknown_mime(tmp_path, monkeypatch):
    monkeypatch.setattr("app.blob_store.BLOB_DIR", tmp_path)
    with SessionLocal() as s:
        ref = upload_file(s, file_name="thing.bin", mime_type="application/octet-stream", content=b"\x00\x01")
        s.commit()
    assert ref.parser_status == "error"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_files_service.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 4: Implement `backend/app/services/files.py`**

```python
import uuid
from pathlib import Path
from sqlalchemy.orm import Session

from app.blob_store import save_blob
from app.models import FileRecord
from app.parsers import parse as parse_file
from app.schemas import FileRef


def upload_file(db: Session, *, file_name: str, mime_type: str, content: bytes) -> FileRef:
    file_id = f"f_{uuid.uuid4().hex[:12]}"
    blob_path = save_blob(file_id, file_name, content)

    parser_status: str
    try:
        parse_file(file_id=file_id, file_name=file_name, path=Path(blob_path), mime_type=mime_type)
        parser_status = "ok"
    except Exception:
        parser_status = "error"

    record = FileRecord(
        id=file_id,
        run_id=None,
        file_name=file_name,
        mime_type=mime_type,
        blob_path=blob_path,
        parser_status=parser_status,
    )
    db.add(record)
    db.flush()

    return FileRef(
        file_id=file_id,
        file_name=file_name,
        mime_type=mime_type,
        blob_path=blob_path,
        parser_status=parser_status,
    )


def get_parsed(db: Session, file_id: str):
    rec = db.get(FileRecord, file_id)
    if rec is None:
        raise ValueError(f"File {file_id} not found")
    return parse_file(
        file_id=rec.id,
        file_name=rec.file_name,
        path=Path(rec.blob_path),
        mime_type=rec.mime_type,
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_files_service.py -v`
Expected: PASS (both tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/__init__.py backend/app/services/files.py backend/tests/test_files_service.py
git commit -m "feat: upload_file service orchestrates blob store + parser + persistence"
```

---

## Task 21: POST /api/files Endpoint

**Files:**
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_files_api.py`

- [ ] **Step 1: Write the failing test** in `backend/tests/test_files_api.py`

```python
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine


def setup_module():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_upload_pdf_returns_file_id_and_ok_status(tmp_path, monkeypatch):
    monkeypatch.setattr("app.blob_store.BLOB_DIR", tmp_path)
    client = TestClient(app)
    fixture = Path(__file__).parent / "fixtures" / "sop.pdf"
    with fixture.open("rb") as f:
        r = client.post(
            "/api/files",
            files={"file": ("sop.pdf", f, "application/pdf")},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["file_id"].startswith("f_")
    assert body["parser_status"] == "ok"


def test_upload_unknown_mime_marks_error(tmp_path, monkeypatch):
    monkeypatch.setattr("app.blob_store.BLOB_DIR", tmp_path)
    client = TestClient(app)
    r = client.post(
        "/api/files",
        files={"file": ("thing.bin", b"\x00", "application/octet-stream")},
    )
    assert r.status_code == 200
    assert r.json()["parser_status"] == "error"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_files_api.py -v`
Expected: FAIL — `404` because route doesn't exist yet.

- [ ] **Step 3: Implement endpoint** — replace `backend/app/main.py` with:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Depends
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app import models  # noqa: F401  (register tables)
from app.services.files import upload_file
from app.schemas import FileRef


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="Ops Diagnostic Agent", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/files", response_model=FileRef)
def post_file(file: UploadFile = File(...), db: Session = Depends(get_db)) -> FileRef:
    content = file.file.read()
    ref = upload_file(db, file_name=file.filename or "unknown", mime_type=file.content_type or "application/octet-stream", content=content)
    db.commit()
    return ref
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_files_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/test_files_api.py
git commit -m "feat: POST /api/files multipart upload endpoint"
```

---

## Task 22: POST /api/files/{file_id}/excerpt Endpoint

**Files:**
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_excerpt_api.py`

Note: the spec/requirements originally sketched this as `GET /api/files/{file_id}/source/{locator}`, but locators are structured objects that don't fit cleanly in a URL path. We use POST with a JSON body for clarity. Both the request and response are simple.

- [ ] **Step 1: Write the failing test** in `backend/tests/test_excerpt_api.py`

```python
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine


def setup_module():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_excerpt_returns_text_for_uploaded_file(tmp_path, monkeypatch):
    monkeypatch.setattr("app.blob_store.BLOB_DIR", tmp_path)
    client = TestClient(app)

    fixture = Path(__file__).parent / "fixtures" / "notes.md"
    with fixture.open("rb") as f:
        upload = client.post(
            "/api/files",
            files={"file": ("notes.md", f, "text/markdown")},
        )
    file_id = upload.json()["file_id"]

    r = client.post(
        f"/api/files/{file_id}/excerpt",
        json={"locator": {"type": "text", "line_start": 1, "line_end": 1}},
    )
    assert r.status_code == 200
    assert "Producer Notes" in r.json()["text"]


def test_excerpt_returns_404_for_unknown_file(tmp_path, monkeypatch):
    monkeypatch.setattr("app.blob_store.BLOB_DIR", tmp_path)
    client = TestClient(app)
    r = client.post(
        "/api/files/f_nope/excerpt",
        json={"locator": {"type": "text", "line_start": 1, "line_end": 1}},
    )
    assert r.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_excerpt_api.py -v`
Expected: FAIL — 404 from the second test happens too early (the route isn't even defined yet, so the first call also fails).

- [ ] **Step 3: Extend `backend/app/main.py`**

Add these imports and routes (keep everything from Task 21):

```python
from fastapi import HTTPException
from pydantic import BaseModel

from app.services.files import get_parsed
from app.parsers import pdf as _p_pdf, docx as _p_docx, md as _p_md, txt as _p_txt
from app.parsers import vtt as _p_vtt, srt as _p_srt, csv as _p_csv, xlsx as _p_xlsx
from app.parsers import mbox as _p_mbox
from app.parsers import json as _p_json


_EXCERPT_MODULES = {
    "pdf": _p_pdf,
    "docx": _p_docx,
    "md": _p_md,
    "txt": _p_txt,
    "transcript_vtt": _p_vtt,
    "transcript_srt": _p_srt,
    "csv": _p_csv,
    "xlsx": _p_xlsx,
    "mbox": _p_mbox,
    "json": _p_json,
}


class ExcerptRequest(BaseModel):
    locator: dict


class ExcerptResponse(BaseModel):
    text: str


@app.post("/api/files/{file_id}/excerpt", response_model=ExcerptResponse)
def post_excerpt(file_id: str, body: ExcerptRequest, db: Session = Depends(get_db)) -> ExcerptResponse:
    try:
        parsed = get_parsed(db, file_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"file {file_id} not found")

    module = _EXCERPT_MODULES.get(parsed.type)
    if module is None:
        raise HTTPException(status_code=400, detail=f"no excerpt module for type {parsed.type}")
    try:
        text = module.excerpt(parsed, body.locator)
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ExcerptResponse(text=text)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_excerpt_api.py -v`
Expected: PASS (both tests)

- [ ] **Step 5: Run full suite**

Run: `pytest -v`
Expected: every test still PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py backend/tests/test_excerpt_api.py
git commit -m "feat: POST /api/files/{file_id}/excerpt returns text at locator"
```

---

## Task 23: LLM Provider Base + Metadata

**Files:**
- Create: `backend/app/llm/__init__.py`
- Create: `backend/app/llm/base.py`
- Create: `backend/tests/test_llm_base.py`

- [ ] **Step 1: Write the failing test** in `backend/tests/test_llm_base.py`

```python
from app.llm.base import GenerateMetadata


def test_generate_metadata_fields():
    m = GenerateMetadata(
        provider="ollama",
        model="llama3.1:8b",
        prompt_name="echo",
        token_estimate=10,
        parsed_json=True,
        retry_count=0,
        latency_ms=120,
    )
    assert m.provider == "ollama"
    assert m.parsed_json is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm_base.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `backend/app/llm/base.py`**

```python
from typing import Protocol, Type
from pydantic import BaseModel


class GenerateMetadata(BaseModel):
    provider: str
    model: str
    prompt_name: str
    token_estimate: int
    parsed_json: bool
    retry_count: int
    latency_ms: int


class LLMProvider(Protocol):
    name: str

    def generate_json(
        self,
        *,
        prompt_name: str,
        prompt: str,
        schema: Type[BaseModel],
    ) -> tuple[dict, GenerateMetadata]: ...
```

- [ ] **Step 4: Create `backend/app/llm/__init__.py`**

```python
from functools import lru_cache

from app.config import get_settings
from app.llm.base import GenerateMetadata, LLMProvider


@lru_cache(maxsize=1)
def get_provider() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "ollama":
        from app.llm.ollama import OllamaProvider
        return OllamaProvider(base_url=settings.ollama_base_url, model=settings.ollama_model)
    if settings.llm_provider == "openai":
        from app.llm.openai import OpenAIProvider
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY required when LLM_PROVIDER=openai")
        return OpenAIProvider(api_key=settings.openai_api_key, model=settings.openai_model)
    if settings.llm_provider == "groq":
        from app.llm.groq import GroqProvider
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY required when LLM_PROVIDER=groq")
        return GroqProvider(
            api_key=settings.groq_api_key, base_url=settings.groq_base_url, model=settings.groq_model,
        )
    if settings.llm_provider == "openai_compatible":
        from app.llm.openai_compat import OpenAICompatProvider
        if not (settings.openai_compatible_api_key and settings.openai_compatible_base_url and settings.openai_compatible_model):
            raise RuntimeError("OPENAI_COMPATIBLE_* env vars required when LLM_PROVIDER=openai_compatible")
        return OpenAICompatProvider(
            api_key=settings.openai_compatible_api_key,
            base_url=settings.openai_compatible_base_url,
            model=settings.openai_compatible_model,
        )
    raise RuntimeError(f"unknown LLM_PROVIDER={settings.llm_provider}")


__all__ = ["GenerateMetadata", "LLMProvider", "get_provider"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_llm_base.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/llm/__init__.py backend/app/llm/base.py backend/tests/test_llm_base.py
git commit -m "feat: LLM provider protocol and metadata schema"
```

---

## Task 24: Ollama Provider (Real-Call Test)

**Files:**
- Create: `backend/app/llm/ollama.py`
- Create: `backend/tests/test_llm_ollama.py`

This task tests against a real Ollama instance. The test is skipped if Ollama is not reachable, but the engineer should run it with Ollama up to verify the provider works.

- [ ] **Step 1: Prereq — ensure Ollama is installed and a small model is pulled**

Run on the host:

```bash
ollama pull llama3.1:8b
ollama serve  # in another terminal if not already running
```

- [ ] **Step 2: Write the failing test** in `backend/tests/test_llm_ollama.py`

```python
import os
import httpx
import pytest
from pydantic import BaseModel

from app.llm.ollama import OllamaProvider


def _ollama_up(base_url: str) -> bool:
    try:
        r = httpx.get(f"{base_url}/api/tags", timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")


class EchoSchema(BaseModel):
    sentiment: str
    confidence: float


@pytest.mark.skipif(not _ollama_up(BASE_URL), reason="Ollama not reachable")
def test_ollama_generate_json_returns_schema_valid_object():
    provider = OllamaProvider(base_url=BASE_URL, model=MODEL)
    prompt = (
        "Classify the sentiment of: 'This product is great!'.\n"
        "Respond with JSON of the form {\"sentiment\": \"positive|negative|neutral\", \"confidence\": float between 0 and 1}."
    )
    result, meta = provider.generate_json(
        prompt_name="sentiment_classifier",
        prompt=prompt,
        schema=EchoSchema,
    )
    EchoSchema.model_validate(result)  # raises on schema failure
    assert meta.provider == "ollama"
    assert meta.model == MODEL
    assert meta.prompt_name == "sentiment_classifier"
    assert meta.parsed_json is True
    assert meta.latency_ms > 0
```

- [ ] **Step 3: Run test — expect it to fail because the module doesn't exist yet**

Run: `pytest tests/test_llm_ollama.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 4: Implement `backend/app/llm/ollama.py`**

```python
import json
import time
from typing import Type
import httpx
from pydantic import BaseModel, ValidationError

from app.llm.base import GenerateMetadata


class OllamaProvider:
    name = "ollama"

    def __init__(self, *, base_url: str, model: str, timeout_s: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s

    def generate_json(
        self,
        *,
        prompt_name: str,
        prompt: str,
        schema: Type[BaseModel],
    ) -> tuple[dict, GenerateMetadata]:
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
        }
        retry_count = 0
        last_error: str | None = None
        start = time.perf_counter()

        for attempt in range(2):
            with httpx.Client(timeout=self.timeout_s) as client:
                r = client.post(f"{self.base_url}/api/chat", json=body)
                r.raise_for_status()
                payload = r.json()
                content = payload.get("message", {}).get("content", "")

            try:
                parsed = json.loads(content)
                schema.model_validate(parsed)
                latency_ms = int((time.perf_counter() - start) * 1000)
                return parsed, GenerateMetadata(
                    provider=self.name,
                    model=self.model,
                    prompt_name=prompt_name,
                    token_estimate=len(prompt) // 4 + len(content) // 4,
                    parsed_json=True,
                    retry_count=retry_count,
                    latency_ms=latency_ms,
                )
            except (json.JSONDecodeError, ValidationError) as e:
                last_error = str(e)
                retry_count += 1
                body["messages"].append({
                    "role": "user",
                    "content": f"Your previous response failed to parse as the required JSON: {e}. Reply with ONLY valid JSON matching the schema.",
                })

        latency_ms = int((time.perf_counter() - start) * 1000)
        return {}, GenerateMetadata(
            provider=self.name,
            model=self.model,
            prompt_name=prompt_name,
            token_estimate=len(prompt) // 4,
            parsed_json=False,
            retry_count=retry_count,
            latency_ms=latency_ms,
        )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_llm_ollama.py -v`
Expected: PASS (or SKIP if Ollama is not running — but it should be running for this task to count as done).

- [ ] **Step 6: Commit**

```bash
git add backend/app/llm/ollama.py backend/tests/test_llm_ollama.py
git commit -m "feat: Ollama LLM provider with strict JSON parsing and one retry"
```

---

## Task 25: OpenAI Provider

**Files:**
- Create: `backend/app/llm/openai.py`
- Create: `backend/tests/test_llm_openai_smoke.py`

The unit-level shape mirrors Ollama. A live API smoke test is included but skipped without `OPENAI_API_KEY`.

- [ ] **Step 1: Write the failing test** in `backend/tests/test_llm_openai_smoke.py`

```python
import os
import pytest
from pydantic import BaseModel
from app.llm.openai import OpenAIProvider


API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


class EchoSchema(BaseModel):
    sentiment: str
    confidence: float


@pytest.mark.skipif(not API_KEY, reason="OPENAI_API_KEY not set")
def test_openai_generate_json_returns_schema_valid_object():
    provider = OpenAIProvider(api_key=API_KEY, model=MODEL)
    prompt = (
        "Classify the sentiment of: 'This product is great!'.\n"
        "Respond with JSON: {\"sentiment\": \"positive|negative|neutral\", \"confidence\": float in [0,1]}."
    )
    result, meta = provider.generate_json(prompt_name="sentiment", prompt=prompt, schema=EchoSchema)
    EchoSchema.model_validate(result)
    assert meta.provider == "openai"
    assert meta.parsed_json is True
```

- [ ] **Step 2: Run test — expect SKIP (no API key) or FAIL (module missing)**

Run: `pytest tests/test_llm_openai_smoke.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `backend/app/llm/openai.py`**

```python
import json
import time
from typing import Type
from openai import OpenAI
from pydantic import BaseModel, ValidationError

from app.llm.base import GenerateMetadata


class OpenAIProvider:
    name = "openai"

    def __init__(self, *, api_key: str, model: str, base_url: str | None = None) -> None:
        self.client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
        self.model = model

    def generate_json(
        self,
        *,
        prompt_name: str,
        prompt: str,
        schema: Type[BaseModel],
    ) -> tuple[dict, GenerateMetadata]:
        retry_count = 0
        messages = [{"role": "user", "content": prompt}]
        start = time.perf_counter()

        for attempt in range(2):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0,
            )
            content = response.choices[0].message.content or ""
            usage = response.usage
            tokens = (usage.prompt_tokens + usage.completion_tokens) if usage else 0

            try:
                parsed = json.loads(content)
                schema.model_validate(parsed)
                latency_ms = int((time.perf_counter() - start) * 1000)
                return parsed, GenerateMetadata(
                    provider=self.name,
                    model=self.model,
                    prompt_name=prompt_name,
                    token_estimate=tokens,
                    parsed_json=True,
                    retry_count=retry_count,
                    latency_ms=latency_ms,
                )
            except (json.JSONDecodeError, ValidationError) as e:
                retry_count += 1
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": f"Previous reply did not match the schema: {e}. Return ONLY valid JSON."})

        latency_ms = int((time.perf_counter() - start) * 1000)
        return {}, GenerateMetadata(
            provider=self.name,
            model=self.model,
            prompt_name=prompt_name,
            token_estimate=0,
            parsed_json=False,
            retry_count=retry_count,
            latency_ms=latency_ms,
        )
```

- [ ] **Step 4: Run test**

Run: `pytest tests/test_llm_openai_smoke.py -v`
Expected: PASS if `OPENAI_API_KEY` is set, otherwise SKIP. Either result is acceptable for task completion — the engineer should set the key and verify PASS at least once.

- [ ] **Step 5: Commit**

```bash
git add backend/app/llm/openai.py backend/tests/test_llm_openai_smoke.py
git commit -m "feat: OpenAI LLM provider with strict JSON mode and one retry"
```

---

## Task 26: Groq Provider

**Files:**
- Create: `backend/app/llm/groq.py`
- Create: `backend/tests/test_llm_groq_smoke.py`

Groq exposes an OpenAI-compatible API, so the implementation reuses `OpenAIProvider` with a custom base URL.

- [ ] **Step 1: Write the failing test** in `backend/tests/test_llm_groq_smoke.py`

```python
import os
import pytest
from pydantic import BaseModel
from app.llm.groq import GroqProvider


API_KEY = os.getenv("GROQ_API_KEY")
BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


class EchoSchema(BaseModel):
    sentiment: str
    confidence: float


@pytest.mark.skipif(not API_KEY, reason="GROQ_API_KEY not set")
def test_groq_generate_json_returns_schema_valid_object():
    provider = GroqProvider(api_key=API_KEY, base_url=BASE_URL, model=MODEL)
    prompt = (
        "Classify the sentiment of: 'This product is great!'.\n"
        "Reply with JSON: {\"sentiment\": \"positive|negative|neutral\", \"confidence\": float in [0,1]}."
    )
    result, meta = provider.generate_json(prompt_name="sentiment", prompt=prompt, schema=EchoSchema)
    EchoSchema.model_validate(result)
    assert meta.provider == "groq"
    assert meta.parsed_json is True
```

- [ ] **Step 2: Run test**

Run: `pytest tests/test_llm_groq_smoke.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `backend/app/llm/groq.py`**

```python
from typing import Type
from pydantic import BaseModel

from app.llm.base import GenerateMetadata
from app.llm.openai import OpenAIProvider


class GroqProvider:
    name = "groq"

    def __init__(self, *, api_key: str, base_url: str, model: str) -> None:
        self._inner = OpenAIProvider(api_key=api_key, model=model, base_url=base_url)
        self.model = model

    def generate_json(
        self,
        *,
        prompt_name: str,
        prompt: str,
        schema: Type[BaseModel],
    ) -> tuple[dict, GenerateMetadata]:
        result, meta = self._inner.generate_json(prompt_name=prompt_name, prompt=prompt, schema=schema)
        meta.provider = self.name
        return result, meta
```

- [ ] **Step 4: Run test**

Run: `pytest tests/test_llm_groq_smoke.py -v`
Expected: PASS if `GROQ_API_KEY` is set, otherwise SKIP.

- [ ] **Step 5: Commit**

```bash
git add backend/app/llm/groq.py backend/tests/test_llm_groq_smoke.py
git commit -m "feat: Groq LLM provider via OpenAI-compatible API"
```

---

## Task 27: OpenAI-Compatible Provider

**Files:**
- Create: `backend/app/llm/openai_compat.py`
- Create: `backend/tests/test_llm_openai_compat.py`

- [ ] **Step 1: Write the failing test** in `backend/tests/test_llm_openai_compat.py`

```python
import os
import pytest
from pydantic import BaseModel
from app.llm.openai_compat import OpenAICompatProvider


API_KEY = os.getenv("OPENAI_COMPATIBLE_API_KEY")
BASE_URL = os.getenv("OPENAI_COMPATIBLE_BASE_URL")
MODEL = os.getenv("OPENAI_COMPATIBLE_MODEL")


class EchoSchema(BaseModel):
    sentiment: str
    confidence: float


@pytest.mark.skipif(
    not (API_KEY and BASE_URL and MODEL),
    reason="OPENAI_COMPATIBLE_* env vars not all set",
)
def test_openai_compat_generate_json_returns_schema_valid_object():
    provider = OpenAICompatProvider(api_key=API_KEY, base_url=BASE_URL, model=MODEL)
    prompt = "Reply with JSON: {\"sentiment\": \"positive\", \"confidence\": 0.9}."
    result, meta = provider.generate_json(prompt_name="echo", prompt=prompt, schema=EchoSchema)
    EchoSchema.model_validate(result)
    assert meta.provider == "openai_compatible"
```

- [ ] **Step 2: Run test**

Run: `pytest tests/test_llm_openai_compat.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `backend/app/llm/openai_compat.py`**

```python
from typing import Type
from pydantic import BaseModel

from app.llm.base import GenerateMetadata
from app.llm.openai import OpenAIProvider


class OpenAICompatProvider:
    name = "openai_compatible"

    def __init__(self, *, api_key: str, base_url: str, model: str) -> None:
        self._inner = OpenAIProvider(api_key=api_key, model=model, base_url=base_url)
        self.model = model

    def generate_json(
        self,
        *,
        prompt_name: str,
        prompt: str,
        schema: Type[BaseModel],
    ) -> tuple[dict, GenerateMetadata]:
        result, meta = self._inner.generate_json(prompt_name=prompt_name, prompt=prompt, schema=schema)
        meta.provider = self.name
        return result, meta
```

- [ ] **Step 4: Run test**

Run: `pytest tests/test_llm_openai_compat.py -v`
Expected: PASS if env vars set, otherwise SKIP.

- [ ] **Step 5: Commit**

```bash
git add backend/app/llm/openai_compat.py backend/tests/test_llm_openai_compat.py
git commit -m "feat: OpenAI-compatible LLM provider wrapper"
```

---

## Task 28: Provider Factory Integration Test

**Files:**
- Create: `backend/tests/test_llm_factory.py`

- [ ] **Step 1: Write the test** in `backend/tests/test_llm_factory.py`

```python
import pytest
from app.llm import get_provider


def test_factory_returns_ollama_by_default(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("BLOB_STORE_DIR", "./test_blobs")
    get_provider.cache_clear()
    p = get_provider()
    assert p.name == "ollama"


def test_factory_rejects_openai_without_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("BLOB_STORE_DIR", "./test_blobs")
    get_provider.cache_clear()
    # Also need to clear settings cache by forcing reimport — easier: just expect RuntimeError
    import app.config
    app.config.get_settings.cache_clear() if hasattr(app.config.get_settings, "cache_clear") else None
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        get_provider()
```

Note: `app.config.get_settings` isn't `lru_cache`'d in this plan, so the second test's `cache_clear` line is a no-op safety belt. If the engineer adds caching later, the line will keep the test correct.

- [ ] **Step 2: Run test**

Run: `pytest tests/test_llm_factory.py -v`
Expected: PASS (both tests)

- [ ] **Step 3: Run full test suite**

Run: `pytest -v`
Expected: every test PASS (or SKIP for tests gated on env vars). No FAIL.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_llm_factory.py
git commit -m "test: LLM provider factory selection and key validation"
```

---

## Task 29: README and Final Sanity

**Files:**
- Create: `backend/README.md`

- [ ] **Step 1: Write `backend/README.md`**

```markdown
# Backend — Plan 1

FastAPI backend foundation: file ingestion, parsing for 10 file types with locator anchors, and an LLM provider layer over Ollama / OpenAI / Groq / OpenAI-compatible. No mock provider.

## Quick start

```bash
make install
cp backend/.env.example backend/.env  # edit values
make fixtures                          # generates parser test fixtures
make test
make dev                               # starts uvicorn on :8000
```

## Endpoints

- `GET /health`
- `POST /api/files` — multipart upload, returns `{file_id, parser_status, ...}`.
- `POST /api/files/{file_id}/excerpt` — body `{locator: {...}}`, returns `{text: "..."}`.

## Providers

Set `LLM_PROVIDER` in `.env` to one of: `ollama` (default, requires Ollama running locally), `openai` (requires `OPENAI_API_KEY`), `groq` (requires `GROQ_API_KEY`), `openai_compatible` (requires all three `OPENAI_COMPATIBLE_*` vars).

## Tests against real models

Smoke tests for OpenAI / Groq / OpenAI-compatible providers skip when their keys aren't set. The Ollama provider test runs as long as `ollama serve` is reachable at `OLLAMA_BASE_URL`. CI defaults to Ollama with `temperature=0`.

## What this plan does NOT include

Agents, LangGraph, Redis checkpointer, Langfuse, persistence for file_summaries / blueprints, Next.js frontend, `make demo`. See Plan 2 and Plan 3.
```

- [ ] **Step 2: Final full test run**

Run: `pytest -v`
Expected: every test PASS or SKIP. No FAIL, no ERROR.

- [ ] **Step 3: Manual smoke check**

```bash
make dev
# in another shell:
curl http://localhost:8000/health
curl -F "file=@backend/tests/fixtures/sop.pdf" http://localhost:8000/api/files
# note the file_id from the response, then:
curl -X POST http://localhost:8000/api/files/<file_id>/excerpt \
     -H "Content-Type: application/json" \
     -d '{"locator": {"type": "pdf", "page": 1, "span_start": 0, "span_end": 50}}'
```

Expected: each call returns expected JSON, no 500s.

- [ ] **Step 4: Commit**

```bash
git add backend/README.md
git commit -m "docs: backend README for Plan 1"
```

---

## Plan Self-Review Notes

This section is for the planner, not the executor — kept here for traceability.

- **Spec coverage check (against `2026-05-23-real-files-diagnostic-redesign-design.md`):**
  - §5 parser table → Tasks 9-18 cover all 10 file types with the exact locator schemas listed.
  - §9 LLM provider design → Tasks 23-28 implement the four providers, the `generate_json` interface, and `GenerateMetadata`. **No mock provider** — confirmed.
  - §10 observability → out of scope for Plan 1 (deferred to Plan 2 as documented in the file structure section).
  - §11 persistence → `runs` and `files` tables only; `file_summaries`, `intake_bundles`, `blueprints` deferred to Plan 2.
  - §6-§8 typed schemas → `Source`, locator union, `ParsedFile`, `ExtractionError`, `FileRef` in Task 6. `FileSummary`/`IntakeBundle`/`Blueprint` deferred to Plan 2 (correct — they're agent-output types).
  - §13 testing → real Ollama tests in Task 24, skip-gated smoke tests for hosted providers, structural-invariant assertions throughout.

- **Endpoint divergence from spec:** The spec sketched `GET /api/files/{file_id}/source/{locator}` but locators are structured objects. This plan uses `POST /api/files/{file_id}/excerpt` with a JSON body. Documented inline in Task 22 and the README. If the spec needs to be updated to match, that's a doc-level change not a code-level one.

- **Placeholder scan:** No "TBD" / "TODO" / "implement later" left in tasks. Every step shows real code or an exact command.

- **Type consistency:** `ParsedFile.type` literal values match `FileType` in `schemas.py` and every parser's `parse()` output. `GenerateMetadata.provider` string matches each provider's `name` attribute (`"ollama"`, `"openai"`, `"groq"`, `"openai_compatible"`).

---

**Plan complete.** Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks, fast iteration.
**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
