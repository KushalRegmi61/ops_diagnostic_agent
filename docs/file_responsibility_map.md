# File Responsibility Map

This document explains what each file is responsible for in the redesigned project. Use it as a map while building. Authoritative spec: [`superpowers/specs/2026-05-23-real-files-diagnostic-redesign-design.md`](superpowers/specs/2026-05-23-real-files-diagnostic-redesign-design.md).

## Root Files

### `README.md`

Starting point. Explains what the project is, why it exists, how to run `make demo`, and which docs to read next.

### `.env.example`

All configuration keys for local development. Groups: database, LLM provider (Ollama / OpenAI / Groq / OpenAI-compatible — no mock), Langfuse, optional per-node provider overrides. No action-safety flags (v1 has no outbound actions).

### `Makefile`

Targets: `dev`, `test`, `demo`. `demo` boots services, pulls the Ollama model, runs the pipeline against `/samples`, opens the browser.

### `docker-compose.yml`

Local services: backend, frontend, Postgres. Optionally documents Ollama setup (usually installed on the host).

### `.gitignore`

Excludes venvs, `node_modules`, `.next`, local databases, `.env`, uploaded blobs.

## Sample Dataset

### `samples/`

Realistic anonymized input files covering every supported type — at least one PDF SOP, one VTT transcript, one CSV lead list, one MBOX export, one JSON CRM dump. Used by `make demo` and integration tests.

## Backend Files

### `backend/pyproject.toml`

Dependencies: FastAPI, Uvicorn, SQLAlchemy, Pydantic settings, LangGraph, **`langgraph-checkpoint-redis`** (Redis-backed checkpointer), `redis`, Langfuse, OpenAI SDK, HTTP client (httpx) for Ollama/Groq, PyMuPDF, python-docx, pandas, openpyxl, webvtt-py, srt, pytest.

### `backend/app/config.py`

Typed settings. Allowed providers: `Literal["ollama", "openai", "groq", "openai_compatible"]`. Database URL, **`REDIS_URL` (required for the LangGraph checkpointer)**, `LANGGRAPH_CHECKPOINTER`, `LANGGRAPH_CHECKPOINT_NAMESPACE`, Langfuse keys, optional `LLM_PROVIDER_FOR_<NODE>` overrides.

### `backend/app/database.py`

SQLAlchemy engine, session factory, `get_db` FastAPI dependency.

### `backend/app/models.py`

Tables: `runs`, `files`, `file_summaries`, `intake_bundles`, `blueprints`. Storage shape only — no business logic.

### `backend/app/schemas.py`

Pydantic types from spec §6–§8: `Source`, `WorkflowRecord`, `PainSignal`, `LeadRow`, `FileSummary`, `SummaryReview`, `RevisionRequest`, `IntakeBundle`, `Contradiction`, `Bottleneck`, `Opportunity`, `BlueprintClaim`, `Blueprint`, `FinalReview`, `DiagnosticState`, `ExtractionError`, `FileRef`.

### `backend/app/state.py`

`DiagnosticState` TypedDict for the LangGraph parent workflow.

### `backend/app/parsers/`

Deterministic file parsers. **No LLM calls here.** One module per file type:

- `pdf.py` — PyMuPDF, locator `{ page, span_start, span_end }`
- `docx.py` — python-docx, locator `{ paragraph_index, span_start, span_end }`
- `md.py`, `txt.py` — builtin, locator `{ line_start, line_end }`
- `vtt.py` — webvtt-py, locator `{ line_start, line_end, ts_start, ts_end }`
- `srt.py` — srt, locator `{ line_start, line_end, ts_start, ts_end }`
- `csv.py` — pandas, locator `{ row_index }`
- `xlsx.py` — openpyxl/pandas, locator `{ sheet, row_index }`
- `mbox.py` — mailbox, locator `{ message_id, header_or_body }`
- `json.py` — locator `{ pointer }` (RFC 6901)

Each parser exports `parse(path) -> ParsedFile` and `excerpt(parsed_file, locator) -> str` for the citation side panel.

### `backend/app/llm.py`

Provider abstraction. Single interface:

```python
generate_json(prompt_name: str, prompt: str, schema: type[BaseModel]) -> tuple[dict, metadata]
```

Provider clients: `OllamaLLMProvider`, `OpenAILLMProvider`, `GroqLLMProvider`, `OpenAICompatibleLLMProvider`. **No `MockLLMProvider`.** Strict JSON parsing with one retry; returns provider metadata (provider, model, prompt_name, token estimate, parsed_json status, retry_count, latency_ms).

### `backend/app/agents/per_file/`

One **tool-routed ReAct agent** per file-type family. Each runs a think → act → observe loop over a fixed toolbelt and emits `FileSummary` with citations:

- `pdf.py`
- `docx.py`
- `markdown.py` (covers `md.py` and `txt.py`)
- `transcript.py` (covers VTT and SRT)
- `table.py` (covers CSV and XLSX)
- `mbox.py`
- `json.py`

Shared modules:

- `agents/per_file/_brief.py` — the extraction brief shared across agents.
- `agents/per_file/_react_loop.py` — the ReAct iteration loop and iteration-cap enforcement.
- `agents/per_file/_router.py` — tool router with Pydantic-validated tool calls.
- `agents/per_file/_tools/` — `search_text`, `read_segment`, `extract_workflow`, `extract_pain_signal`, `extract_lead_row`, `cite_locator`, `finalize_summary`.

### `backend/app/agents/lead/`

The lead agent's four phases as separate node modules:

- `review_summaries.py` — emits `SummaryReview` with `revision_requests`. Bounded one redo cycle.
- `synthesis.py` — `cross_file_synthesis`, emits `IntakeBundle`.
- `workflow_map.py`, `bottleneck_detect.py`, `roi_score.py`, `fastest_win_select.py`, `solution_blueprint.py` — diagnostic chain.
- `self_review.py` — `self_review_final`, emits `FinalReview`. Bounded one revision.

### `backend/app/graph.py`

Defines the LangGraph parent workflow and wires the multi-agent pipeline: `fan_out_files` → per-file agents → `review_summaries` (with redo edge back to flagged agents) → `cross_file_synthesis` → diagnostic chain (`workflow_map` → `bottleneck_detect` → `roi_score` → `fastest_win_select` → `solution_blueprint`) → `self_review_final` (with revision edge back to `solution_blueprint`) → emit.

Constructs the compiled graph with a **Redis-backed checkpointer** (`langgraph-checkpoint-redis`) using `REDIS_URL` from config. Every node boundary writes a checkpoint keyed by `run_id` — this is what makes the reviewer redo loop, self-review revision loop, and per-file failure isolation cheap and correct.

### `backend/app/checkpointer.py`

Builds the Redis-backed LangGraph checkpointer from settings. Verifies Redis connectivity at startup. Refuses to start the backend if Redis is unavailable (no in-memory fallback in v1).

### `backend/app/observability.py`

Langfuse wrapper. Starts the parent trace, opens nested spans for every node and LLM call. Local trace persistence is intentionally not used.

### `backend/app/services/`

Application orchestration:

- `files.py` — uploads, blob storage, parser invocation.
- `runs.py` — run lifecycle, graph invocation, persistence.

API endpoints stay thin; orchestration lives here.

### `backend/app/main.py`

FastAPI app. Routes:

- `GET /health`
- `POST /api/files`
- `POST /api/runs`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/blueprint`
- `POST /api/files/{file_id}/excerpt` — locator supplied as JSON body (`{"locator": {...}}`) because locators are structured objects.

### `Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml`

Demo-only deployment artifact. `docker-compose.yml` at the repo root orchestrates `postgres`, `redis`, `ollama` (with model preloaded), `backend`, `frontend` — each with a health check. `make demo` brings the stack up, waits for backend health, uploads `/samples/` and runs with `auto_approve=true`.

Out of scope: Kubernetes manifests, EC2 deployment, CI/CD pipelines.

### `backend/tests/`

Test layers (all against real Ollama, `temperature=0`):

- `tests/fixtures/` — fixture input files for parsers and agents.
- `test_parsers.py` — deterministic.
- `test_per_file_agents.py` — schema + citation invariants.
- `test_review_summaries.py` — crafted-gap fixtures.
- `test_diagnostic_chain.py` — fixture `IntakeBundle` → blueprint invariants.
- `test_self_review.py` — broken-citation fixtures.
- `test_graph_e2e.py` — full pipeline against `/samples`.
- `test_observability.py` — span tree shape.

## Frontend Files

### `frontend/package.json`

Dependencies and scripts (`dev`, `build`, `lint`).

### `frontend/lib/api.ts`

Typed API client matching the backend's endpoints.

### `frontend/app/layout.tsx`

Global app shell.

### `frontend/app/upload/page.tsx`

Drag-and-drop upload view with per-file parse status.

### `frontend/app/runs/[run_id]/page.tsx`

Run progress view. Streams per-file-agent completion, review pass/fail, revision triggers, diagnostic chain progress.

### `frontend/app/runs/[run_id]/blueprint/page.tsx`

Blueprint view with clickable citations.

### `frontend/app/runs/[run_id]/review/page.tsx`

Human-in-the-loop checkpoint UI. Renders the reviewer agent's `SummaryReview` with Approve / Edit / Skip actions before any redo cycle is triggered.


### `frontend/components/CitationPanel.tsx`

Side panel that renders the source file at a cited locator. Knows how to display PDF page + span, transcript line + timestamp, CSV row, MBOX message body, etc.

### `frontend/app/styles.css`

Dashboard styling. Not a marketing page.

### `frontend/next.config.ts`, `frontend/tsconfig.json`

Standard Next.js + TypeScript config.

## Documentation Files

### `docs/requirements.md`

Product requirements aligned to the redesign spec.

### `docs/architecture.md`

Technical architecture: parent workflow, per-file agents, lead-agent phases, provider design, observability.

### `docs/build_from_scratch_plan.md`

Step-by-step build sequence.

### `docs/project_glossary.md`

Project-specific vocabulary.

### `docs/demo_script.md`

Five-minute meeting talk track.

### `docs/company_research_report.md`

Why the project maps to Agent Integrator's business.

### `docs/superpowers/specs/2026-05-23-real-files-diagnostic-redesign-design.md`

**Authoritative spec.** When any other doc disagrees with the spec, the spec wins.
