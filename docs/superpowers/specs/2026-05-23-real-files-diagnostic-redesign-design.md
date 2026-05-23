# Real-Files Diagnostic Redesign — Design Spec

**Date:** 2026-05-23
**Status:** Approved for planning
**Supersedes:** the "paste messy intake text" framing in `docs/requirements.md` and `docs/architecture.md`

## 1. Why redesign

The original project goals assumed a human pastes messy text into a textarea. The redesigned goal is stronger and more honest: the agent must accept the kinds of real files an ops team actually has, read them, reason over them, and propose solutions with verifiable citations. The system must work end-to-end on real data with real LLMs — no mock providers, no fixture-canned demo paths.

## 2. Goals

1. **Ingest real ops files.** PDF/DOCX/MD SOPs, `.txt`/`.vtt`/`.srt` transcripts, CSV/XLSX spreadsheets, CSV/MBOX/JSON email & CRM exports. Uploads only — no paste box.
2. **Parallel per-file agents, one lead agent.** Each uploaded file gets one LLM agent that emits a typed `FileSummary` with citations. A single lead agent reasons across all summaries.
3. **Two real review steps.** Lead reviews per-file summaries (with bounded redo of flagged per-file agents), then self-reviews its final blueprint (with bounded revision).
4. **Cite everything.** Every workflow, bottleneck, opportunity, and blueprint claim points back to a specific page/line/row/message in a specific file.
5. **Real LLMs end-to-end.** Supported providers: `ollama`, `openai`, `groq`, `openai_compatible`. No `mock` provider. CI runs against a local Ollama model with `temperature=0`; demos run against hosted models.
6. **Works on real data.** The repo ships realistic sample input files in `/samples` and a `make demo` target that runs the full pipeline against them with no manual steps.

## 3. Non-goals (v1)

- Agent-run graph (lead_intake → coverage_classifier → … → approved_action_executor).
- Human approval gate UI and approval persistence.
- Real outbound actions (email send, CRM write, SMS).
- Vector database / RAG retrieval. (Per-file agents read parsed files directly. Hybrid retrieval may return in v2.)
- File upload by URL, cloud-drive sync, OCR for scanned PDFs.

These remain in the broader project vision but are out of scope for this redesign.

## 4. Architecture

This is a **multi-agent system**. Each agent has a narrow job, a typed input contract, and a typed output contract. One agent's output is the next agent's input. The LangGraph parent workflow is the wiring diagram — nothing more, nothing less.

Roles:

- **Per-file agents** (one per uploaded file, run in parallel) — each consumes one parsed file and emits a `FileSummary`. Summarizers, not deciders.
- **Reviewer agent** (lead role, phase 1) — consumes the set of `FileSummary` objects and emits a `SummaryReview` with `revision_requests`. Drives the bounded redo loop.
- **Synthesizer agent** (lead role, phase 2) — consumes reviewed `FileSummary` objects and emits an `IntakeBundle`, preserving contradictions.
- **Diagnostic-chain agents** (lead role, phase 3) — five sequential agents (`workflow_map`, `bottleneck_detect`, `roi_score`, `fastest_win_select`, `solution_blueprint`). Each consumes the bundle plus the previous agent's typed output and emits the next typed artifact.
- **Self-review agent** (lead role, phase 4) — consumes the blueprint and emits a `FinalReview`, driving the bounded revision loop.

Handoff contract: every agent's input and output is a Pydantic model declared in §6–§8. Agents never read each other's prompts or internals; they only see typed artifacts in `DiagnosticState`. This is what makes the system testable agent-by-agent and traceable claim-by-claim.

```
┌────────────┐   ┌──────────────────────────────────────────────┐
│ Upload UI  │──▶│            Parent LangGraph                  │
│ (Next.js)  │   │                                              │
└────────────┘   │  fan_out_files                               │
                 │      │   │   │   │      (parallel)           │
                 │      ▼   ▼   ▼   ▼                           │
                 │   per-file LLM agents                        │
                 │   (pdf_agent · transcript_agent ·            │
                 │    table_agent · mbox_agent · md_agent)      │
                 │      │                                       │
                 │      ▼                                       │
                 │   review_summaries  ──▶ redo (≤1 cycle)      │
                 │      │                                       │
                 │      ▼                                       │
                 │   cross_file_synthesis                       │
                 │      ▼                                       │
                 │   workflow_map → bottleneck_detect           │
                 │     → roi_score → fastest_win_select         │
                 │     → solution_blueprint                     │
                 │      ▼                                       │
                 │   self_review_final  ──▶ revise (≤1 pass)    │
                 └──────┬───────────────────────────────────────┘
                        ▼
                 Blueprint + UI (cites sources)
```

Five layers, each independently testable: **parsers** (deterministic), **per-file agents** (LLM, typed summaries), **lead-agent review + synthesis** (LLM), **lead-agent diagnostic chain** (LLM, cites sources), **lead-agent self-review** (LLM).

## 5. File ingestion + parsing

Parsers are deterministic and contain no LLM calls. Each parser returns the file content with locators preserved so downstream citations can point back precisely.

| File type | Parser | Locator payload |
|---|---|---|
| PDF | PyMuPDF (`fitz`) | `{ page, span_start, span_end }` |
| DOCX | `python-docx` | `{ paragraph_index, span_start, span_end }` |
| MD / TXT | builtin | `{ line_start, line_end }` |
| Transcript `.vtt` | `webvtt-py` | `{ line_start, line_end, ts_start, ts_end }` |
| Transcript `.srt` | `srt` | `{ line_start, line_end, ts_start, ts_end }` |
| CSV | `pandas` | `{ row_index, sheet: null }` |
| XLSX | `openpyxl`/`pandas` | `{ sheet, row_index }` |
| MBOX | `mailbox` | `{ message_id, header_or_body, span_start?, span_end? }` |
| JSON (CRM export) | builtin + schema infer | `{ pointer }` (RFC 6901 JSON Pointer) |

Corrupt or unparseable files do not abort the run. They emit an `ExtractionError` and the run continues with the remaining files.

## 6. Per-file agents

Each file gets one LLM agent. Agents run in parallel via LangGraph fan-out. Every agent receives:

- the parsed content of one file, with locator anchors,
- the same **extraction brief** so summaries across agents are comparable,
- a **tool router** giving it a fixed toolbelt (see §6.1),
- the typed `FileSummary` schema it must return.

### 6.1 Tool-routed ReAct loop

Per-file agents are not single-shot prompt-and-parse. They run a **ReAct loop** over a fixed toolbelt — think → call tool → observe → continue — capped at a small maximum iteration budget (default 6). This is the explicit place this project exercises ReAct and tool routing.

Toolbelt (deterministic, no LLM inside the tools themselves):

| Tool | Purpose | Inputs | Outputs |
|---|---|---|---|
| `search_text(query, top_k=3)` | Localized retrieval within this file. Token-overlap + substring scoring across `ParsedSegment` list. | `query: str`, `top_k: int` | `list[{segment_index, score, text, locator}]` |
| `read_segment(segment_index)` | Read one segment in full. | `segment_index: int` | `{text, locator}` |
| `extract_workflow(name, ...)` | Add a typed `WorkflowRecord` to the agent's working state. | typed payload | confirmation |
| `extract_pain_signal(category, text, ...)` | Add a typed `PainSignal`. | typed payload | confirmation |
| `extract_lead_row(raw, normalized, ...)` | Add a typed `LeadRow` (table/MBOX/JSON files only). | typed payload | confirmation |
| `cite_locator(locator)` | Validate a locator against the parser and return the excerpt at that locator — used by the agent to verify a citation before attaching it. | `locator: dict` | `{text, valid: bool}` |
| `finalize_summary()` | End the loop. The agent commits a `FileSummary` built from the working state. | — | the `FileSummary` |

The router enforces:

- one tool call per iteration,
- typed argument validation (Pydantic) at the router boundary,
- a hard iteration cap; if reached without `finalize_summary`, the loop emits the partial state with an explicit caveat,
- citation validity — `cite_locator` is the only path that produces a `Source`, so no `Source` can exist that didn't roundtrip through the parser.

Tracing: each tool call is a child span of the per-file agent's span in Langfuse (§10), with tool name, arguments, and result.

### 6.2 In-file retrieval (RAG, light)

`search_text` is the project's v1 retrieval primitive. It is intentionally **localized to a single file** (the file the agent owns) — there is no cross-file vector store in v1. The score is `(token_overlap * 0.7) + (substring_match * 0.3)`, computed deterministically over the segment list.

Why this is the right shape for v1:

- The agent's job is to summarize one file thoroughly, not search the whole corpus.
- Citations stay anchored to specific segments without needing a separate embedding store.
- Cross-file evidence is the synthesizer's job (§7.2), reasoning over already-extracted `FileSummary` objects.

Hybrid vector RAG across files is the v2 extension (§16.2 company knowledge source).

```python
class Source(BaseModel):
    file_id: str
    file_name: str
    type: Literal["pdf","docx","md","txt","transcript_vtt","transcript_srt",
                  "csv","xlsx","mbox","json"]
    locator: dict  # type-specific payload, always present

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
    lead_rows: list[LeadRow]       # populated only for csv/xlsx/mbox/json
    open_questions: list[str]
    agent_notes: str
```

Per-file agents are summarizers, not deciders. They never score opportunities or pick winners.

## 7. Lead agent

The lead agent owns all reasoning across files. It runs four phases as separate LangGraph nodes so each phase is independently traceable.

### 7.0 Human-in-the-loop checkpoint (UI gate)

Before the lead agent's redo cycle triggers, the UI presents the `SummaryReview` to the operator. The operator can:

- **Approve** — proceed with the proposed redo requests as-is,
- **Edit** — modify the list (drop requests, add new ones, change reason text), then proceed,
- **Skip** — proceed without any redo.

A non-interactive `auto-approve` mode skips the gate (used by `make demo` and headless eval runs). The gate is the v1 manifestation of human-in-the-loop in this project — outbound-action approvals are v2 (§16.1).

The same gate pattern is available (but optional, default off) at the `self_review_final` decision point.

### 7.1 `review_summaries` (input review)

Reads every `FileSummary` and emits a `SummaryReview`:

```python
class RevisionRequest(BaseModel):
    file_id: str
    reason: Literal["missing_info","contradiction","weak_citation",
                    "ignored_open_question","schema_drift"]
    detail: str

class SummaryReview(BaseModel):
    revision_requests: list[RevisionRequest]
    notes: str
```

If `revision_requests` is non-empty, the parent graph re-runs only the flagged per-file agents with the original file plus the reason+detail, then re-enters `review_summaries`. **Bounded: at most one redo cycle**, then the graph proceeds even if issues remain (unresolved issues are recorded and surfaced in the final blueprint's caveats).

### 7.2 `cross_file_synthesis`

Reconciles per-file outputs into a single `IntakeBundle`. The lead agent — not deterministic code — does this so contradictions can be reasoned about rather than silently merged.

```python
class IntakeBundle(BaseModel):
    workflows: list[WorkflowRecord]
    pain_signals: list[PainSignal]
    lead_rows: list[LeadRow]
    contradictions: list[Contradiction]   # both citations preserved
    file_index: list[Source]
    extraction_errors: list[ExtractionError]

class Contradiction(BaseModel):
    topic: str
    statements: list[dict]  # each: {claim, sources}
```

### 7.3 Diagnostic chain (five nodes)

`workflow_map → bottleneck_detect → roi_score → fastest_win_select → solution_blueprint`. Each node consumes `IntakeBundle` plus prior nodes' outputs and writes back into `DiagnosticState`. Every record produced (each Bottleneck, each Opportunity, each Blueprint claim) carries a non-empty `sources: list[Source]`.

```python
class Bottleneck(BaseModel):
    workflow_name: str
    signal: Literal["delay","error","repetition","handoff",
                    "missing_data","visibility_gap","revenue_leak"]
    impact: str
    sources: list[Source]

class Opportunity(BaseModel):
    workflow_name: str
    bottleneck_refs: list[int]   # indices into DiagnosticState.bottlenecks
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
    opportunity_ref: int   # index into DiagnosticState.opportunities
    summary: BlueprintClaim
    steps: list[BlueprintClaim]
    required_systems: list[BlueprintClaim]
    success_metrics: list[BlueprintClaim]
    risks: list[BlueprintClaim]
```

### 7.4 `self_review_final` (output review)

Reads its own blueprint and runs an audit. Checks:

1. **Citation existence:** every `sources[i]` resolves to a `file_index` entry.
2. **Citation reachability:** every locator is valid against the parsed file (deterministic post-check, not the LLM).
3. **No silent drops:** every `open_question` from the summary review either appears in `Blueprint.risks` or in `caveats`.
4. **Internal consistency:** the selected opportunity has the highest (or tied-highest) `roi_score`; the blueprint addresses at least one bottleneck listed under the selected opportunity.

The lead agent emits a `FinalReview` describing pass/fail per check. On fail, the graph re-runs `solution_blueprint` once with the failure detail in context, then forcibly emits.

```python
class FinalReview(BaseModel):
    citation_existence_ok: bool
    citation_reachability_ok: bool
    no_silent_drops_ok: bool
    internal_consistency_ok: bool
    detail: str
    revised_once: bool
```

## 8. Shared graph state

```python
class FileRef(BaseModel):
    file_id: str
    file_name: str
    mime_type: str
    parsed_path: str       # on-disk parsed-content artifact
    parser_status: Literal["ok","error"]

class ExtractionError(BaseModel):
    file_id: str
    stage: Literal["parse","agent","review"]
    message: str

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

## 9. LLM provider design

Supported providers: `ollama`, `openai`, `groq`, `openai_compatible`. No mock provider exists in code.

```python
result, metadata = llm.generate_json(
    prompt_name="per_file_pdf_agent",
    prompt=prompt,
    schema=FileSummary,
)
```

`metadata` records provider, model, prompt_name, token estimate, parsed-JSON status, retry count, latency. Sent to Langfuse on every call.

**Per-node provider override (optional, off by default):** environment variables of the form `LLM_PROVIDER_FOR_<NODE>` may redirect a specific node to a different provider/model — useful for running heavy lead-agent nodes on a strong hosted model while per-file agents stay on local Ollama. Off by default to keep the architecture simple.

## 10. Observability

One Langfuse trace per `run_id`. Nested spans:

- `parent_graph`
  - `parse_files` (one child span per file)
  - `per_file_agents` (one child span per file; each contains its LLM generation)
  - `review_summaries`
  - `redo_round` (only when triggered)
  - `cross_file_synthesis`
  - `diagnostic_chain` (one child span per chain node)
  - `self_review_final`
  - `blueprint_revision` (only when triggered)

Every LLM call records prompt name, provider, model, token usage, latency, parsed-JSON success. Local trace persistence is intentionally not used.

## 11. Persistence

PostgreSQL stores durable records:

- `runs(run_id, status, created_at, langfuse_trace_id)`
- `files(file_id, run_id, file_name, mime_type, parsed_path, parser_status)`
- `file_summaries(file_id, json)`
- `intake_bundles(run_id, json)`
- `blueprints(run_id, json)`

SQLite is the acceptable local fallback for development relational storage.

### 11.1 Redis — LangGraph checkpointer

Redis is **required for v1** as the LangGraph checkpointer. It is not an optional resume mechanism; it is what makes the multi-agent loops work cleanly.

Why this multi-agent design needs a checkpointer:

- **Bounded redo loop (`review_summaries`).** When the reviewer agent flags a subset of per-file agents for redo, the parent graph must resume from the `file_summaries` state and re-run only the flagged agents — without re-parsing files or re-running successful agents. The checkpointer is what makes that resume cheap and correct.
- **Bounded revision loop (`self_review_final`).** When self-review fails, the graph re-runs only `solution_blueprint` with the failure detail in context. Everything upstream (workflows, bottlenecks, opportunities, selection) is preserved from the prior checkpoint.
- **Per-file-agent failure isolation.** A single per-file agent that errors out can be retried independently from a checkpoint taken at fan-out time, without re-running its siblings.
- **Long runs survive disconnects.** Large file sets take tens of seconds. The UI polls run state from Redis-backed checkpoints; a browser refresh never loses progress.
- **One source of truth for "where is this run?"** Every poll for run progress reads the same checkpointed state every node writes to. No drift between UI status and graph state.

Configuration:

```bash
REDIS_URL=redis://localhost:6379/0
LANGGRAPH_CHECKPOINTER=redis
LANGGRAPH_CHECKPOINT_NAMESPACE=ops_diagnostic
```

Checkpoint identity: `(run_id)`. Each run is one Redis namespace.

Checkpoint cadence: at every node boundary (LangGraph default). The reviewer and self-review loops rely on this — they read the prior checkpoint, decide, and either continue or branch.

Failure mode if Redis is unavailable: backend refuses to start a new run and surfaces a clear error. There is no in-memory fallback for the checkpointer in v1 — a partial multi-agent run without checkpoints would silently lose retry semantics.

## 12. UI

Single-page Next.js dashboard, three views:

1. **Upload** — drag-and-drop, shows per-file parse status live.
2. **Run progress** — streams per-file-agent completion (with their tool-call timeline), review pass/fail, the human-in-the-loop redo checkpoint, and revision triggers. Includes a link out to the Langfuse trace for the run.
3. **Blueprint** — selected opportunity, blueprint sections; every claim has clickable citations that open a side panel showing the source file at the cited locator (PDF page, transcript line+timestamp, CSV row, etc.).

## 13. Testing strategy

No mock provider. CI runs against a local Ollama model (`llama3.1:8b` or smaller) with `temperature=0`. Tests assert **invariants**, not exact wording.

| Unit | Test approach |
|---|---|
| Parsers | fixture files → assert anchored output structurally |
| Per-file agent | fixture file → agent run → assert `FileSummary` schema validates, every cited locator exists in the parsed file |
| `review_summaries` | crafted `FileSummary` with deliberate gap → assert a matching `RevisionRequest` is emitted |
| Diagnostic chain | fixture `IntakeBundle` → assert blueprint schema, ≥1 citation per claim, selected opportunity is top-3 ROI |
| `self_review_final` | blueprint with a deliberately broken citation → assert revision triggered |
| Full graph | real Ollama + sample files in `/samples` → end-to-end run, blueprint emitted with citations, Langfuse trace ID recorded |

Langfuse-recorded traces double as regression artifacts. Tests time out generously; CI uses `temperature=0` to keep variance low but does not assert exact strings.

## 14. Demo story

`make demo` from a clean clone:

1. `docker-compose up -d` brings up Postgres, Redis, Ollama (with the configured model preloaded), backend, and frontend.
2. The script waits for backend `/health` to return 200.
3. The script uploads every file under `/samples/` and starts a run with `auto_approve=true` so the human-in-the-loop gate is skipped.
4. It opens the browser to the blueprint view with citations rendered.

Measurement is end-to-end via Langfuse: every node, every LLM call, every tool call, every redo/revision decision shows up in one nested trace per run (§10). There is no separate offline eval harness in v1.

No mocks. No "if demo: short-circuit". The pipeline that produces the demo output is the same pipeline a real user gets.

### 14.1 Docker layout

- `backend/Dockerfile` — multi-stage Python image; runs `uvicorn app.main:app`.
- `frontend/Dockerfile` — Node + Next.js, production build.
- `docker-compose.yml` at the repo root with services: `postgres`, `redis`, `ollama`, `backend`, `frontend`. Volumes for Postgres data, Redis data, Ollama models, and uploaded blobs. A health-check on each service so `make demo` waits for readiness deterministically.
- `docker-compose.dev.yml` (optional override) — mounts source for hot-reload during development.

Out of scope for v1: Kubernetes manifests, EC2 deployment, CI/CD pipelines. The Docker compose flow is the only supported deployment artifact.

## 15. Build order

1. Parser layer + locator tests (no LLM yet).
2. LLM provider layer for `ollama`, `openai`, `groq`, `openai_compatible`.
3. Per-file agent (single file type first: PDF), end-to-end against Ollama.
4. Remaining per-file agents (transcript, CSV/XLSX, MBOX, JSON, MD/TXT).
5. `review_summaries` + bounded redo.
6. `cross_file_synthesis` + `IntakeBundle`.
7. Diagnostic chain (five nodes).
8. `self_review_final` + bounded revision.
9. Persistence + Langfuse wiring.
10. Next.js UI (upload, progress, blueprint with citations).
11. `/samples` realistic dataset and `make demo`.

## 16. Deferred to v2

### 16.1 Carry-overs from the original scope

- Approval-gated agent run (lead_intake → … → approved_action_executor).
- Real outbound actions behind feature flags.
- OCR for scanned PDFs.
- Cloud-drive sync ingest.

### 16.2 Company knowledge source (long-lived memory)

A per-company knowledge store that the lead agent consults during synthesis and writes to after every run. The point is to make the agent get better the more it works with a given company — not just smarter in one session.

What it stores:
- **Past run blueprints and their outcomes** — which proposed automations were implemented, which paid off, which stalled, and why.
- **Success patterns** — recurring shapes of "this kind of bottleneck in this kind of workflow tends to be solved by this kind of automation, at this kind of ROI."
- **Company-specific facts that don't belong in any single uploaded file** — house style, preferred vendors, integration constraints, regulatory boundaries, named systems and what they actually do.
- **Lead-agent self-notes** — open questions from prior runs, hypotheses to revisit, things that turned out to be wrong.

How it's used:
- In `cross_file_synthesis`, the lead agent retrieves relevant prior entries to reconcile current findings against company history (e.g. "this 'CRM' is actually their custom Airtable, not Salesforce — same as last run").
- In `roi_score` and `fastest_win_select`, prior success/failure outcomes calibrate the scoring (e.g. "automations of this type have shipped fast here; weight effort lower").
- In `solution_blueprint`, past wins serve as concrete reference solutions the agent can cite alongside file evidence.

How it's updated:
- A `post_run_learning` node writes back: which findings were novel, which corroborated prior knowledge, which contradicted it. Contradictions surface for human review before being committed to long-term memory.
- Knowledge entries carry provenance (run_id, source files, date) so the agent can reason about staleness.

Implementation sketch:
- Hybrid store: a small relational table for typed facts and outcomes, plus a vector index over free-text success-story narratives. Retrieval is per-node, scoped to the current company.
- This is the first v2 piece that justifies introducing retrieval into the architecture — by then there is enough learned content to make retrieval worthwhile.

### 16.3 Multimodal inputs

Extend the file-ingestion layer beyond text:

- **Audio.** `.mp3`, `.wav`, `.m4a` discovery-call and meeting recordings. Transcribed via a real ASR provider (Whisper local or hosted), then handed to a transcript per-file agent. Locators include `{ ts_start, ts_end, speaker }`.
- **Images.** Screenshots of dashboards, CRM views, error states, whiteboard photos. A vision-capable per-file agent describes the operational signal in the image (e.g. "Salesforce pipeline shows 47 leads stuck in 'Awaiting Documents' > 30 days") and emits typed `PainSignal` / `WorkflowRecord` records cited back to `{ image_id, bbox }` when the model returns regions.
- **Video** (stretch). Treated as audio + sampled frames; out of scope until audio + image agents are stable.

The per-file-agent contract (one LLM agent → typed `FileSummary` with citations) carries over unchanged. Only the parser and locator schema grow.

### 16.4 Continuous learning loop

The knowledge source in §16.2 is a static record by default. The continuous-learning extension makes it adaptive:

- **Outcome capture.** A lightweight feedback UI lets the operator record what actually happened after a blueprint shipped (built / not built, time saved, surprises). Feedback is structured, not free-text-only.
- **Pattern mining.** A scheduled job re-reads accumulated outcomes and updates the company's success-pattern entries (e.g. "for this client, document-collection automations have a 3× higher ROI hit-rate than reporting automations").
- **Prompt evolution.** Per-node prompts can be augmented with retrieved patterns at runtime ("recent successes here look like X"). Prompts themselves are not rewritten by the system; humans still own prompt source.
- **Cross-company carry (opt-in).** Anonymized patterns can be shared across companies behind an explicit flag. Off by default; never on without consent.

This is what turns the agent from "smart consultant in a session" into "operator that remembers."
