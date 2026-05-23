# Build From Scratch Plan

This is the top-level roadmap. The redesign spec is large enough that one implementation plan would be unusable, so the work is decomposed into **three sequential sub-project plans**, each producing working software on its own.

Authoritative spec: [`superpowers/specs/2026-05-23-real-files-diagnostic-redesign-design.md`](superpowers/specs/2026-05-23-real-files-diagnostic-redesign-design.md).

## Guiding Rules

- Start each plan with one working vertical slice, then expand.
- Do not stub LLM calls. Use local Ollama (`temperature=0`) for every step that needs reasoning.
- Every plan ends with the same green test suite.

## Plan 1 — Backend Foundation + Parsers + LLM Providers

**Detailed plan:** [`superpowers/plans/2026-05-23-backend-foundation-plan.md`](superpowers/plans/2026-05-23-backend-foundation-plan.md) (29 tasks).

**Scope:**

1. **Backend shell** — FastAPI, typed settings, health endpoint.
2. **Database + storage** — SQLAlchemy engine, `runs` and `files` tables (storage shape for agent outputs comes in Plan 2), on-disk blob store.
3. **Pydantic schemas for Plan 1** — `Source`, typed locator union, `ParsedFile`, `ParsedSegment`, `ExtractionError`, `FileRef`. Agent-output types (`FileSummary`, `IntakeBundle`, `Blueprint`, etc.) come in Plan 2.
4. **File ingestion API** — `POST /api/files` (multipart upload), `POST /api/files/{file_id}/excerpt` returning text at a structured locator. (Note: the locator is a JSON body, not a URL path parameter, because locators are structured objects.)
5. **Parser layer** — deterministic parsers for 10 file types (PDF/DOCX/MD/TXT/VTT/SRT/CSV/XLSX/MBOX/JSON), each exporting `parse()` and `excerpt()`, each with the locator schema from spec §5.
6. **LLM provider layer** — `generate_json(prompt_name, prompt, schema)` over four providers: `ollama`, `openai`, `groq`, `openai_compatible`. **No mock provider.** Ollama tested with real local model calls at `temperature=0`. Hosted providers have skip-gated smoke tests.

**Exit criteria:** every test green (or skip-gated on missing env), `make dev` runs, you can upload a file via curl and round-trip a locator excerpt.

## Plan 2 — Multi-Agent Graph + Redis Checkpointer + Langfuse

**Detailed plan:** TBD — written after Plan 1 lands so types/endpoints are locked.

**Scope:**

7. **Per-file agents (tool-routed ReAct)** — one LLM agent per file-type family (PDF, DOCX, transcript, table, MBOX, markdown, JSON). Each runs a ReAct loop over a fixed toolbelt (`search_text`, `read_segment`, `extract_workflow`, `extract_pain_signal`, `extract_lead_row`, `cite_locator`, `finalize_summary`) dispatched by an explicit router with iteration cap and Pydantic-validated tool args. Each emits `FileSummary` with citations. Tested against real Ollama with schema + citation-reachability invariants and tool-call ordering invariants.
8. **Parent LangGraph workflow** — `fan_out_files` → parallel per-file agents → merge into `file_summaries` in `DiagnosticState`.
9. **Redis-backed checkpointer** — `langgraph-checkpoint-redis` keyed by `run_id`. Required, no in-memory fallback. Includes kill/resume validation.
10. **Reviewer agent + human-in-the-loop UI gate** — reads all `FileSummary` objects, emits `SummaryReview`. The UI presents the review as an approve/edit/skip checkpoint before any redo triggers (`auto_approve=true` skips for demo and headless eval runs). Triggers bounded redo cycle (max one round) of flagged per-file agents.
11. **Synthesizer agent** — reconciles into `IntakeBundle`, preserving contradictions with both citations.
12. **Diagnostic chain** — five sequential lead-role agents: `workflow_map` → `bottleneck_detect` → `roi_score` → `fastest_win_select` → `solution_blueprint`. Every record carries `sources`.
13. **Self-review agent** — audits citation existence, citation reachability (deterministic post-check), no silent drops, internal consistency. Bounded one revision pass.
14. **Persistence for agent outputs** — `file_summaries`, `intake_bundles`, `blueprints` tables.
15. **Langfuse observability** — one nested trace per run with the span tree from spec §10.
16. **API surface** — `POST /api/runs`, `GET /api/runs/{run_id}`, `GET /api/runs/{run_id}/blueprint`.

**Exit criteria:** end-to-end backend run produces a cited blueprint, kill/resume validates checkpoints, Langfuse trace shows the full nested tree.

## Plan 3 — Frontend + Sample Dataset + Demo

**Detailed plan:** TBD — written after Plan 2 lands.

**Scope:**

17. **Frontend shell + Upload view** — Next.js app, drag-and-drop upload with per-file parse-status indicator.
18. **Run Progress view** — streams per-file-agent completion (with their tool-call timeline), review status, the human-in-the-loop redo checkpoint, revision triggers, diagnostic chain progress.
19. **Blueprint view with citation side panel** — every claim has a clickable citation that opens the source file at the cited locator (PDF page, transcript line + timestamp, CSV row, MBOX message).
20. **Sample dataset** — realistic anonymized files in `/samples` covering all supported types.
21. **Dockerized demo** — `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml` with `postgres`, `redis`, `ollama`, `backend`, `frontend` services. `make demo` brings the stack up, waits for backend health, uploads `/samples/`, runs with `auto_approve=true`, opens the browser.

**Exit criteria:** from a clean clone, `make demo` succeeds end-to-end with one command. Every run produces a nested Langfuse trace.

**Out of scope:** Kubernetes, EC2, cloud deploys, CI/CD pipelines, offline eval harness — honestly carried by CareGene evidence per [`resume_concept_map.md`](resume_concept_map.md).

## Cross-Plan Validation Activities

These happen continuously, not as one-time gates:

### Run real demo modes

Same pipeline against each provider:

```bash
# Ollama (default for CI and dev)
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.1:8b

# OpenAI
LLM_PROVIDER=openai
OPENAI_MODEL=gpt-4.1-mini

# Groq
LLM_PROVIDER=groq
GROQ_MODEL=llama-3.3-70b-versatile

# OpenAI-compatible
LLM_PROVIDER=openai_compatible
OPENAI_COMPATIBLE_BASE_URL=...
OPENAI_COMPATIBLE_MODEL=...

# Langfuse (required from Plan 2 onward)
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_BASE_URL=https://us.cloud.langfuse.com
```

### Test layers (cumulative across plans)

1. Parser unit tests — deterministic, fixture files. (Plan 1)
2. LLM provider tests — real Ollama, skip-gated hosted smoke tests. (Plan 1)
3. Per-file agent integration tests — real Ollama, schema + citation invariants. (Plan 2)
4. Reviewer agent tests — crafted-gap fixtures. (Plan 2)
5. Diagnostic chain tests — fixture `IntakeBundle` → blueprint invariants. (Plan 2)
6. Self-review tests — broken-citation fixtures. (Plan 2)
7. Full-graph integration test against `/samples` — real Ollama, real Redis, real Langfuse. (Plan 2 / Plan 3)
8. Frontend smoke tests — upload, progress, blueprint views. (Plan 3)

## Meeting Narrative

Once all three plans land, you should be able to explain (per [`demo_script.md`](demo_script.md)):

- why uploading real files (not pasted text) is the right framing,
- how parallel per-file agents + a lead agent map to ops-diagnostic reasoning,
- how citations make the blueprint trustworthy,
- how Redis + LangGraph checkpoints make the bounded review/revision loops correct and cheap,
- how Langfuse makes the whole run debuggable,
- and how this maps to Agent Integrator's client delivery model.

## v2 (deferred)

Per spec §16:

- Company knowledge source with continuous learning.
- Multimodal inputs (audio via ASR, images via vision-capable agent).
- Approval-gated agent run + real outbound actions behind feature flags.
- OCR for scanned PDFs.
- Cloud-drive sync ingest.
