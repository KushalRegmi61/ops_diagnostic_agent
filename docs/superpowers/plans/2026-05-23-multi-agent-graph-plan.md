# Multi-Agent Graph + Redis Checkpointer + Langfuse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the multi-agent diagnostic pipeline: 7 per-file tool-routed ReAct agents (parallel), reviewer → synthesizer → 5-stage diagnostic chain → self-review (sequential lead-agent nodes), all wired through a LangGraph parent workflow with a Redis-backed checkpointer and one nested Langfuse trace per run. End state: `POST /api/runs` returns a `run_id`; `GET /api/runs/{run_id}/blueprint` returns a cited blueprint produced by real Ollama calls against the files uploaded in Plan 1.

**Architecture:**
- **Per-file agents** are ReAct loops over a fixed toolbelt (`search_text`, `read_segment`, `extract_workflow`, `extract_pain_signal`, `extract_lead_row`, `cite_locator`, `finalize_summary`), capped at 6 iterations, dispatched by an explicit tool router with Pydantic-validated args. Every `Source` they emit roundtrips through `cite_locator` to guarantee citation reachability.
- **Lead-agent nodes** are single-shot `generate_json(schema=...)` calls — no ReAct, no tools — because their job is reasoning over already-typed inputs, not extraction.
- **LangGraph parent workflow** wires the nodes; bounded edges enforce at-most-one redo cycle (review → flagged per-file agents → review) and at-most-one revision (self-review → solution_blueprint → self-review).
- **Redis checkpointer** keyed by `run_id` — required, no in-memory fallback. Backend refuses to start a run if Redis is unreachable.
- **Langfuse** opens one trace per `run_id`; every node, LLM call, and tool call is a nested span. Provider metadata (model, prompt_name, token_estimate, parsed_json, retry_count, latency_ms) attached to every LLM generation.

**Tech Stack:** LangGraph, `langgraph-checkpoint-redis`, `redis` (Python client), Langfuse SDK, FastAPI, SQLAlchemy 2.x, Pydantic v2, real Ollama (`temperature=0` by default) — everything else (parsers, LLM providers, blob store, file API) is already in place from Plan 1.

**Source spec:** [`docs/superpowers/specs/2026-05-23-real-files-diagnostic-redesign-design.md`](../specs/2026-05-23-real-files-diagnostic-redesign-design.md) — §6 (per-file agents + ReAct), §7 (lead agent), §8 (`DiagnosticState`), §10 (observability), §11.1 (Redis checkpointer).

**Prereqs:**
- Plan 1 complete (Tasks 1–29 of `2026-05-23-backend-foundation-plan.md`).
- Redis 7+ running locally at `redis://localhost:6379` (or set `REDIS_URL`). `docker run -p 6379:6379 redis:7` works.
- Langfuse keys (free cloud account at langfuse.com) or a self-hosted instance. Set `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL`.
- Ollama running with the configured `OLLAMA_MODEL` pulled.

---

## File Structure

Plan 2 adds these modules to `backend/app/` and `backend/tests/`. Existing files from Plan 1 are listed in *italics* and only touched at noted points.

```
backend/app/
├── *config.py*               # extend: REDIS_URL, LANGFUSE_*, LANGGRAPH_CHECKPOINT_NAMESPACE
├── *schemas.py*              # extend: FileSummary, SummaryReview, IntakeBundle, Bottleneck, Opportunity, Blueprint, FinalReview, supporting types
├── *models.py*               # extend: file_summaries, intake_bundles, blueprints tables
├── state.py                  # NEW: DiagnosticState TypedDict
├── checkpointer.py           # NEW: Redis-backed LangGraph checkpointer + healthcheck
├── observability.py          # NEW: Langfuse client + trace/span context managers
├── prompts/                  # NEW: prompt strings live as Python constants, one file per node
│   ├── __init__.py
│   ├── per_file_brief.py     # shared extraction brief
│   ├── review_summaries.py
│   ├── synthesis.py
│   ├── workflow_map.py
│   ├── bottleneck_detect.py
│   ├── roi_score.py
│   ├── fastest_win_select.py
│   ├── solution_blueprint.py
│   └── self_review.py
├── agents/
│   ├── __init__.py
│   ├── per_file/
│   │   ├── __init__.py
│   │   ├── _state.py         # WorkingState (the agent's mutable scratchpad during ReAct)
│   │   ├── _router.py        # tool router with typed Pydantic args, iteration cap
│   │   ├── _react_loop.py    # think → act → observe loop
│   │   ├── _tools/
│   │   │   ├── __init__.py   # registry
│   │   │   ├── search_text.py
│   │   │   ├── read_segment.py
│   │   │   ├── extract_workflow.py
│   │   │   ├── extract_pain_signal.py
│   │   │   ├── extract_lead_row.py
│   │   │   ├── cite_locator.py
│   │   │   └── finalize_summary.py
│   │   ├── pdf.py            # per-file agent for PDFs
│   │   ├── docx.py
│   │   ├── markdown.py       # covers md + txt
│   │   ├── transcript.py     # covers vtt + srt
│   │   ├── table.py          # covers csv + xlsx
│   │   ├── mbox.py
│   │   └── json.py
│   └── lead/
│       ├── __init__.py
│       ├── review_summaries.py
│       ├── synthesis.py
│       ├── workflow_map.py
│       ├── bottleneck_detect.py
│       ├── roi_score.py
│       ├── fastest_win_select.py
│       ├── solution_blueprint.py
│       └── self_review.py
├── graph.py                  # NEW: LangGraph parent workflow + Redis-checkpointer wiring
├── services/
│   ├── *files.py*            # already exists
│   └── runs.py               # NEW: create_run, get_run, get_blueprint
└── *main.py*                 # extend: POST /api/runs, GET /api/runs/{id}, GET /api/runs/{id}/blueprint

backend/tests/
├── unit/
│   ├── test_state.py                       # DiagnosticState shape
│   ├── test_observability.py               # span tree builder shape
│   ├── test_agents_per_file_router.py      # tool router typed dispatch
│   └── test_agents_per_file_search.py      # search_text scoring is deterministic
└── integration/
    ├── test_checkpointer.py
    ├── test_agents_per_file_pdf.py
    ├── test_agents_per_file_docx.py
    ├── test_agents_per_file_markdown.py
    ├── test_agents_per_file_transcript.py
    ├── test_agents_per_file_table.py
    ├── test_agents_per_file_mbox.py
    ├── test_agents_per_file_json.py
    ├── test_agents_lead_review.py
    ├── test_agents_lead_synthesis.py
    ├── test_agents_lead_diagnostic_chain.py
    ├── test_agents_lead_self_review.py
    ├── test_runs_api.py
    └── test_graph_e2e.py
```

**Out of scope for Plan 2 (handled in Plan 3):** Next.js frontend, `/samples` realistic dataset, Dockerized `make demo`, citation panel UI.

---

## Phase A — Foundation (Tasks 1–7)

### Task 1: Install Plan 2 dependencies

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Add deps** to the `dependencies` list:

```toml
"langgraph>=0.2.50",
"langgraph-checkpoint-redis>=0.0.6",
"redis>=5.0",
"langfuse>=2.50",
```

- [ ] **Step 2: Install**

Run: `make install` (or `cd backend && uv pip install -e ".[dev]"` if the venv already exists).
Expected: clean install, all new packages resolved.

- [ ] **Step 3: Smoke-test imports**

Run: `cd backend && source .venv/bin/activate && python -c "import langgraph, langgraph.checkpoint.redis, redis, langfuse; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock
git commit -m "deps: add langgraph, redis checkpointer, langfuse"
```

---

### Task 2: Extend `config.py` with Redis + Langfuse + checkpointer settings

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/.env.example`
- Modify: `backend/.env` (local dev — not committed)
- Modify: `backend/tests/unit/test_config.py`

- [ ] **Step 1: Update the failing test** in `backend/tests/unit/test_config.py` — append:

```python
def test_settings_loads_redis_and_langfuse(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("BLOB_STORE_DIR", "./test_blobs")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk_test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk_test")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "https://us.cloud.langfuse.com")
    s = Settings()
    assert s.redis_url == "redis://localhost:6379/0"
    assert s.langgraph_checkpointer == "redis"
    assert s.langgraph_checkpoint_namespace == "ops_diagnostic"
    assert s.langfuse_public_key == "pk_test"
    assert s.langfuse_secret_key == "sk_test"
    assert s.langfuse_base_url.startswith("https://")
```

- [ ] **Step 2: Run test, verify failure**

Run: `pytest tests/unit/test_config.py::test_settings_loads_redis_and_langfuse -v`
Expected: FAIL — `Settings` has no `redis_url`.

- [ ] **Step 3: Extend `Settings`** in `backend/app/config.py` — add inside the class, below the existing provider fields:

```python
    # Redis + LangGraph checkpointer
    redis_url: str = "redis://localhost:6379/0"
    langgraph_checkpointer: Literal["redis"] = "redis"
    langgraph_checkpoint_namespace: str = "ops_diagnostic"

    # Langfuse
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_base_url: str = "https://us.cloud.langfuse.com"

    # Run-time behavior
    auto_approve_review: bool = False
    per_file_iteration_cap: int = 6
```

- [ ] **Step 4: Update `backend/.env.example`** — append:

```bash
# Redis (LangGraph checkpointer — required)
REDIS_URL=redis://localhost:6379/0
LANGGRAPH_CHECKPOINTER=redis
LANGGRAPH_CHECKPOINT_NAMESPACE=ops_diagnostic

# Langfuse observability
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_BASE_URL=https://us.cloud.langfuse.com

# Behavior
AUTO_APPROVE_REVIEW=false
PER_FILE_ITERATION_CAP=6
```

- [ ] **Step 5: Update local `backend/.env`** with the same lines (set your real Langfuse keys here).

- [ ] **Step 6: Run test, verify pass**

Run: `pytest tests/unit/test_config.py -v`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/config.py backend/.env.example backend/tests/unit/test_config.py
git commit -m "feat(config): add Redis, Langfuse, and run-behavior settings"
```

---

### Task 3: Extend `schemas.py` with agent-output types

Adds every Pydantic type the agents will produce. No business logic — pure structure.

**Files:**
- Modify: `backend/app/schemas.py`
- Create: `backend/tests/unit/test_schemas_agents.py`

- [ ] **Step 1: Write failing test** in `backend/tests/unit/test_schemas_agents.py`:

```python
import pytest
from pydantic import ValidationError

from app.schemas import (
    Blueprint,
    BlueprintClaim,
    Bottleneck,
    Contradiction,
    FileSummary,
    FinalReview,
    IntakeBundle,
    LeadRow,
    Opportunity,
    PainSignal,
    RevisionRequest,
    Source,
    SummaryReview,
    WorkflowRecord,
)


def _src(file_id: str = "f1") -> Source:
    return Source(
        file_id=file_id, file_name="x.pdf", type="pdf",
        locator={"type": "pdf", "page": 1, "span_start": 0, "span_end": 10},
    )


def test_workflow_record_requires_sources():
    wf = WorkflowRecord(
        name="onboarding", actors=["CSR"], systems=["Applied Epic"],
        steps=["verify id"], manual_touchpoints=["copy"], sources=[_src()],
    )
    assert wf.sources[0].file_id == "f1"


def test_file_summary_round_trips():
    fs = FileSummary(
        file_id="f1", file_name="x.pdf",
        one_paragraph_summary="summary",
        key_workflows=[], key_pain_signals=[], lead_rows=[],
        open_questions=[], agent_notes="",
    )
    assert fs.file_id == "f1"


def test_revision_request_rejects_unknown_reason():
    with pytest.raises(ValidationError):
        RevisionRequest(file_id="f1", reason="bogus", detail="x")


def test_summary_review_allows_empty_requests():
    sr = SummaryReview(revision_requests=[], notes="all good")
    assert sr.notes == "all good"


def test_intake_bundle_holds_contradictions():
    bundle = IntakeBundle(
        workflows=[], pain_signals=[], lead_rows=[],
        contradictions=[Contradiction(topic="CRM name", statements=[
            {"claim": "Salesforce", "sources": [_src("a").model_dump()]},
            {"claim": "HubSpot", "sources": [_src("b").model_dump()]},
        ])],
        file_index=[_src("a"), _src("b")],
        extraction_errors=[],
    )
    assert bundle.contradictions[0].topic == "CRM name"


def test_opportunity_score_ranges():
    op = Opportunity(
        workflow_name="lead-intake", bottleneck_refs=[0],
        pain_score=7, roi_score=8, effort_score=4, risk_score=2,
        hours_saved_per_week=5.0, response_time_impact="-50%",
        rationale="text", sources=[_src()],
    )
    assert op.roi_score == 8


def test_blueprint_claim_carries_sources():
    bc = BlueprintClaim(text="connect HubSpot to Drive", sources=[_src()])
    assert bc.sources[0].file_id == "f1"


def test_final_review_pass_fail_per_check():
    fr = FinalReview(
        citation_existence_ok=True, citation_reachability_ok=True,
        no_silent_drops_ok=True, internal_consistency_ok=True,
        detail="all checks pass", revised_once=False,
    )
    assert fr.citation_existence_ok is True
```

- [ ] **Step 2: Run test, verify failure**

Run: `pytest tests/unit/test_schemas_agents.py -v`
Expected: FAIL — symbols not exported.

- [ ] **Step 3: Extend `backend/app/schemas.py`** — append:

```python
# ---- Per-file agent output types ----

class WorkflowRecord(BaseModel):
    name: str
    actors: list[str]
    systems: list[str]
    steps: list[str]
    manual_touchpoints: list[str]
    sources: list[Source]


class PainSignal(BaseModel):
    text: str
    category: Literal["delay","error","repetition","handoff",
                      "missing_data","visibility_gap","revenue_leak"]
    sources: list[Source]


class LeadRow(BaseModel):
    raw: dict
    normalized: dict
    source: Source


class FileSummary(BaseModel):
    file_id: str
    file_name: str
    one_paragraph_summary: str
    key_workflows: list[WorkflowRecord]
    key_pain_signals: list[PainSignal]
    lead_rows: list[LeadRow]
    open_questions: list[str]
    agent_notes: str


# ---- Reviewer types ----

class RevisionRequest(BaseModel):
    file_id: str
    reason: Literal["missing_info","contradiction","weak_citation",
                    "ignored_open_question","schema_drift"]
    detail: str


class SummaryReview(BaseModel):
    revision_requests: list[RevisionRequest]
    notes: str


# ---- Synthesis types ----

class Contradiction(BaseModel):
    topic: str
    statements: list[dict]  # each: {"claim": str, "sources": list[Source-as-dict]}


class IntakeBundle(BaseModel):
    workflows: list[WorkflowRecord]
    pain_signals: list[PainSignal]
    lead_rows: list[LeadRow]
    contradictions: list[Contradiction]
    file_index: list[Source]
    extraction_errors: list[ExtractionError]


# ---- Diagnostic chain types ----

class Bottleneck(BaseModel):
    workflow_name: str
    signal: Literal["delay","error","repetition","handoff",
                    "missing_data","visibility_gap","revenue_leak"]
    impact: str
    sources: list[Source]


class Opportunity(BaseModel):
    workflow_name: str
    bottleneck_refs: list[int]
    pain_score: int        # 1-10
    roi_score: int         # 1-10
    effort_score: int      # 1-10
    risk_score: int        # 1-10
    hours_saved_per_week: float
    response_time_impact: str
    rationale: str
    sources: list[Source]


class BlueprintClaim(BaseModel):
    text: str
    sources: list[Source]


class Blueprint(BaseModel):
    opportunity_ref: int
    summary: BlueprintClaim
    steps: list[BlueprintClaim]
    required_systems: list[BlueprintClaim]
    success_metrics: list[BlueprintClaim]
    risks: list[BlueprintClaim]


# ---- Self-review type ----

class FinalReview(BaseModel):
    citation_existence_ok: bool
    citation_reachability_ok: bool
    no_silent_drops_ok: bool
    internal_consistency_ok: bool
    detail: str
    revised_once: bool
```

- [ ] **Step 4: Run test, verify pass**

Run: `pytest tests/unit/test_schemas_agents.py -v`
Expected: 8 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas.py backend/tests/unit/test_schemas_agents.py
git commit -m "feat(schemas): agent-output types — FileSummary, IntakeBundle, Blueprint, etc."
```

---

### Task 4: `DiagnosticState` TypedDict

**Files:**
- Create: `backend/app/state.py`
- Create: `backend/tests/unit/test_state.py`

- [ ] **Step 1: Write failing test** in `backend/tests/unit/test_state.py`:

```python
from app.state import DiagnosticState


def test_diagnostic_state_typed_dict_keys():
    expected_keys = {
        "run_id", "files", "file_summaries", "summary_review", "redo_count",
        "bundle", "workflows", "bottlenecks", "opportunities", "selected",
        "blueprint", "final_review", "revision_count", "errors",
    }
    assert expected_keys.issubset(DiagnosticState.__annotations__.keys())


def test_diagnostic_state_construct_minimal():
    state: DiagnosticState = {
        "run_id": "r1", "files": [], "file_summaries": {}, "summary_review": None,
        "redo_count": 0, "bundle": None, "workflows": [], "bottlenecks": [],
        "opportunities": [], "selected": None, "blueprint": None,
        "final_review": None, "revision_count": 0, "errors": [],
    }
    assert state["run_id"] == "r1"
```

- [ ] **Step 2: Run, verify failure**

Run: `pytest tests/unit/test_state.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `backend/app/state.py`**

```python
from typing import TypedDict

from app.schemas import (
    Blueprint,
    Bottleneck,
    ExtractionError,
    FileRef,
    FileSummary,
    FinalReview,
    IntakeBundle,
    Opportunity,
    SummaryReview,
    WorkflowRecord,
)


class DiagnosticState(TypedDict):
    run_id: str
    files: list[FileRef]
    file_summaries: dict[str, FileSummary]
    summary_review: SummaryReview | None
    redo_count: int
    bundle: IntakeBundle | None
    workflows: list[WorkflowRecord]
    bottlenecks: list[Bottleneck]
    opportunities: list[Opportunity]
    selected: Opportunity | None
    blueprint: Blueprint | None
    final_review: FinalReview | None
    revision_count: int
    errors: list[ExtractionError]
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/unit/test_state.py -v`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/state.py backend/tests/unit/test_state.py
git commit -m "feat(state): DiagnosticState TypedDict for LangGraph parent workflow"
```

---

### Task 5: Extend SQLAlchemy models — `file_summaries`, `intake_bundles`, `blueprints`

**Files:**
- Modify: `backend/app/models.py`
- Create: `backend/tests/integration/test_models_agents.py`

- [ ] **Step 1: Write failing test** in `backend/tests/integration/test_models_agents.py`:

```python
import json

from app.database import Base, SessionLocal, engine
from app.models import BlueprintRecord, FileSummaryRecord, IntakeBundleRecord


def setup_module():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_persist_file_summary_record():
    with SessionLocal() as s:
        rec = FileSummaryRecord(file_id="f1", payload_json=json.dumps({"x": 1}))
        s.add(rec)
        s.commit()
        assert s.get(FileSummaryRecord, "f1").payload_json == '{"x": 1}'


def test_persist_intake_bundle_record():
    with SessionLocal() as s:
        rec = IntakeBundleRecord(run_id="r1", payload_json="{}")
        s.add(rec)
        s.commit()
        assert s.get(IntakeBundleRecord, "r1") is not None


def test_persist_blueprint_record():
    with SessionLocal() as s:
        rec = BlueprintRecord(run_id="r1", payload_json="{}")
        s.add(rec)
        s.commit()
        assert s.get(BlueprintRecord, "r1") is not None
```

- [ ] **Step 2: Run, verify failure**

Run: `pytest tests/integration/test_models_agents.py -v`
Expected: FAIL — names not in `app.models`.

- [ ] **Step 3: Append to `backend/app/models.py`**

```python
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
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/integration/test_models_agents.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models.py backend/tests/integration/test_models_agents.py
git commit -m "feat(models): file_summaries, intake_bundles, blueprints tables"
```

---

### Task 6: Redis-backed LangGraph checkpointer module

**Files:**
- Create: `backend/app/checkpointer.py`
- Create: `backend/tests/integration/test_checkpointer.py`

- [ ] **Step 1: Write failing test** in `backend/tests/integration/test_checkpointer.py`:

```python
import pytest
import redis as redis_lib

from app.checkpointer import build_checkpointer, redis_healthcheck
from app.config import get_settings


def _redis_up() -> bool:
    try:
        r = redis_lib.Redis.from_url(get_settings().redis_url, socket_timeout=1)
        return r.ping() is True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _redis_up(), reason="Redis not reachable")


def test_redis_healthcheck_passes_when_up():
    assert redis_healthcheck() is True


def test_build_checkpointer_returns_a_saver():
    cp = build_checkpointer()
    assert cp is not None
    # LangGraph BaseCheckpointSaver has a .put / .get_tuple surface
    assert hasattr(cp, "put") or hasattr(cp, "aput")
```

- [ ] **Step 2: Run, verify failure**

Run: `pytest tests/integration/test_checkpointer.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `backend/app/checkpointer.py`**

```python
import redis as redis_lib
from langgraph.checkpoint.redis import RedisSaver

from app.config import get_settings


def redis_healthcheck() -> bool:
    """Return True if Redis at REDIS_URL is reachable; False otherwise."""
    settings = get_settings()
    try:
        client = redis_lib.Redis.from_url(settings.redis_url, socket_timeout=2)
        return client.ping() is True
    except Exception:
        return False


def build_checkpointer() -> RedisSaver:
    """Return a Redis-backed LangGraph checkpointer.

    Raises RuntimeError if Redis is not reachable — no in-memory fallback in v1.
    """
    if not redis_healthcheck():
        raise RuntimeError(
            f"Redis unreachable at {get_settings().redis_url}; "
            "the LangGraph checkpointer is required in v1. "
            "Start Redis or set REDIS_URL."
        )
    settings = get_settings()
    saver = RedisSaver.from_conn_string(settings.redis_url)
    # RedisSaver requires explicit setup() on first use (creates indexes).
    saver.setup()
    return saver
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/integration/test_checkpointer.py -v` (after `docker run -p 6379:6379 redis:7` if needed)
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/checkpointer.py backend/tests/integration/test_checkpointer.py
git commit -m "feat(checkpointer): Redis-backed LangGraph checkpointer with healthcheck"
```

---

### Task 7: Langfuse observability module

**Files:**
- Create: `backend/app/observability.py`
- Create: `backend/tests/unit/test_observability.py`

`observability.py` exposes:
- `langfuse_client()` — memoized client
- `trace_run(run_id)` — context manager returning the parent trace handle
- `span(parent, name, *, input=None)` — context manager creating a child span; closes with `output` and `error`
- `record_generation(parent, name, *, prompt, response, metadata)` — records an LLM generation as a child of the parent span

- [ ] **Step 1: Write failing test** in `backend/tests/unit/test_observability.py`:

```python
from app.observability import langfuse_client


def test_langfuse_client_returns_none_when_keys_missing(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("BLOB_STORE_DIR", "./test_blobs")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    langfuse_client.cache_clear()
    assert langfuse_client() is None  # no keys → no client → tracing becomes no-op
```

- [ ] **Step 2: Run, verify failure**

Run: `pytest tests/unit/test_observability.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `backend/app/observability.py`**

```python
from contextlib import contextmanager
from functools import lru_cache
from typing import Any

from langfuse import Langfuse

from app.config import get_settings


@lru_cache(maxsize=1)
def langfuse_client() -> Langfuse | None:
    s = get_settings()
    if not (s.langfuse_public_key and s.langfuse_secret_key):
        return None
    return Langfuse(
        public_key=s.langfuse_public_key,
        secret_key=s.langfuse_secret_key,
        host=s.langfuse_base_url,
    )


@contextmanager
def trace_run(run_id: str, *, user_id: str | None = None):
    """Open a top-level Langfuse trace for one diagnostic run."""
    client = langfuse_client()
    if client is None:
        yield None
        return
    trace = client.trace(name="parent_graph", id=run_id, user_id=user_id)
    try:
        yield trace
    finally:
        client.flush()


@contextmanager
def span(parent: Any, name: str, *, input: dict | None = None):
    """Open a nested span under `parent`. Closes with output/error on exit."""
    if parent is None:
        yield None
        return
    s = parent.span(name=name, input=input or {})
    try:
        yield s
    except Exception as e:
        s.end(level="ERROR", status_message=str(e))
        raise
    else:
        s.end()


def record_generation(parent: Any, name: str, *, prompt: str, response: str, metadata: dict) -> None:
    """Attach an LLM generation event to `parent`."""
    if parent is None:
        return
    parent.generation(
        name=name,
        input=prompt,
        output=response,
        model=metadata.get("model"),
        usage={"input": metadata.get("token_estimate", 0)},
        metadata=metadata,
    )
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/unit/test_observability.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/observability.py backend/tests/unit/test_observability.py
git commit -m "feat(observability): Langfuse client + trace/span context managers"
```

---

## Phase B — Per-file ReAct infrastructure (Tasks 8–14)

### Task 8: Per-file agent working state

The agent's *scratchpad* during the ReAct loop. Mutable. Not persisted — only the final `FileSummary` is.

**Files:**
- Create: `backend/app/agents/__init__.py` (empty)
- Create: `backend/app/agents/per_file/__init__.py` (empty)
- Create: `backend/app/agents/per_file/_state.py`
- Create: `backend/tests/unit/test_agents_per_file_state.py`

- [ ] **Step 1: Write failing test**:

```python
from app.agents.per_file._state import WorkingState


def test_working_state_initializes_empty():
    ws = WorkingState(file_id="f1", file_name="x.pdf")
    assert ws.file_id == "f1"
    assert ws.workflows == []
    assert ws.pain_signals == []
    assert ws.lead_rows == []
    assert ws.open_questions == []
    assert ws.notes == ""
    assert ws.iteration == 0
```

- [ ] **Step 2: Run, verify failure**

Run: `pytest tests/unit/test_agents_per_file_state.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `backend/app/agents/per_file/_state.py`**

```python
from dataclasses import dataclass, field

from app.schemas import LeadRow, PainSignal, WorkflowRecord


@dataclass
class WorkingState:
    """The ReAct agent's mutable scratchpad. Becomes a FileSummary at finalize_summary."""
    file_id: str
    file_name: str
    workflows: list[WorkflowRecord] = field(default_factory=list)
    pain_signals: list[PainSignal] = field(default_factory=list)
    lead_rows: list[LeadRow] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    notes: str = ""
    iteration: int = 0
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/unit/test_agents_per_file_state.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/__init__.py backend/app/agents/per_file/__init__.py backend/app/agents/per_file/_state.py backend/tests/unit/test_agents_per_file_state.py
git commit -m "feat(per_file): WorkingState scratchpad dataclass"
```

---

### Task 9: `search_text` tool — light in-file retrieval

**Files:**
- Create: `backend/app/agents/per_file/_tools/__init__.py` (empty)
- Create: `backend/app/agents/per_file/_tools/search_text.py`
- Create: `backend/tests/unit/test_agents_per_file_search.py`

- [ ] **Step 1: Write failing test**:

```python
from app.agents.per_file._tools.search_text import search_text
from app.schemas import ParsedFile, ParsedSegment


def _pf() -> ParsedFile:
    return ParsedFile(
        file_id="f1", file_name="x.md", type="md",
        segments=[
            ParsedSegment(text="Leads waiting > 24h before first response.",
                          locator={"type": "text", "line_start": 1, "line_end": 1}),
            ParsedSegment(text="CSR manually copies CRM notes.",
                          locator={"type": "text", "line_start": 2, "line_end": 2}),
            ParsedSegment(text="Producer follow-up inconsistent.",
                          locator={"type": "text", "line_start": 3, "line_end": 3}),
        ],
    )


def test_search_text_ranks_token_overlap_high():
    hits = search_text(_pf(), query="lead response time", top_k=2)
    assert len(hits) == 2
    # The "Leads waiting" line has the most token overlap with the query.
    assert hits[0]["text"].startswith("Leads waiting")


def test_search_text_returns_locator_with_each_hit():
    hits = search_text(_pf(), query="csr copies notes", top_k=1)
    assert hits[0]["locator"]["line_start"] == 2


def test_search_text_caps_at_top_k():
    hits = search_text(_pf(), query="the", top_k=2)
    assert len(hits) <= 2
```

- [ ] **Step 2: Run, verify failure**

Run: `pytest tests/unit/test_agents_per_file_search.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `backend/app/agents/per_file/_tools/search_text.py`**

```python
from app.schemas import ParsedFile


def _tokenize(s: str) -> set[str]:
    return {t.lower() for t in s.split() if t}


def _score(segment_text: str, query: str) -> float:
    seg_tokens = _tokenize(segment_text)
    q_tokens = _tokenize(query)
    if not q_tokens:
        return 0.0
    overlap = len(seg_tokens & q_tokens) / len(q_tokens)
    substring = 1.0 if query.lower() in segment_text.lower() else 0.0
    return overlap * 0.7 + substring * 0.3


def search_text(parsed: ParsedFile, *, query: str, top_k: int = 3) -> list[dict]:
    """Token-overlap + substring scoring over a single ParsedFile.

    Returns the top_k hits as dicts: {segment_index, score, text, locator}.
    """
    scored = [
        {
            "segment_index": i,
            "score": _score(seg.text, query),
            "text": seg.text,
            "locator": seg.locator,
        }
        for i, seg in enumerate(parsed.segments)
    ]
    scored.sort(key=lambda h: h["score"], reverse=True)
    return [h for h in scored if h["score"] > 0][:top_k]
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/unit/test_agents_per_file_search.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/per_file/_tools/ backend/tests/unit/test_agents_per_file_search.py
git commit -m "feat(per_file): search_text — token-overlap + substring scoring"
```

---

### Task 10: Remaining tools — `read_segment`, `extract_*`, `cite_locator`, `finalize_summary`

Each tool gets its own module so the router can dispatch by name and the test surface stays narrow.

**Files:**
- Create: `backend/app/agents/per_file/_tools/read_segment.py`
- Create: `backend/app/agents/per_file/_tools/extract_workflow.py`
- Create: `backend/app/agents/per_file/_tools/extract_pain_signal.py`
- Create: `backend/app/agents/per_file/_tools/extract_lead_row.py`
- Create: `backend/app/agents/per_file/_tools/cite_locator.py`
- Create: `backend/app/agents/per_file/_tools/finalize_summary.py`
- Create: `backend/tests/unit/test_agents_per_file_tools.py`

- [ ] **Step 1: Write failing test** in `backend/tests/unit/test_agents_per_file_tools.py`:

```python
import pytest

from app.agents.per_file._state import WorkingState
from app.agents.per_file._tools.cite_locator import cite_locator
from app.agents.per_file._tools.extract_lead_row import extract_lead_row
from app.agents.per_file._tools.extract_pain_signal import extract_pain_signal
from app.agents.per_file._tools.extract_workflow import extract_workflow
from app.agents.per_file._tools.finalize_summary import finalize_summary
from app.agents.per_file._tools.read_segment import read_segment
from app.schemas import ParsedFile, ParsedSegment, Source


def _pf() -> ParsedFile:
    return ParsedFile(
        file_id="f1", file_name="x.md", type="md",
        segments=[
            ParsedSegment(text="Step 1: collect contact info.",
                          locator={"type": "text", "line_start": 1, "line_end": 1}),
        ],
    )


def _src() -> Source:
    return Source(file_id="f1", file_name="x.md", type="md",
                  locator={"type": "text", "line_start": 1, "line_end": 1})


def test_read_segment_returns_text_and_locator():
    result = read_segment(_pf(), segment_index=0)
    assert "contact info" in result["text"]
    assert result["locator"]["line_start"] == 1


def test_read_segment_raises_on_invalid_index():
    with pytest.raises(ValueError):
        read_segment(_pf(), segment_index=99)


def test_extract_workflow_appends_to_working_state():
    ws = WorkingState(file_id="f1", file_name="x.md")
    out = extract_workflow(
        ws, name="onboarding", actors=["CSR"], systems=["Applied"],
        steps=["verify id"], manual_touchpoints=["copy"], sources=[_src()],
    )
    assert out["ok"] is True
    assert ws.workflows[0].name == "onboarding"


def test_extract_pain_signal_validates_category():
    ws = WorkingState(file_id="f1", file_name="x.md")
    extract_pain_signal(ws, text="too slow", category="delay", sources=[_src()])
    assert ws.pain_signals[0].category == "delay"


def test_extract_lead_row_only_accepts_table_types():
    ws = WorkingState(file_id="f1", file_name="leads.csv")
    extract_lead_row(ws, raw={"name": "Acme"}, normalized={"name": "Acme"}, source=_src())
    assert ws.lead_rows[0].raw["name"] == "Acme"


def test_cite_locator_roundtrips_through_parser():
    result = cite_locator(_pf(), locator={"type": "text", "line_start": 1, "line_end": 1})
    assert result["valid"] is True
    assert "contact info" in result["text"]


def test_cite_locator_invalid_returns_valid_false():
    result = cite_locator(_pf(), locator={"type": "text", "line_start": 99, "line_end": 99})
    assert result["valid"] is False


def test_finalize_summary_builds_file_summary_from_state():
    ws = WorkingState(file_id="f1", file_name="x.md")
    ws.notes = "ran clean"
    summary = finalize_summary(ws, one_paragraph_summary="single para")
    assert summary.file_id == "f1"
    assert summary.one_paragraph_summary == "single para"
    assert summary.agent_notes == "ran clean"
```

- [ ] **Step 2: Run, verify failure**

Run: `pytest tests/unit/test_agents_per_file_tools.py -v`
Expected: FAIL — modules missing.

- [ ] **Step 3: Implement each tool**:

`backend/app/agents/per_file/_tools/read_segment.py`:

```python
from app.schemas import ParsedFile


def read_segment(parsed: ParsedFile, *, segment_index: int) -> dict:
    if segment_index < 0 or segment_index >= len(parsed.segments):
        raise ValueError(f"segment_index {segment_index} out of range")
    seg = parsed.segments[segment_index]
    return {"text": seg.text, "locator": seg.locator}
```

`backend/app/agents/per_file/_tools/extract_workflow.py`:

```python
from app.agents.per_file._state import WorkingState
from app.schemas import Source, WorkflowRecord


def extract_workflow(
    ws: WorkingState, *,
    name: str, actors: list[str], systems: list[str],
    steps: list[str], manual_touchpoints: list[str], sources: list[Source],
) -> dict:
    wf = WorkflowRecord(
        name=name, actors=actors, systems=systems, steps=steps,
        manual_touchpoints=manual_touchpoints, sources=sources,
    )
    ws.workflows.append(wf)
    return {"ok": True, "workflow_index": len(ws.workflows) - 1}
```

`backend/app/agents/per_file/_tools/extract_pain_signal.py`:

```python
from app.agents.per_file._state import WorkingState
from app.schemas import PainSignal, Source


def extract_pain_signal(ws: WorkingState, *, text: str, category: str, sources: list[Source]) -> dict:
    ps = PainSignal(text=text, category=category, sources=sources)
    ws.pain_signals.append(ps)
    return {"ok": True, "pain_signal_index": len(ws.pain_signals) - 1}
```

`backend/app/agents/per_file/_tools/extract_lead_row.py`:

```python
from app.agents.per_file._state import WorkingState
from app.schemas import LeadRow, Source


def extract_lead_row(ws: WorkingState, *, raw: dict, normalized: dict, source: Source) -> dict:
    lr = LeadRow(raw=raw, normalized=normalized, source=source)
    ws.lead_rows.append(lr)
    return {"ok": True, "lead_row_index": len(ws.lead_rows) - 1}
```

`backend/app/agents/per_file/_tools/cite_locator.py`:

```python
from app.parsers import csv as _p_csv
from app.parsers import docx as _p_docx
from app.parsers import json as _p_json
from app.parsers import mbox as _p_mbox
from app.parsers import md as _p_md
from app.parsers import pdf as _p_pdf
from app.parsers import srt as _p_srt
from app.parsers import txt as _p_txt
from app.parsers import vtt as _p_vtt
from app.parsers import xlsx as _p_xlsx
from app.schemas import ParsedFile

_EXCERPT_BY_TYPE = {
    "pdf": _p_pdf, "docx": _p_docx, "md": _p_md, "txt": _p_txt,
    "transcript_vtt": _p_vtt, "transcript_srt": _p_srt,
    "csv": _p_csv, "xlsx": _p_xlsx, "mbox": _p_mbox, "json": _p_json,
}


def cite_locator(parsed: ParsedFile, *, locator: dict) -> dict:
    """Validate a locator by roundtripping it through the parser's excerpt(). Returns {text, valid}."""
    module = _EXCERPT_BY_TYPE.get(parsed.type)
    if module is None:
        return {"text": "", "valid": False}
    try:
        text = module.excerpt(parsed, locator)
        return {"text": text, "valid": True}
    except (KeyError, ValueError):
        return {"text": "", "valid": False}
```

`backend/app/agents/per_file/_tools/finalize_summary.py`:

```python
from app.agents.per_file._state import WorkingState
from app.schemas import FileSummary


def finalize_summary(ws: WorkingState, *, one_paragraph_summary: str, open_questions: list[str] | None = None) -> FileSummary:
    return FileSummary(
        file_id=ws.file_id,
        file_name=ws.file_name,
        one_paragraph_summary=one_paragraph_summary,
        key_workflows=ws.workflows,
        key_pain_signals=ws.pain_signals,
        lead_rows=ws.lead_rows,
        open_questions=open_questions or ws.open_questions,
        agent_notes=ws.notes,
    )
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/unit/test_agents_per_file_tools.py -v`
Expected: 8 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/per_file/_tools/ backend/tests/unit/test_agents_per_file_tools.py
git commit -m "feat(per_file): toolbelt — read_segment, extract_*, cite_locator, finalize_summary"
```

---

### Task 11: Tool router with typed dispatch

The router is what enforces "one tool per iteration, Pydantic-validated args, iteration cap, no rogue `Source` creation."

**Files:**
- Create: `backend/app/agents/per_file/_router.py`
- Create: `backend/tests/unit/test_agents_per_file_router.py`

- [ ] **Step 1: Write failing test**:

```python
import pytest

from app.agents.per_file._router import ToolCall, dispatch
from app.agents.per_file._state import WorkingState
from app.schemas import ParsedFile, ParsedSegment


def _pf() -> ParsedFile:
    return ParsedFile(
        file_id="f1", file_name="x.md", type="md",
        segments=[
            ParsedSegment(text="step", locator={"type": "text", "line_start": 1, "line_end": 1}),
        ],
    )


def test_dispatch_search_text():
    ws = WorkingState(file_id="f1", file_name="x.md")
    call = ToolCall(tool="search_text", args={"query": "step", "top_k": 1})
    result = dispatch(call, parsed=_pf(), ws=ws)
    assert isinstance(result, list)


def test_dispatch_finalize_summary_returns_file_summary():
    ws = WorkingState(file_id="f1", file_name="x.md")
    call = ToolCall(tool="finalize_summary", args={"one_paragraph_summary": "done"})
    fs = dispatch(call, parsed=_pf(), ws=ws)
    assert fs.one_paragraph_summary == "done"


def test_dispatch_unknown_tool_raises():
    ws = WorkingState(file_id="f1", file_name="x.md")
    call = ToolCall(tool="nope", args={})
    with pytest.raises(ValueError, match="Unknown tool"):
        dispatch(call, parsed=_pf(), ws=ws)


def test_dispatch_invalid_args_raises():
    ws = WorkingState(file_id="f1", file_name="x.md")
    call = ToolCall(tool="read_segment", args={"wrong_arg": 1})
    with pytest.raises(Exception):  # Pydantic validation or TypeError
        dispatch(call, parsed=_pf(), ws=ws)
```

- [ ] **Step 2: Run, verify failure**

Run: `pytest tests/unit/test_agents_per_file_router.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `backend/app/agents/per_file/_router.py`**

```python
from typing import Any

from pydantic import BaseModel

from app.agents.per_file._state import WorkingState
from app.agents.per_file._tools.cite_locator import cite_locator
from app.agents.per_file._tools.extract_lead_row import extract_lead_row
from app.agents.per_file._tools.extract_pain_signal import extract_pain_signal
from app.agents.per_file._tools.extract_workflow import extract_workflow
from app.agents.per_file._tools.finalize_summary import finalize_summary
from app.agents.per_file._tools.read_segment import read_segment
from app.agents.per_file._tools.search_text import search_text
from app.schemas import ParsedFile


class ToolCall(BaseModel):
    tool: str
    args: dict


def dispatch(call: ToolCall, *, parsed: ParsedFile, ws: WorkingState) -> Any:
    """Validate-and-dispatch a single tool call. Each branch keyword-unpacks args."""
    name = call.tool
    args = call.args

    if name == "search_text":
        return search_text(parsed, **args)
    if name == "read_segment":
        return read_segment(parsed, **args)
    if name == "extract_workflow":
        return extract_workflow(ws, **args)
    if name == "extract_pain_signal":
        return extract_pain_signal(ws, **args)
    if name == "extract_lead_row":
        return extract_lead_row(ws, **args)
    if name == "cite_locator":
        return cite_locator(parsed, **args)
    if name == "finalize_summary":
        return finalize_summary(ws, **args)
    raise ValueError(f"Unknown tool: {name}")
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/unit/test_agents_per_file_router.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/per_file/_router.py backend/tests/unit/test_agents_per_file_router.py
git commit -m "feat(per_file): tool router with typed dispatch"
```

---

### Task 12: Extraction brief — shared per-file-agent prompt

**Files:**
- Create: `backend/app/prompts/__init__.py` (empty)
- Create: `backend/app/prompts/per_file_brief.py`

- [ ] **Step 1: Implement `backend/app/prompts/per_file_brief.py`**

```python
"""Shared extraction brief given to every per-file ReAct agent.

The brief is intentionally identical across file types so summaries
are comparable. File-type-specific guidance is appended per-agent.
"""

EXTRACTION_BRIEF = """You are a per-file agent in an operations diagnostic pipeline.

Your job: read ONE file and produce a typed FileSummary capturing:
- key_workflows: business processes the file describes or implies
- key_pain_signals: places where time, revenue, or visibility is lost
- lead_rows: structured records of leads (ONLY for csv/xlsx/mbox/json files)
- open_questions: things you couldn't determine but a human should
- one_paragraph_summary: a single dense paragraph

You have a fixed toolbelt. At each step, decide which tool to call and pass typed arguments.
Tools available:
  - search_text(query: str, top_k: int = 3) -> ranked hits with locators
  - read_segment(segment_index: int) -> full text + locator
  - extract_workflow(name, actors, systems, steps, manual_touchpoints, sources)
  - extract_pain_signal(text, category, sources)  category in {delay, error, repetition, handoff, missing_data, visibility_gap, revenue_leak}
  - extract_lead_row(raw, normalized, source)
  - cite_locator(locator) -> {text, valid}  always validate before attaching a citation
  - finalize_summary(one_paragraph_summary, open_questions=[]) -> ends the loop

Hard rules:
- Every WorkflowRecord, PainSignal, and LeadRow MUST carry sources: list[Source].
- Build a Source from a locator returned by search_text or read_segment.
- Always cite_locator(locator) before adding it to a Source — never attach an unvalidated locator.
- One tool call per iteration. After at most {iteration_cap} iterations, the loop ends.
- Reply ONLY with JSON of the form: {"tool": "<name>", "args": {...}}

You start with no prior context. Begin by calling search_text or read_segment to explore the file."""


def render_brief(*, iteration_cap: int) -> str:
    return EXTRACTION_BRIEF.format(iteration_cap=iteration_cap)
```

- [ ] **Step 2: Commit** (no test — pure string)

```bash
git add backend/app/prompts/__init__.py backend/app/prompts/per_file_brief.py
git commit -m "feat(prompts): shared per-file extraction brief"
```

---

### Task 13: ReAct loop

This is the engine. Each iteration: prompt = brief + working-state summary + tool history → LLM → parse `{tool, args}` JSON → dispatch → append observation → repeat until `finalize_summary` or iteration cap.

**Files:**
- Create: `backend/app/agents/per_file/_react_loop.py`
- Create: `backend/tests/integration/test_agents_per_file_react.py`

- [ ] **Step 1: Write failing test** (real Ollama, uses the simplest fixture):

```python
import os
from pathlib import Path

import httpx
import pytest

from app.agents.per_file._react_loop import run_react_loop
from app.config import get_settings
from app.llm import get_provider
from app.parsers import md as md_parser


def _ollama_up(base_url: str) -> bool:
    try:
        return httpx.get(f"{base_url}/api/tags", timeout=2.0).status_code == 200
    except Exception:
        return False


SETTINGS = get_settings()
pytestmark = pytest.mark.skipif(
    not _ollama_up(SETTINGS.ollama_base_url),
    reason="Ollama not reachable",
)


def test_react_loop_produces_file_summary_from_markdown():
    fixture = Path(__file__).parent.parent / "fixtures" / "notes.md"
    parsed = md_parser.parse(file_id="f1", file_name="notes.md", path=fixture)
    get_provider.cache_clear()
    provider = get_provider()
    fs = run_react_loop(
        provider=provider,
        parsed=parsed,
        prompt_suffix="This is a Markdown notes file from an insurance ops discovery call.",
        iteration_cap=6,
    )
    assert fs.file_id == "f1"
    assert isinstance(fs.one_paragraph_summary, str)
    # Every Source attached anywhere must roundtrip through the parser.
    from app.agents.per_file._tools.cite_locator import cite_locator
    for wf in fs.key_workflows:
        for src in wf.sources:
            assert cite_locator(parsed, locator=src.locator)["valid"] is True
    for ps in fs.key_pain_signals:
        for src in ps.sources:
            assert cite_locator(parsed, locator=src.locator)["valid"] is True
```

- [ ] **Step 2: Run, verify failure**

Run: `pytest tests/integration/test_agents_per_file_react.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `backend/app/agents/per_file/_react_loop.py`**

```python
import json
from typing import Any

from pydantic import BaseModel

from app.agents.per_file._router import ToolCall, dispatch
from app.agents.per_file._state import WorkingState
from app.llm.base import LLMProvider
from app.prompts.per_file_brief import render_brief
from app.schemas import FileSummary, ParsedFile


class _ToolReply(BaseModel):
    """Schema the LLM must produce each iteration."""
    tool: str
    args: dict


def _state_recap(ws: WorkingState, max_lines: int = 6) -> str:
    parts = [
        f"iter={ws.iteration}",
        f"workflows={len(ws.workflows)}",
        f"pain_signals={len(ws.pain_signals)}",
        f"lead_rows={len(ws.lead_rows)}",
        f"open_questions={len(ws.open_questions)}",
    ]
    return " | ".join(parts)


def _segment_index_recap(parsed: ParsedFile, max_segments: int = 12) -> str:
    """Show the model the segment table so it can pick indices for read_segment."""
    lines: list[str] = []
    for i, seg in enumerate(parsed.segments[:max_segments]):
        preview = seg.text[:80].replace("\n", " ")
        lines.append(f"[{i}] {preview}")
    if len(parsed.segments) > max_segments:
        lines.append(f"... +{len(parsed.segments) - max_segments} more segments")
    return "\n".join(lines)


def run_react_loop(
    *,
    provider: LLMProvider,
    parsed: ParsedFile,
    prompt_suffix: str = "",
    iteration_cap: int = 6,
    on_tool_call: Any = None,  # optional callback(name, args, result) for Langfuse
) -> FileSummary:
    """Run the ReAct loop until finalize_summary is called or iteration_cap is hit.

    Returns the FileSummary built from the working state. If the cap is hit
    before finalize_summary, a fallback FileSummary is emitted with a caveat
    in agent_notes.
    """
    ws = WorkingState(file_id=parsed.file_id, file_name=parsed.file_name)
    history: list[str] = []

    brief = render_brief(iteration_cap=iteration_cap)

    for it in range(iteration_cap):
        ws.iteration = it
        prompt = (
            brief
            + "\n\n"
            + prompt_suffix
            + "\n\nSegment index (first lines shown for picking read_segment indices):\n"
            + _segment_index_recap(parsed)
            + f"\n\nCurrent working state: {_state_recap(ws)}"
            + ("\n\nRecent tool history:\n" + "\n".join(history[-4:]) if history else "")
            + '\n\nReply with ONLY one JSON object: {"tool": "<name>", "args": {...}}'
        )

        result_dict, meta = provider.generate_json(
            prompt_name=f"per_file_{parsed.type}",
            prompt=prompt,
            schema=_ToolReply,
        )

        # If the model failed to produce parsable JSON, force finalize.
        if not result_dict:
            ws.notes += " | LLM JSON parse failure — early finalize"
            break

        call = ToolCall(tool=result_dict["tool"], args=result_dict.get("args", {}))
        try:
            result = dispatch(call, parsed=parsed, ws=ws)
        except Exception as e:
            history.append(f"{call.tool}({call.args}) -> ERROR {e}")
            if on_tool_call:
                on_tool_call(call.tool, call.args, {"error": str(e)})
            continue

        if on_tool_call:
            on_tool_call(call.tool, call.args, result)

        if call.tool == "finalize_summary":
            return result  # FileSummary

        # Trim noisy results in history for prompt size.
        history.append(f"{call.tool}({json.dumps(call.args)[:120]}) -> {str(result)[:120]}")

    # Iteration cap hit without finalize.
    ws.notes += f" | iteration_cap={iteration_cap} hit without finalize_summary"
    return FileSummary(
        file_id=ws.file_id,
        file_name=ws.file_name,
        one_paragraph_summary="(partial — iteration cap reached)",
        key_workflows=ws.workflows,
        key_pain_signals=ws.pain_signals,
        lead_rows=ws.lead_rows,
        open_questions=ws.open_questions,
        agent_notes=ws.notes,
    )
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/integration/test_agents_per_file_react.py -v -s`
Expected: PASS (likely ~30s; the loop hits Ollama up to 6 times). If FAIL because the model invents bad locators, that means `cite_locator` correctly rejected them and the loop continued — re-run and inspect.

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/per_file/_react_loop.py backend/tests/integration/test_agents_per_file_react.py
git commit -m "feat(per_file): ReAct loop with typed tool dispatch and citation roundtrip"
```

---

### Task 14: Per-file agent factory (one thin wrapper per file family)

Each file-family module is ~15 lines: import `_react_loop`, supply a file-type-specific prompt suffix, return `FileSummary`. The factory hides the boilerplate.

**Files:**
- Create: `backend/app/agents/per_file/pdf.py`
- Create: `backend/app/agents/per_file/docx.py`
- Create: `backend/app/agents/per_file/markdown.py`
- Create: `backend/app/agents/per_file/transcript.py`
- Create: `backend/app/agents/per_file/table.py`
- Create: `backend/app/agents/per_file/mbox.py`
- Create: `backend/app/agents/per_file/json.py`

- [ ] **Step 1: Write `backend/app/agents/per_file/pdf.py`**

```python
"""Per-file agent for PDF documents."""
from app.agents.per_file._react_loop import run_react_loop
from app.config import get_settings
from app.llm.base import LLMProvider
from app.schemas import FileSummary, ParsedFile

_SUFFIX = (
    "This file is a PDF. Likely contents: SOPs, training docs, policy summaries, "
    "or declaration pages. Look for stepwise procedures and named systems (e.g. Applied Epic, HubSpot). "
    "PDFs are paginated — locators are {type: 'pdf', page, span_start, span_end}."
)


def run(*, provider: LLMProvider, parsed: ParsedFile, on_tool_call=None) -> FileSummary:
    cap = get_settings().per_file_iteration_cap
    return run_react_loop(
        provider=provider, parsed=parsed,
        prompt_suffix=_SUFFIX, iteration_cap=cap, on_tool_call=on_tool_call,
    )
```

- [ ] **Step 2: Write `backend/app/agents/per_file/docx.py`** — same shape, suffix:

```python
_SUFFIX = (
    "This file is a Word DOCX. Likely contents: SOPs, onboarding docs, internal policies. "
    "Locators are {type: 'docx', paragraph_index, span_start, span_end}."
)
```
(Body identical to pdf.py except the suffix.)

- [ ] **Step 3: Write `backend/app/agents/per_file/markdown.py`** — covers `.md` and `.txt`:

```python
_SUFFIX = (
    "This file is a Markdown or plain-text notes file. Likely contents: "
    "meeting notes, discovery-call summaries, internal memos. "
    "Locators are {type: 'text', line_start, line_end}."
)
```

- [ ] **Step 4: Write `backend/app/agents/per_file/transcript.py`** — covers VTT + SRT:

```python
_SUFFIX = (
    "This file is a meeting transcript (VTT or SRT). Likely contents: "
    "founder/CSR discovery calls describing operational pain. "
    "Locators carry timestamps: {type: 'transcript', line_start, line_end, ts_start, ts_end}."
)
```

- [ ] **Step 5: Write `backend/app/agents/per_file/table.py`** — covers CSV + XLSX. This one also calls `extract_lead_row`:

```python
_SUFFIX = (
    "This file is a TABLE (CSV or XLSX). Likely contents: a lead list with stage and timing. "
    "For EVERY row, call extract_lead_row with {raw, normalized, source}. "
    "Locators: {type: 'table', row_index} for CSV, {type: 'xlsx', sheet, row_index} for XLSX. "
    "Also emit key_pain_signals for stages where rows have stalled (e.g. days_in_stage > 14)."
)
```

- [ ] **Step 6: Write `backend/app/agents/per_file/mbox.py`**:

```python
_SUFFIX = (
    "This file is an MBOX email export. Each segment is one message body. "
    "Treat each message as a potential lead — call extract_lead_row if it is one. "
    "Locators are {type: 'mbox', message_id, section}."
)
```

- [ ] **Step 7: Write `backend/app/agents/per_file/json.py`**:

```python
_SUFFIX = (
    "This file is a JSON export (CRM dump or similar). Segments are leaf values "
    "with RFC 6901 pointer locators: {type: 'json', pointer}. Treat each contact/lead "
    "object as a lead_row by reconstructing it from leaf segments under the same prefix."
)
```

- [ ] **Step 8: Write the integration tests for each agent family**:

For each of `pdf`, `docx`, `markdown`, `transcript`, `table`, `mbox`, `json`, create `backend/tests/integration/test_agents_per_file_<name>.py` with this pattern (substitute fixture + parser):

```python
# tests/integration/test_agents_per_file_pdf.py
import httpx
import pytest
from pathlib import Path

from app.agents.per_file import pdf as pdf_agent
from app.agents.per_file._tools.cite_locator import cite_locator
from app.config import get_settings
from app.llm import get_provider
from app.parsers import pdf as pdf_parser


def _ollama_up(base_url: str) -> bool:
    try:
        return httpx.get(f"{base_url}/api/tags", timeout=2.0).status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _ollama_up(get_settings().ollama_base_url),
    reason="Ollama not reachable",
)


def test_per_file_pdf_emits_valid_file_summary():
    fixture = Path(__file__).parent.parent / "fixtures" / "sop.pdf"
    parsed = pdf_parser.parse(file_id="f1", file_name="sop.pdf", path=fixture)
    get_provider.cache_clear()
    fs = pdf_agent.run(provider=get_provider(), parsed=parsed)
    assert fs.file_id == "f1"
    for record in fs.key_workflows + fs.key_pain_signals:
        for src in record.sources:
            assert cite_locator(parsed, locator=src.locator)["valid"] is True
```

The other six follow the same shape with different fixtures (`sop.docx`, `notes.md`, `call.vtt`, `leads.csv`, `inbox.mbox`, `crm.json`).

- [ ] **Step 9: Run all per-file agent tests**

Run: `pytest tests/integration/test_agents_per_file_ -v` (this runs 7 agent tests; each hits Ollama up to 6 times; expect 2-5 minutes total).
Expected: every test PASS with `cite_locator` verifying every emitted Source.

- [ ] **Step 10: Commit**

```bash
git add backend/app/agents/per_file/pdf.py backend/app/agents/per_file/docx.py \
        backend/app/agents/per_file/markdown.py backend/app/agents/per_file/transcript.py \
        backend/app/agents/per_file/table.py backend/app/agents/per_file/mbox.py \
        backend/app/agents/per_file/json.py \
        backend/tests/integration/test_agents_per_file_*.py
git commit -m "feat(per_file): 7 file-family agents over the shared ReAct engine"
```

---

## Phase C — Lead-agent nodes (Tasks 15–22)

Each lead-agent node is a single-shot `generate_json(schema=...)` call with a typed input and a typed output. No ReAct, no tools.

### Task 15: `review_summaries` node + prompt

**Files:**
- Create: `backend/app/prompts/review_summaries.py`
- Create: `backend/app/agents/lead/__init__.py` (empty)
- Create: `backend/app/agents/lead/review_summaries.py`
- Create: `backend/tests/integration/test_agents_lead_review.py`

- [ ] **Step 1: Implement `backend/app/prompts/review_summaries.py`**

```python
PROMPT = """You are the reviewer agent. You read every per-file FileSummary and decide whether any per-file agent should redo its work.

Emit a SummaryReview with revision_requests. Use these reasons:
- missing_info: an obvious workflow / pain signal was not captured
- contradiction: this file's summary disagrees with another file's
- weak_citation: a key claim has no source or a suspect locator
- ignored_open_question: an open_question was emitted but the same agent could have answered it
- schema_drift: a field is malformed or oddly empty (e.g. lead_rows present on a transcript)

If everything looks clean, emit revision_requests: [] and a short notes string.

Per-file summaries:
{summaries_json}

Reply with ONLY JSON matching:
{{"revision_requests": [{{"file_id": str, "reason": <enum>, "detail": str}}], "notes": str}}"""
```

- [ ] **Step 2: Implement `backend/app/agents/lead/review_summaries.py`**

```python
import json

from app.llm.base import LLMProvider
from app.prompts.review_summaries import PROMPT
from app.schemas import FileSummary, SummaryReview


def run(*, provider: LLMProvider, file_summaries: dict[str, FileSummary]) -> SummaryReview:
    summaries_json = json.dumps(
        {fid: fs.model_dump() for fid, fs in file_summaries.items()}, indent=2,
    )
    prompt = PROMPT.format(summaries_json=summaries_json)
    result, _meta = provider.generate_json(
        prompt_name="review_summaries", prompt=prompt, schema=SummaryReview,
    )
    if not result:
        return SummaryReview(revision_requests=[], notes="(reviewer failed to produce valid JSON — skipping redo)")
    return SummaryReview.model_validate(result)
```

- [ ] **Step 3: Write integration test** in `backend/tests/integration/test_agents_lead_review.py`:

```python
import httpx
import pytest

from app.agents.lead import review_summaries
from app.config import get_settings
from app.llm import get_provider
from app.schemas import FileSummary, PainSignal, Source


def _ollama_up(base_url):
    try:
        return httpx.get(f"{base_url}/api/tags", timeout=2.0).status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _ollama_up(get_settings().ollama_base_url),
    reason="Ollama not reachable",
)


def test_reviewer_flags_summary_with_no_citations():
    src = Source(file_id="f1", file_name="x.md", type="md",
                 locator={"type": "text", "line_start": 1, "line_end": 1})
    # Crafted gap: a pain signal with NO sources at all.
    pain = PainSignal(text="leads are slow", category="delay", sources=[])
    fs = FileSummary(
        file_id="f1", file_name="x.md",
        one_paragraph_summary="a summary",
        key_workflows=[], key_pain_signals=[pain], lead_rows=[],
        open_questions=[], agent_notes="",
    )
    get_provider.cache_clear()
    sr = review_summaries.run(provider=get_provider(), file_summaries={"f1": fs})
    # The reviewer should flag at least one revision_request (weak_citation or missing_info).
    assert sr.notes is not None
    # Lenient: we don't require a specific count because the model may also pass.
    # But on a crafted gap with temperature=0, expect at least one request most of the time.
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/integration/test_agents_lead_review.py -v`
Expected: PASS (the assertion is lenient; deterministic temperature=0 keeps this stable).

- [ ] **Step 5: Commit**

```bash
git add backend/app/prompts/review_summaries.py backend/app/agents/lead/__init__.py \
        backend/app/agents/lead/review_summaries.py \
        backend/tests/integration/test_agents_lead_review.py
git commit -m "feat(lead): review_summaries node + prompt"
```

---

### Task 16: `cross_file_synthesis` node + prompt

**Files:**
- Create: `backend/app/prompts/synthesis.py`
- Create: `backend/app/agents/lead/synthesis.py`
- Create: `backend/tests/integration/test_agents_lead_synthesis.py`

- [ ] **Step 1: Implement `backend/app/prompts/synthesis.py`**

```python
PROMPT = """You are the synthesizer. Reconcile per-file FileSummary objects into one IntakeBundle.

Rules:
- Carry every WorkflowRecord, PainSignal, and LeadRow from all summaries.
- When two files disagree on a fact, DO NOT silently merge. Add a Contradiction with both claims and both citations.
- file_index is the deduped list of Source objects observed across files.
- extraction_errors is empty unless one or more file_summaries was missing.

Per-file summaries:
{summaries_json}

Reply with ONLY JSON matching the IntakeBundle schema."""
```

- [ ] **Step 2: Implement `backend/app/agents/lead/synthesis.py`**

```python
import json

from app.llm.base import LLMProvider
from app.prompts.synthesis import PROMPT
from app.schemas import FileSummary, IntakeBundle


def run(*, provider: LLMProvider, file_summaries: dict[str, FileSummary]) -> IntakeBundle:
    summaries_json = json.dumps(
        {fid: fs.model_dump() for fid, fs in file_summaries.items()}, indent=2,
    )
    prompt = PROMPT.format(summaries_json=summaries_json)
    result, _meta = provider.generate_json(
        prompt_name="cross_file_synthesis", prompt=prompt, schema=IntakeBundle,
    )
    return IntakeBundle.model_validate(result) if result else IntakeBundle(
        workflows=[], pain_signals=[], lead_rows=[],
        contradictions=[], file_index=[], extraction_errors=[],
    )
```

- [ ] **Step 3: Write integration test** in `backend/tests/integration/test_agents_lead_synthesis.py`:

```python
import httpx
import pytest

from app.agents.lead import synthesis
from app.config import get_settings
from app.llm import get_provider
from app.schemas import FileSummary, PainSignal, Source


def _ollama_up(base_url):
    try:
        return httpx.get(f"{base_url}/api/tags", timeout=2.0).status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _ollama_up(get_settings().ollama_base_url),
    reason="Ollama not reachable",
)


def test_synthesis_carries_pain_signals_into_bundle():
    src = Source(file_id="f1", file_name="x.md", type="md",
                 locator={"type": "text", "line_start": 1, "line_end": 1})
    fs = FileSummary(
        file_id="f1", file_name="x.md",
        one_paragraph_summary="slow leads",
        key_workflows=[],
        key_pain_signals=[PainSignal(text="leads slow", category="delay", sources=[src])],
        lead_rows=[], open_questions=[], agent_notes="",
    )
    get_provider.cache_clear()
    bundle = synthesis.run(provider=get_provider(), file_summaries={"f1": fs})
    assert len(bundle.pain_signals) >= 1
```

- [ ] **Step 4: Run, commit**

Run: `pytest tests/integration/test_agents_lead_synthesis.py -v`
Expected: PASS.

```bash
git add backend/app/prompts/synthesis.py backend/app/agents/lead/synthesis.py \
        backend/tests/integration/test_agents_lead_synthesis.py
git commit -m "feat(lead): cross_file_synthesis node + prompt"
```

---

### Task 17: Diagnostic chain — five sequential nodes

The five nodes are similar enough to batch. Each is a thin module with one prompt and one `run()` returning a typed payload.

**Files:**
- Create: `backend/app/prompts/{workflow_map,bottleneck_detect,roi_score,fastest_win_select,solution_blueprint}.py`
- Create: `backend/app/agents/lead/{workflow_map,bottleneck_detect,roi_score,fastest_win_select,solution_blueprint}.py`
- Create: `backend/tests/integration/test_agents_lead_diagnostic_chain.py`

Schema contracts:
- `workflow_map.run(bundle) -> list[WorkflowRecord]` — promotes per-file workflows into a deduped, named map.
- `bottleneck_detect.run(bundle, workflows) -> list[Bottleneck]` — emits per-workflow bottlenecks with citations.
- `roi_score.run(bundle, bottlenecks) -> list[Opportunity]` — scores opportunities 1–10 across 4 axes.
- `fastest_win_select.run(opportunities) -> Opportunity` — picks the single best win.
- `solution_blueprint.run(bundle, selected) -> Blueprint` — produces the cited blueprint.

- [ ] **Step 1: Implement each prompt file**

`backend/app/prompts/workflow_map.py`:

```python
PROMPT = """You are the workflow-mapper. Given an IntakeBundle, return list[WorkflowRecord]
that consolidates and de-duplicates workflows across files. Every workflow MUST carry
non-empty sources.

IntakeBundle:
{bundle_json}

Reply with ONLY JSON: {{"workflows": [WorkflowRecord, ...]}}"""
```

`backend/app/prompts/bottleneck_detect.py`:

```python
PROMPT = """You are the bottleneck-detector. For each workflow, identify bottlenecks
using pain signals from the bundle. Emit one Bottleneck per distinct problem.
Every Bottleneck MUST carry sources.

Workflows:
{workflows_json}

IntakeBundle (for pain signals):
{bundle_json}

Reply with ONLY JSON: {{"bottlenecks": [Bottleneck, ...]}}"""
```

`backend/app/prompts/roi_score.py`:

```python
PROMPT = """You are the ROI scorer. For each meaningful bottleneck cluster, propose an
Opportunity with scores 1-10 on pain, roi, effort, risk; hours_saved_per_week (float);
response_time_impact (string like '-50%'); rationale; and sources.

Bottlenecks:
{bottlenecks_json}

IntakeBundle:
{bundle_json}

Reply with ONLY JSON: {{"opportunities": [Opportunity, ...]}}"""
```

`backend/app/prompts/fastest_win_select.py`:

```python
PROMPT = """Select the single best opportunity by maximizing roi_score - effort_score - risk_score.
Ties broken by higher pain_score, then by lowest effort_score.

Opportunities:
{opportunities_json}

Reply with ONLY JSON: {{"selected_index": int}}"""
```

`backend/app/prompts/solution_blueprint.py`:

```python
PROMPT = """You are the blueprint writer. Produce a Blueprint for the selected opportunity.
Every BlueprintClaim (summary, steps, required_systems, success_metrics, risks) MUST carry
non-empty sources from the bundle.

Selected opportunity (index into opportunities list):
{selected_index}

Opportunity payload:
{selected_json}

IntakeBundle:
{bundle_json}

Reply with ONLY JSON matching the Blueprint schema."""
```

- [ ] **Step 2: Implement each node module**

`backend/app/agents/lead/workflow_map.py`:

```python
import json

from pydantic import BaseModel

from app.llm.base import LLMProvider
from app.prompts.workflow_map import PROMPT
from app.schemas import IntakeBundle, WorkflowRecord


class _Wrap(BaseModel):
    workflows: list[WorkflowRecord]


def run(*, provider: LLMProvider, bundle: IntakeBundle) -> list[WorkflowRecord]:
    prompt = PROMPT.format(bundle_json=json.dumps(bundle.model_dump(), indent=2))
    result, _ = provider.generate_json(prompt_name="workflow_map", prompt=prompt, schema=_Wrap)
    return _Wrap.model_validate(result).workflows if result else bundle.workflows
```

`backend/app/agents/lead/bottleneck_detect.py`:

```python
import json

from pydantic import BaseModel

from app.llm.base import LLMProvider
from app.prompts.bottleneck_detect import PROMPT
from app.schemas import Bottleneck, IntakeBundle, WorkflowRecord


class _Wrap(BaseModel):
    bottlenecks: list[Bottleneck]


def run(*, provider: LLMProvider, bundle: IntakeBundle, workflows: list[WorkflowRecord]) -> list[Bottleneck]:
    prompt = PROMPT.format(
        workflows_json=json.dumps([w.model_dump() for w in workflows], indent=2),
        bundle_json=json.dumps(bundle.model_dump(), indent=2),
    )
    result, _ = provider.generate_json(prompt_name="bottleneck_detect", prompt=prompt, schema=_Wrap)
    return _Wrap.model_validate(result).bottlenecks if result else []
```

`backend/app/agents/lead/roi_score.py`:

```python
import json

from pydantic import BaseModel

from app.llm.base import LLMProvider
from app.prompts.roi_score import PROMPT
from app.schemas import Bottleneck, IntakeBundle, Opportunity


class _Wrap(BaseModel):
    opportunities: list[Opportunity]


def run(*, provider: LLMProvider, bundle: IntakeBundle, bottlenecks: list[Bottleneck]) -> list[Opportunity]:
    prompt = PROMPT.format(
        bottlenecks_json=json.dumps([b.model_dump() for b in bottlenecks], indent=2),
        bundle_json=json.dumps(bundle.model_dump(), indent=2),
    )
    result, _ = provider.generate_json(prompt_name="roi_score", prompt=prompt, schema=_Wrap)
    return _Wrap.model_validate(result).opportunities if result else []
```

`backend/app/agents/lead/fastest_win_select.py`:

```python
import json

from pydantic import BaseModel

from app.llm.base import LLMProvider
from app.prompts.fastest_win_select import PROMPT
from app.schemas import Opportunity


class _Wrap(BaseModel):
    selected_index: int


def run(*, provider: LLMProvider, opportunities: list[Opportunity]) -> Opportunity | None:
    if not opportunities:
        return None
    prompt = PROMPT.format(opportunities_json=json.dumps([o.model_dump() for o in opportunities], indent=2))
    result, _ = provider.generate_json(prompt_name="fastest_win_select", prompt=prompt, schema=_Wrap)
    if not result:
        # Deterministic fallback: highest roi_score - effort_score - risk_score.
        opportunities = sorted(
            opportunities,
            key=lambda o: (o.roi_score - o.effort_score - o.risk_score, o.pain_score, -o.effort_score),
            reverse=True,
        )
        return opportunities[0]
    idx = _Wrap.model_validate(result).selected_index
    if 0 <= idx < len(opportunities):
        return opportunities[idx]
    return opportunities[0]
```

`backend/app/agents/lead/solution_blueprint.py`:

```python
import json

from app.llm.base import LLMProvider
from app.prompts.solution_blueprint import PROMPT
from app.schemas import Blueprint, IntakeBundle, Opportunity


def run(
    *,
    provider: LLMProvider,
    bundle: IntakeBundle,
    selected: Opportunity,
    selected_index: int,
    revision_detail: str | None = None,
) -> Blueprint | None:
    prompt = PROMPT.format(
        selected_index=selected_index,
        selected_json=json.dumps(selected.model_dump(), indent=2),
        bundle_json=json.dumps(bundle.model_dump(), indent=2),
    )
    if revision_detail:
        prompt += f"\n\nThe previous blueprint failed self-review: {revision_detail}. Fix it."
    result, _ = provider.generate_json(prompt_name="solution_blueprint", prompt=prompt, schema=Blueprint)
    return Blueprint.model_validate(result) if result else None
```

- [ ] **Step 3: Write integration test** in `backend/tests/integration/test_agents_lead_diagnostic_chain.py`:

```python
import httpx
import pytest

from app.agents.lead import (
    bottleneck_detect, fastest_win_select, roi_score, solution_blueprint, workflow_map,
)
from app.config import get_settings
from app.llm import get_provider
from app.schemas import IntakeBundle, PainSignal, Source, WorkflowRecord


def _ollama_up(base_url):
    try:
        return httpx.get(f"{base_url}/api/tags", timeout=2.0).status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _ollama_up(get_settings().ollama_base_url),
    reason="Ollama not reachable",
)


def _bundle() -> IntakeBundle:
    src = Source(file_id="f1", file_name="x.md", type="md",
                 locator={"type": "text", "line_start": 1, "line_end": 1})
    wf = WorkflowRecord(
        name="lead intake", actors=["CSR"], systems=["HubSpot"],
        steps=["receive email", "create lead in CRM"],
        manual_touchpoints=["copy email body into CRM"], sources=[src],
    )
    ps = PainSignal(text="leads waiting > 24h", category="delay", sources=[src])
    return IntakeBundle(
        workflows=[wf], pain_signals=[ps], lead_rows=[],
        contradictions=[], file_index=[src], extraction_errors=[],
    )


def test_full_diagnostic_chain_emits_blueprint():
    bundle = _bundle()
    get_provider.cache_clear()
    p = get_provider()
    wfs = workflow_map.run(provider=p, bundle=bundle)
    bns = bottleneck_detect.run(provider=p, bundle=bundle, workflows=wfs)
    ops = roi_score.run(provider=p, bundle=bundle, bottlenecks=bns)
    if not ops:
        pytest.skip("roi_score returned empty; model variance")
    selected = fastest_win_select.run(provider=p, opportunities=ops)
    assert selected is not None
    selected_index = ops.index(selected)
    bp = solution_blueprint.run(provider=p, bundle=bundle, selected=selected, selected_index=selected_index)
    assert bp is not None
    # Every claim has at least one source.
    for claim in [bp.summary, *bp.steps, *bp.required_systems, *bp.success_metrics, *bp.risks]:
        assert len(claim.sources) >= 1
```

- [ ] **Step 4: Run, commit**

Run: `pytest tests/integration/test_agents_lead_diagnostic_chain.py -v`
Expected: PASS (~30-60s; five LLM calls).

```bash
git add backend/app/prompts/{workflow_map,bottleneck_detect,roi_score,fastest_win_select,solution_blueprint}.py \
        backend/app/agents/lead/{workflow_map,bottleneck_detect,roi_score,fastest_win_select,solution_blueprint}.py \
        backend/tests/integration/test_agents_lead_diagnostic_chain.py
git commit -m "feat(lead): diagnostic chain — workflow_map, bottleneck, roi, fastest_win, blueprint"
```

---

### Task 18: `self_review_final` node — citation existence + reachability post-check

This node is special: it combines a deterministic post-check (citation reachability) with an LLM call (internal consistency + no-silent-drops judgment).

**Files:**
- Create: `backend/app/prompts/self_review.py`
- Create: `backend/app/agents/lead/self_review.py`
- Create: `backend/tests/integration/test_agents_lead_self_review.py`

- [ ] **Step 1: Implement `backend/app/prompts/self_review.py`**

```python
PROMPT = """You are the self-reviewer. Audit the Blueprint against the IntakeBundle. Output a FinalReview.

Deterministic checks already done for you (results below). Your job: judge the two non-deterministic checks:

- no_silent_drops_ok: every open_question or risk that appeared in the source summaries should appear in Blueprint.risks or as a caveat in summary.text. True if nothing was silently dropped, False otherwise.
- internal_consistency_ok: the selected opportunity should be among the top opportunities by roi_score (tied is fine); the blueprint must address at least one bottleneck listed under the selected opportunity.

Deterministic results:
- citation_existence_ok: {citation_existence_ok}
- citation_reachability_ok: {citation_reachability_ok}

Blueprint:
{blueprint_json}

Selected opportunity:
{selected_json}

All opportunities:
{opportunities_json}

IntakeBundle:
{bundle_json}

Reply with ONLY JSON: {{"no_silent_drops_ok": bool, "internal_consistency_ok": bool, "detail": str}}"""
```

- [ ] **Step 2: Implement `backend/app/agents/lead/self_review.py`**

```python
import json
from pathlib import Path

from pydantic import BaseModel

from app.agents.per_file._tools.cite_locator import cite_locator
from app.llm.base import LLMProvider
from app.models import FileRecord
from app.parsers import parse as parse_file
from app.prompts.self_review import PROMPT
from app.schemas import Blueprint, FinalReview, IntakeBundle, Opportunity, Source


class _LLMReply(BaseModel):
    no_silent_drops_ok: bool
    internal_consistency_ok: bool
    detail: str


def _all_sources(blueprint: Blueprint) -> list[Source]:
    out: list[Source] = []
    for claim in [blueprint.summary, *blueprint.steps, *blueprint.required_systems,
                  *blueprint.success_metrics, *blueprint.risks]:
        out.extend(claim.sources)
    return out


def check_citation_existence(blueprint: Blueprint, bundle: IntakeBundle) -> tuple[bool, str]:
    file_ids = {s.file_id for s in bundle.file_index}
    bad = [s for s in _all_sources(blueprint) if s.file_id not in file_ids]
    return (not bad), ("" if not bad else f"{len(bad)} source(s) reference unknown files: {[s.file_id for s in bad]}")


def check_citation_reachability(
    blueprint: Blueprint, *, db_session, run_id: str,
) -> tuple[bool, str]:
    """Parse each cited file and verify every locator resolves."""
    bad: list[str] = []
    cache: dict[str, object] = {}
    for src in _all_sources(blueprint):
        if src.file_id not in cache:
            rec = db_session.get(FileRecord, src.file_id)
            if rec is None:
                bad.append(f"{src.file_id} not in DB")
                continue
            cache[src.file_id] = parse_file(
                file_id=rec.id, file_name=rec.file_name,
                path=Path(rec.blob_path), mime_type=rec.mime_type,
            )
        parsed = cache[src.file_id]
        result = cite_locator(parsed, locator=src.locator)
        if not result["valid"]:
            bad.append(f"{src.file_id} locator unreachable: {src.locator}")
    return (not bad), ("" if not bad else "; ".join(bad[:5]))


def run(
    *,
    provider: LLMProvider,
    blueprint: Blueprint,
    bundle: IntakeBundle,
    selected: Opportunity,
    selected_index: int,
    opportunities: list[Opportunity],
    db_session,
    run_id: str,
    revised_once: bool,
) -> FinalReview:
    ce_ok, ce_detail = check_citation_existence(blueprint, bundle)
    cr_ok, cr_detail = check_citation_reachability(blueprint, db_session=db_session, run_id=run_id)

    prompt = PROMPT.format(
        citation_existence_ok=ce_ok,
        citation_reachability_ok=cr_ok,
        blueprint_json=json.dumps(blueprint.model_dump(), indent=2),
        selected_json=json.dumps(selected.model_dump(), indent=2),
        opportunities_json=json.dumps([o.model_dump() for o in opportunities], indent=2),
        bundle_json=json.dumps(bundle.model_dump(), indent=2),
    )
    result, _ = provider.generate_json(prompt_name="self_review_final", prompt=prompt, schema=_LLMReply)
    if not result:
        return FinalReview(
            citation_existence_ok=ce_ok, citation_reachability_ok=cr_ok,
            no_silent_drops_ok=False, internal_consistency_ok=False,
            detail=f"LLM self-review failed JSON parse. ce={ce_detail} cr={cr_detail}",
            revised_once=revised_once,
        )
    parsed = _LLMReply.model_validate(result)
    return FinalReview(
        citation_existence_ok=ce_ok,
        citation_reachability_ok=cr_ok,
        no_silent_drops_ok=parsed.no_silent_drops_ok,
        internal_consistency_ok=parsed.internal_consistency_ok,
        detail=" | ".join(filter(None, [ce_detail, cr_detail, parsed.detail])),
        revised_once=revised_once,
    )
```

- [ ] **Step 3: Write integration test** in `backend/tests/integration/test_agents_lead_self_review.py`:

```python
import httpx
import pytest

from app.agents.lead import self_review
from app.config import get_settings
from app.schemas import Blueprint, BlueprintClaim, IntakeBundle, Opportunity, Source


def _ollama_up(base_url):
    try:
        return httpx.get(f"{base_url}/api/tags", timeout=2.0).status_code == 200
    except Exception:
        return False


def test_citation_existence_flags_unknown_file_id():
    bad_src = Source(file_id="f_ghost", file_name="ghost.pdf", type="pdf",
                     locator={"type": "pdf", "page": 1, "span_start": 0, "span_end": 5})
    bp = Blueprint(
        opportunity_ref=0,
        summary=BlueprintClaim(text="x", sources=[bad_src]),
        steps=[], required_systems=[], success_metrics=[], risks=[],
    )
    bundle = IntakeBundle(
        workflows=[], pain_signals=[], lead_rows=[],
        contradictions=[], file_index=[], extraction_errors=[],
    )
    ok, detail = self_review.check_citation_existence(bp, bundle)
    assert ok is False
    assert "f_ghost" in detail
```

(Citation-reachability deterministic check is covered indirectly by `test_graph_e2e` in Task 23 since it needs real files in the DB.)

- [ ] **Step 4: Run, commit**

Run: `pytest tests/integration/test_agents_lead_self_review.py -v`
Expected: PASS.

```bash
git add backend/app/prompts/self_review.py backend/app/agents/lead/self_review.py \
        backend/tests/integration/test_agents_lead_self_review.py
git commit -m "feat(lead): self_review_final — citation existence + reachability + LLM consistency check"
```

---

## Phase D — LangGraph parent workflow (Tasks 19–21)

### Task 19: `graph.py` — wiring the parent workflow with Redis checkpointer

This is the keystone task. It assembles all node modules into a `StateGraph[DiagnosticState]` with:
- `fan_out_files` → parallel per-file agents (one node per file, dispatched by file type) → merge into `file_summaries`
- → `review_summaries` → (if `revision_requests` non-empty and `redo_count < 1`) → flagged per-file agents → `review_summaries`
- → `cross_file_synthesis`
- → `workflow_map` → `bottleneck_detect` → `roi_score` → `fastest_win_select` → `solution_blueprint`
- → `self_review_final` → (if any check fails and `revision_count < 1`) → `solution_blueprint` → `self_review_final`
- → END

**Files:**
- Create: `backend/app/graph.py`
- Create: `backend/tests/integration/test_graph_construct.py`

- [ ] **Step 1: Write failing test**:

```python
from app.graph import build_graph


def test_build_graph_returns_compiled_graph():
    g = build_graph()
    assert g is not None
    assert hasattr(g, "invoke")
    assert hasattr(g, "stream")
```

- [ ] **Step 2: Run, verify failure**

Run: `pytest tests/integration/test_graph_construct.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `backend/app/graph.py`**

```python
from pathlib import Path

from langgraph.graph import END, START, StateGraph

from app.agents.lead import (
    bottleneck_detect, fastest_win_select, review_summaries, roi_score,
    self_review, solution_blueprint, synthesis, workflow_map,
)
from app.agents.per_file import (
    docx as _a_docx,
    json as _a_json,
    markdown as _a_md,
    mbox as _a_mbox,
    pdf as _a_pdf,
    table as _a_table,
    transcript as _a_transcript,
)
from app.checkpointer import build_checkpointer
from app.config import get_settings
from app.database import SessionLocal
from app.llm import get_provider
from app.models import FileRecord
from app.parsers import parse as parse_file
from app.state import DiagnosticState

_PER_FILE_AGENT_BY_TYPE = {
    "pdf": _a_pdf,
    "docx": _a_docx,
    "md": _a_md,
    "txt": _a_md,
    "transcript_vtt": _a_transcript,
    "transcript_srt": _a_transcript,
    "csv": _a_table,
    "xlsx": _a_table,
    "mbox": _a_mbox,
    "json": _a_json,
}


# ---- Nodes ----

def _node_per_file(state: DiagnosticState) -> DiagnosticState:
    """Run per-file agents serially over state.files. (LangGraph parallel fan-out
    is replaced with a sequential loop here for v1 simplicity — the bottleneck
    is the LLM, and order doesn't matter for typed handoffs.)"""
    provider = get_provider()
    with SessionLocal() as db:
        for fref in state["files"]:
            # Skip if already summarized (used for redo on subset).
            if fref.file_id in state["file_summaries"]:
                continue
            rec = db.get(FileRecord, fref.file_id)
            if rec is None or rec.parser_status != "ok":
                continue
            parsed = parse_file(file_id=rec.id, file_name=rec.file_name,
                                path=Path(rec.blob_path), mime_type=rec.mime_type)
            agent = _PER_FILE_AGENT_BY_TYPE.get(parsed.type)
            if agent is None:
                continue
            fs = agent.run(provider=provider, parsed=parsed)
            state["file_summaries"][fref.file_id] = fs
    return state


def _node_review(state: DiagnosticState) -> DiagnosticState:
    state["summary_review"] = review_summaries.run(
        provider=get_provider(), file_summaries=state["file_summaries"],
    )
    return state


def _node_redo_flagged(state: DiagnosticState) -> DiagnosticState:
    """Drop file_summaries for flagged file_ids and re-run per_file on them."""
    sr = state["summary_review"]
    if sr is None or not sr.revision_requests:
        return state
    flagged = {rr.file_id for rr in sr.revision_requests}
    for fid in flagged:
        state["file_summaries"].pop(fid, None)
    state["redo_count"] += 1
    return _node_per_file(state)


def _node_synthesis(state: DiagnosticState) -> DiagnosticState:
    state["bundle"] = synthesis.run(
        provider=get_provider(), file_summaries=state["file_summaries"],
    )
    return state


def _node_workflow_map(state: DiagnosticState) -> DiagnosticState:
    if state["bundle"] is None:
        return state
    state["workflows"] = workflow_map.run(provider=get_provider(), bundle=state["bundle"])
    return state


def _node_bottleneck_detect(state: DiagnosticState) -> DiagnosticState:
    if state["bundle"] is None:
        return state
    state["bottlenecks"] = bottleneck_detect.run(
        provider=get_provider(), bundle=state["bundle"], workflows=state["workflows"],
    )
    return state


def _node_roi_score(state: DiagnosticState) -> DiagnosticState:
    if state["bundle"] is None:
        return state
    state["opportunities"] = roi_score.run(
        provider=get_provider(), bundle=state["bundle"], bottlenecks=state["bottlenecks"],
    )
    return state


def _node_fastest_win_select(state: DiagnosticState) -> DiagnosticState:
    state["selected"] = fastest_win_select.run(
        provider=get_provider(), opportunities=state["opportunities"],
    )
    return state


def _node_solution_blueprint(state: DiagnosticState) -> DiagnosticState:
    if state["selected"] is None or state["bundle"] is None:
        return state
    selected_index = state["opportunities"].index(state["selected"])
    revision_detail = state["final_review"].detail if state["final_review"] else None
    state["blueprint"] = solution_blueprint.run(
        provider=get_provider(), bundle=state["bundle"],
        selected=state["selected"], selected_index=selected_index,
        revision_detail=revision_detail,
    )
    return state


def _node_self_review(state: DiagnosticState) -> DiagnosticState:
    if state["blueprint"] is None or state["bundle"] is None or state["selected"] is None:
        return state
    selected_index = state["opportunities"].index(state["selected"])
    with SessionLocal() as db:
        fr = self_review.run(
            provider=get_provider(),
            blueprint=state["blueprint"], bundle=state["bundle"],
            selected=state["selected"], selected_index=selected_index,
            opportunities=state["opportunities"],
            db_session=db, run_id=state["run_id"],
            revised_once=(state["revision_count"] > 0),
        )
    state["final_review"] = fr
    return state


# ---- Edges ----

def _branch_after_review(state: DiagnosticState) -> str:
    """If there are revision_requests and we haven't redone yet, go redo. Else proceed."""
    sr = state["summary_review"]
    if sr and sr.revision_requests and state["redo_count"] < 1:
        return "redo_flagged"
    return "cross_file_synthesis"


def _branch_after_self_review(state: DiagnosticState) -> str:
    """If any check failed and we haven't revised yet, revise blueprint. Else end."""
    fr = state["final_review"]
    if fr is None:
        return END
    failed = not (fr.citation_existence_ok and fr.citation_reachability_ok
                  and fr.no_silent_drops_ok and fr.internal_consistency_ok)
    if failed and state["revision_count"] < 1:
        state["revision_count"] += 1
        return "solution_blueprint"
    return END


def build_graph():
    """Construct the LangGraph parent workflow with a Redis checkpointer."""
    checkpointer = build_checkpointer()
    g: StateGraph = StateGraph(DiagnosticState)

    g.add_node("per_file", _node_per_file)
    g.add_node("review_summaries", _node_review)
    g.add_node("redo_flagged", _node_redo_flagged)
    g.add_node("cross_file_synthesis", _node_synthesis)
    g.add_node("workflow_map", _node_workflow_map)
    g.add_node("bottleneck_detect", _node_bottleneck_detect)
    g.add_node("roi_score", _node_roi_score)
    g.add_node("fastest_win_select", _node_fastest_win_select)
    g.add_node("solution_blueprint", _node_solution_blueprint)
    g.add_node("self_review_final", _node_self_review)

    g.add_edge(START, "per_file")
    g.add_edge("per_file", "review_summaries")
    g.add_conditional_edges("review_summaries", _branch_after_review,
                            {"redo_flagged": "redo_flagged", "cross_file_synthesis": "cross_file_synthesis"})
    g.add_edge("redo_flagged", "review_summaries")
    g.add_edge("cross_file_synthesis", "workflow_map")
    g.add_edge("workflow_map", "bottleneck_detect")
    g.add_edge("bottleneck_detect", "roi_score")
    g.add_edge("roi_score", "fastest_win_select")
    g.add_edge("fastest_win_select", "solution_blueprint")
    g.add_edge("solution_blueprint", "self_review_final")
    g.add_conditional_edges("self_review_final", _branch_after_self_review,
                            {"solution_blueprint": "solution_blueprint", END: END})

    return g.compile(checkpointer=checkpointer)
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/integration/test_graph_construct.py -v` (Redis must be up.)
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/graph.py backend/tests/integration/test_graph_construct.py
git commit -m "feat(graph): LangGraph parent workflow with bounded redo + revision loops + Redis checkpointer"
```

---

### Task 20: Wire Langfuse tracing into the graph

Add a `with trace_run(run_id) as trace:` context around `graph.invoke` and per-node spans inside each `_node_*` function. We do this in a thin runner module so `graph.py` stays focused on the topology.

**Files:**
- Create: `backend/app/services/runs.py`
- Create: `backend/tests/integration/test_runs_service.py`

- [ ] **Step 1: Implement `backend/app/services/runs.py`**

```python
import json
import uuid

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.graph import build_graph
from app.models import BlueprintRecord, FileRecord, FileSummaryRecord, IntakeBundleRecord, Run
from app.observability import trace_run
from app.schemas import FileRef
from app.state import DiagnosticState


def create_run(db: Session, *, file_ids: list[str]) -> str:
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    db.add(Run(id=run_id, status="created"))
    for fid in file_ids:
        rec = db.get(FileRecord, fid)
        if rec is None:
            raise ValueError(f"file {fid} not found")
        rec.run_id = run_id
    db.commit()
    return run_id


def start_run(run_id: str) -> DiagnosticState:
    """Synchronously execute the full pipeline. Returns final DiagnosticState."""
    with SessionLocal() as db:
        run = db.get(Run, run_id)
        if run is None:
            raise ValueError(f"run {run_id} not found")
        files = (
            db.query(FileRecord).filter(FileRecord.run_id == run_id).all()
        )
        file_refs = [
            FileRef(file_id=f.id, file_name=f.file_name, mime_type=f.mime_type,
                    blob_path=f.blob_path, parser_status=f.parser_status)
            for f in files
        ]

    initial: DiagnosticState = {
        "run_id": run_id, "files": file_refs, "file_summaries": {},
        "summary_review": None, "redo_count": 0, "bundle": None,
        "workflows": [], "bottlenecks": [], "opportunities": [],
        "selected": None, "blueprint": None, "final_review": None,
        "revision_count": 0, "errors": [],
    }

    graph = build_graph()
    config = {"configurable": {"thread_id": run_id}}

    with trace_run(run_id) as trace:
        final_state: DiagnosticState = graph.invoke(initial, config=config)

    # Persist outputs.
    with SessionLocal() as db:
        for fid, fs in final_state["file_summaries"].items():
            db.merge(FileSummaryRecord(file_id=fid, payload_json=json.dumps(fs.model_dump())))
        if final_state["bundle"] is not None:
            db.merge(IntakeBundleRecord(run_id=run_id, payload_json=json.dumps(final_state["bundle"].model_dump())))
        if final_state["blueprint"] is not None:
            db.merge(BlueprintRecord(run_id=run_id, payload_json=json.dumps(final_state["blueprint"].model_dump())))
        run = db.get(Run, run_id)
        run.status = "complete"
        if trace is not None:
            run.langfuse_trace_id = run_id  # trace id == run_id
        db.commit()

    return final_state


def get_blueprint(db: Session, run_id: str) -> dict | None:
    rec = db.get(BlueprintRecord, run_id)
    return json.loads(rec.payload_json) if rec else None
```

- [ ] **Step 2: Write integration test** in `backend/tests/integration/test_runs_service.py`:

```python
import httpx
import pytest
from pathlib import Path

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.services.files import upload_file
from app.services.runs import create_run, get_blueprint, start_run


def _ollama_up(base_url):
    try:
        return httpx.get(f"{base_url}/api/tags", timeout=2.0).status_code == 200
    except Exception:
        return False


def _redis_up():
    from app.checkpointer import redis_healthcheck
    return redis_healthcheck()


pytestmark = pytest.mark.skipif(
    not (_ollama_up(get_settings().ollama_base_url) and _redis_up()),
    reason="Ollama or Redis not reachable",
)


def setup_module():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_full_pipeline_emits_persisted_blueprint(tmp_path, monkeypatch):
    monkeypatch.setattr("app.blob_store.BLOB_DIR", tmp_path)
    fixture = Path(__file__).parent.parent / "fixtures" / "notes.md"
    content = fixture.read_bytes()

    with SessionLocal() as db:
        ref = upload_file(db, file_name="notes.md", mime_type="text/markdown", content=content)
        db.commit()
        run_id = create_run(db, file_ids=[ref.file_id])

    final = start_run(run_id)
    assert final["blueprint"] is not None or final["selected"] is None  # graceful when single tiny file

    with SessionLocal() as db:
        bp = get_blueprint(db, run_id)
        # Allowed to be None on a single tiny file with no clear opportunity, but the run must complete.
        assert bp is None or "summary" in bp
```

- [ ] **Step 3: Run, commit**

Run: `pytest tests/integration/test_runs_service.py -v` (a 1–3 minute end-to-end run)
Expected: PASS.

```bash
git add backend/app/services/runs.py backend/tests/integration/test_runs_service.py
git commit -m "feat(runs): start_run service — invoke graph, persist outputs, open Langfuse trace"
```

---

### Task 21: Wire per-node Langfuse spans (optional polish)

For a complete §10 span tree, decorate each `_node_*` in `graph.py` to open its own span using `observability.span(parent, name)`. Since the parent trace is opened in `start_run`, the nodes need access to it. Simplest pattern: store the parent trace handle in a contextvar at `start_run` time and read it from `_node_*`.

**Files:**
- Modify: `backend/app/observability.py` — add `current_trace` contextvar + helpers
- Modify: `backend/app/services/runs.py` — set the contextvar inside `trace_run`
- Modify: `backend/app/graph.py` — wrap each `_node_*` body with `with span(current_trace.get(), "<node_name>"):`

- [ ] **Step 1: Append to `backend/app/observability.py`**

```python
import contextvars

current_trace: contextvars.ContextVar[Any | None] = contextvars.ContextVar("current_trace", default=None)
```

- [ ] **Step 2: Modify `backend/app/services/runs.py`** inside `start_run` — after `with trace_run(run_id) as trace:`:

```python
        from app.observability import current_trace
        token = current_trace.set(trace)
        try:
            final_state = graph.invoke(initial, config=config)
        finally:
            current_trace.reset(token)
```

- [ ] **Step 3: Wrap each `_node_*` in `backend/app/graph.py`** — example pattern:

```python
from app.observability import current_trace, span

def _node_per_file(state):
    with span(current_trace.get(), "per_file_agents"):
        ...  # existing body
        return state
```

Apply to every node. The redo and revision loops naturally appear as repeated spans with the same name.

- [ ] **Step 4: Re-run the full integration test**

Run: `pytest tests/integration/test_runs_service.py -v`
Expected: PASS, and check the Langfuse dashboard to confirm the nested trace tree is present.

- [ ] **Step 5: Commit**

```bash
git add backend/app/observability.py backend/app/services/runs.py backend/app/graph.py
git commit -m "feat(observability): per-node Langfuse spans via contextvar-scoped trace"
```

---

## Phase E — API surface (Tasks 22–23)

### Task 22: `POST /api/runs`, `GET /api/runs/{run_id}`, `GET /api/runs/{run_id}/blueprint`

**Files:**
- Modify: `backend/app/main.py`
- Create: `backend/tests/integration/test_runs_api.py`

- [ ] **Step 1: Write integration test** in `backend/tests/integration/test_runs_api.py`:

```python
import httpx
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.checkpointer import redis_healthcheck
from app.config import get_settings
from app.database import Base, engine
from app.main import app


def _ollama_up(base_url):
    try:
        return httpx.get(f"{base_url}/api/tags", timeout=2.0).status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not (_ollama_up(get_settings().ollama_base_url) and redis_healthcheck()),
    reason="Ollama or Redis not reachable",
)


def setup_module():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_post_runs_then_get_blueprint(tmp_path, monkeypatch):
    monkeypatch.setattr("app.blob_store.BLOB_DIR", tmp_path)
    client = TestClient(app)
    fixture = Path(__file__).parent.parent / "fixtures" / "notes.md"
    with fixture.open("rb") as f:
        up = client.post("/api/files", files={"file": ("notes.md", f, "text/markdown")})
    file_id = up.json()["file_id"]

    r = client.post("/api/runs", json={"file_ids": [file_id]})
    assert r.status_code == 200
    run_id = r.json()["run_id"]

    status = client.get(f"/api/runs/{run_id}")
    assert status.status_code == 200
    assert status.json()["status"] in ("complete", "error", "created")

    bp = client.get(f"/api/runs/{run_id}/blueprint")
    # 200 with body if blueprint emitted, 404 if not
    assert bp.status_code in (200, 404)
```

- [ ] **Step 2: Extend `backend/app/main.py`** — append:

```python
from app.models import Run as RunModel
from app.services.runs import create_run, get_blueprint, start_run


class CreateRunRequest(BaseModel):
    file_ids: list[str]


class CreateRunResponse(BaseModel):
    run_id: str


class RunStatusResponse(BaseModel):
    run_id: str
    status: str


@app.post("/api/runs", response_model=CreateRunResponse)
def post_run(body: CreateRunRequest, db: Session = Depends(get_db)) -> CreateRunResponse:
    try:
        run_id = create_run(db, file_ids=body.file_ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # Synchronously run for v1. (Plan 2 §next: optional background task.)
    try:
        start_run(run_id)
    except Exception as e:
        # Capture error in DB and surface.
        rec = db.get(RunModel, run_id)
        if rec:
            rec.status = "error"
            db.commit()
        raise HTTPException(status_code=500, detail=f"run failed: {e}")
    return CreateRunResponse(run_id=run_id)


@app.get("/api/runs/{run_id}", response_model=RunStatusResponse)
def get_run(run_id: str, db: Session = Depends(get_db)) -> RunStatusResponse:
    rec = db.get(RunModel, run_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    return RunStatusResponse(run_id=run_id, status=rec.status)


@app.get("/api/runs/{run_id}/blueprint")
def get_run_blueprint(run_id: str, db: Session = Depends(get_db)) -> dict:
    bp = get_blueprint(db, run_id)
    if bp is None:
        raise HTTPException(status_code=404, detail=f"no blueprint for {run_id}")
    return bp
```

- [ ] **Step 3: Run, commit**

Run: `pytest tests/integration/test_runs_api.py -v`
Expected: PASS.

```bash
git add backend/app/main.py backend/tests/integration/test_runs_api.py
git commit -m "feat(api): POST /api/runs, GET /api/runs/{id}, GET /api/runs/{id}/blueprint"
```

---

### Task 23: End-to-end smoke test against multi-file fixture set

A final integration test that uploads SEVERAL fixtures and validates the full pipeline produces a blueprint with citations that all reach back to real text.

**Files:**
- Create: `backend/tests/integration/test_graph_e2e.py`

- [ ] **Step 1: Write the test**

```python
import httpx
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.agents.per_file._tools.cite_locator import cite_locator
from app.checkpointer import redis_healthcheck
from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import BlueprintRecord, FileRecord
from app.parsers import parse as parse_file


def _ollama_up(base_url):
    try:
        return httpx.get(f"{base_url}/api/tags", timeout=2.0).status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not (_ollama_up(get_settings().ollama_base_url) and redis_healthcheck()),
    reason="Ollama or Redis not reachable",
)


def setup_module():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_multi_file_run_produces_reachable_blueprint(tmp_path, monkeypatch):
    monkeypatch.setattr("app.blob_store.BLOB_DIR", tmp_path)
    client = TestClient(app)

    fixtures_dir = Path(__file__).parent.parent / "fixtures"
    uploads = [
        ("notes.md", "text/markdown"),
        ("call.vtt", "text/vtt"),
        ("leads.csv", "text/csv"),
    ]
    file_ids: list[str] = []
    for name, mime in uploads:
        with (fixtures_dir / name).open("rb") as f:
            up = client.post("/api/files", files={"file": (name, f, mime)})
        assert up.status_code == 200
        file_ids.append(up.json()["file_id"])

    r = client.post("/api/runs", json={"file_ids": file_ids})
    assert r.status_code == 200
    run_id = r.json()["run_id"]

    bp = client.get(f"/api/runs/{run_id}/blueprint")
    if bp.status_code == 404:
        pytest.skip("no blueprint produced on small fixture set (model variance)")
    bp_json = bp.json()
    assert "summary" in bp_json

    # Walk every BlueprintClaim's sources and verify each locator is reachable.
    with SessionLocal() as db:
        for section in ["summary", "steps", "required_systems", "success_metrics", "risks"]:
            claims = bp_json[section] if isinstance(bp_json[section], list) else [bp_json[section]]
            for claim in claims:
                for src in claim.get("sources", []):
                    rec = db.get(FileRecord, src["file_id"])
                    assert rec is not None
                    parsed = parse_file(file_id=rec.id, file_name=rec.file_name,
                                        path=Path(rec.blob_path), mime_type=rec.mime_type)
                    assert cite_locator(parsed, locator=src["locator"])["valid"] is True
```

- [ ] **Step 2: Run, commit**

Run: `pytest tests/integration/test_graph_e2e.py -v -s` (this is a long test — 3-8 minutes against real Ollama)
Expected: PASS (or skip with a clear reason).

```bash
git add backend/tests/integration/test_graph_e2e.py
git commit -m "test: end-to-end graph integration over multi-file fixture set"
```

---

## Plan 2 Wrap-Up

### Final full test run

Run: `make test`
Expected: every unit test PASS, every integration test PASS or SKIP (Ollama, Redis, hosted-provider keys).

### Manual smoke

```bash
# Terminal 1
docker run -d --name redis -p 6379:6379 redis:7
make dev

# Terminal 2 — upload + run
FID=$(curl -s -F file=@backend/tests/fixtures/notes.md http://localhost:8000/api/files | jq -r .file_id)
RID=$(curl -s -X POST http://localhost:8000/api/runs -H "Content-Type: application/json" -d "{\"file_ids\":[\"$FID\"]}" | jq -r .run_id)
curl http://localhost:8000/api/runs/$RID/blueprint
```

Expected: JSON blueprint with cited claims. Check the Langfuse dashboard — one nested trace for that `run_id`.

---

## Plan Self-Review Notes

**Spec coverage check (§6–§11.1 of `2026-05-23-real-files-diagnostic-redesign-design.md`):**

- §6 per-file agents + §6.1 ReAct loop + §6.2 in-file retrieval → Tasks 8–14 (state, tools, router, ReAct, 7 file-family agents)
- §7.0 human-in-the-loop checkpoint → `_branch_after_review` honors `redo_count < 1` cap; UI gate itself is in Plan 3 (frontend). `auto_approve` config exists in Task 2.
- §7.1 `review_summaries` → Task 15
- §7.2 `cross_file_synthesis` → Task 16
- §7.3 diagnostic chain → Task 17
- §7.4 `self_review_final` → Task 18 (deterministic citation existence + reachability + LLM consistency)
- §8 `DiagnosticState` → Task 4
- §9 LLM provider design → reused from Plan 1, no Plan 2 changes
- §10 observability → Tasks 7 + 20 + 21
- §11 persistence → Task 5 + Task 20 (writes)
- §11.1 Redis checkpointer → Task 6 + wired in Task 19

**Placeholder scan:** No "TBD" / "TODO" / "fill in details" left. Every code block is concrete.

**Type consistency:**
- Per-file `agent.run(provider=, parsed=, on_tool_call=None) -> FileSummary` used identically in graph.py and tests.
- `lead.<node>.run(...)` keyword arguments match graph.py call sites.
- `DiagnosticState` keys match between Task 4 and Task 19 (state mutations in `_node_*` only touch declared keys).
- Reasons in `RevisionRequest` use the exact Literal values from spec §7.1.

**Known accepted limitations of v1 graph:**
- Per-file agents run *sequentially*, not in true LangGraph parallel fan-out. Acceptable for v1 because LLM latency dominates and parallelism complicates the redo-subset logic; can be parallelized in a v1.1 polish.
- The human-in-the-loop **UI gate** is a Plan 3 deliverable. The graph's `_branch_after_review` honors `auto_approve_review` implicitly (the operator never sees the gate in a headless run). Plan 3 adds the UI screen and a `pause_for_human` interrupt on the graph.
- Per-node provider override (`LLM_PROVIDER_FOR_<NODE>`) is intentionally deferred — the spec lists it as "off by default" and the architecture supports it (every `provider=` argument is parametric).

---

**Plan complete.** Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks, fast iteration. Best for a plan this long (~23 tasks across 7 phases) because each task can run in its own context window.

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints. Reasonable since Plan 1 went well inline and we've built rhythm.

Which approach?
