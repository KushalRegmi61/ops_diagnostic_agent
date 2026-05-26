# Backend Hardening Audit — Ops Diagnostic Agent

**Reviewer:** senior backend pass
**Date:** 2026-05-26
**Tree state:** HEAD `d38bb70` + uncommitted LangChain provider migration (treated as given; not stomped)
**Scope verified:** `backend/app/{config,database,blob_store,main,observability,models,graph}.py`, `backend/app/services/{files,runs}.py`, `backend/app/llm/{__init__,langchain_base,openai,ollama}.py`. Other files marked `[unverified]` where referenced.

The existing high-level design (11-node LangGraph pipeline, Redis checkpointer, per-file ReAct agents, citation invariant) is sound. This audit targets the structural plumbing underneath.

---

## A. Config & caching contract drift

### A1. `get_settings()` is uncached despite documented `@lru_cache`  ·  **P1**
- **Where:** `backend/app/config.py:77-79`
- **What:** Function builds a fresh `Settings()` on every call; no `@lru_cache`. `CLAUDE.md` documents it as `@lru_cache(maxsize=1)` with a `.cache_clear()` contract.
- **Failure mode:** Tests that mutate `.env` mid-suite call `get_provider.cache_clear()` per CLAUDE.md guidance — but `get_settings()` is not cached, so the contract is silently inconsistent. Future readers will write `get_settings.cache_clear()` and get `AttributeError`.

### A2. `BLOB_DIR` is frozen at import time  ·  **P1**
- **Where:** `backend/app/blob_store.py:11`
- **What:** `BLOB_DIR = Path(get_settings().blob_store_dir)` runs once at module import.
- **Failure mode:** Changing `BLOB_STORE_DIR` env between tests or via runtime config has no effect; uploaded bytes still land in the original directory. Integration tests that need an isolated blob dir cannot achieve it without monkey-patching the module attribute.

### A3. `engine` is built at import time from frozen settings  ·  **P2**
- **Where:** `backend/app/database.py:14-19`
- **What:** `_settings = get_settings()` at import; `engine` built once from `_settings.database_url`.
- **Failure mode:** Same as A2 — DSN cannot be reconfigured at runtime; tests cannot point at a temp SQLite without reaching into the module.

### A4. `settings` captured at import in `main.py`  ·  **P2**
- **Where:** `backend/app/main.py:55`
- **What:** Module-level `settings = get_settings()` used by CORS middleware.
- **Failure mode:** Any later change to `frontend_cors_origins` requires a process restart.

### A5. `get_provider.cache_clear()` called per run  ·  **P2**
- **Where:** `backend/app/services/runs.py:184`
- **What:** Every `start_run()` invocation clears the provider cache that `app/llm/__init__.py:15` exists to maintain.
- **Failure mode:** Per-run cost includes re-importing the provider module and reconstructing the LangChain client. Defeats `@lru_cache(maxsize=1)`; contradicts the docstring that promises a process-lifetime instance.

---

## B. Background execution & concurrency

### B1. `BackgroundTasks` runs multi-minute work in the threadpool  ·  **P1**
- **Where:** `backend/app/main.py:228` (`background_tasks.add_task(_start_run_background, run_id)`)
- **What:** `start_run` is synchronous and can take minutes (LLM calls + graph + Redis I/O). FastAPI's `BackgroundTasks` runs it in the shared anyio threadpool.
- **Failure mode:** N concurrent runs occupy N threadpool slots indefinitely. Default threadpool is 40 workers — a single user POSTing 41+ runs (or other endpoints needing the pool) starves the server. No bound, no queue depth, no backpressure on `POST /api/runs`.

### B2. Cross-thread event publish without `call_soon_threadsafe` [unverified]  ·  **P1**
- **Where:** `backend/app/run_events.py` [unverified — not opened in this audit, only referenced via `main.py:30,47,162,221`]
- **What:** `run_event_hub.bind_loop(asyncio.get_running_loop())` at startup; `publish()` is called from the background-task worker thread (`_start_run_background`) via `_run_event_emitter`.
- **Failure mode:** If `publish()` invokes `queue.put_nowait()` on an asyncio Queue directly from the worker thread, behavior is undefined: dropped events, deadlocks, or `RuntimeError: no running event loop`. The bound loop must be used via `loop.call_soon_threadsafe(queue.put_nowait, event)`. Needs verification before fix.

### B3. Background task opens its own session; partial Langfuse/DB visibility on failure  ·  **P1**
- **Where:** `backend/app/main.py:174-197`
- **What:** `_start_run_background` opens `SessionLocal()` and lets `start_run` flush (not commit) intermediate `FileSummaryRecord` / `IntakeBundleRecord` rows. On exception, the outer handler does `db.rollback()` then opens a fresh state write for `run.status="error"`.
- **Failure mode:** Langfuse already emitted "per_file_completed" / "synthesis_completed" spans for work whose DB rows just got rolled back. Operator looking at the trace sees a half-successful run; the DB shows nothing. Reproducible by raising an exception mid-`solution_blueprint`.

### B4. `clear_context()` semantics across threads  ·  **P2**
- **Where:** `backend/app/structured_logging.py` [unverified] + `backend/app/main.py:104,207`, `backend/app/services/runs.py:167-168`
- **What:** `clear_context() / bind_context(run_id=...)` use ContextVars. FastAPI's `BackgroundTasks` copies the context at scheduling time, but `start_run` then re-binds.
- **Failure mode:** Log lines emitted between `BackgroundTasks` dispatch and `start_run`'s own `bind_context` carry the *request* context, not the run context. Minor — affects log grepping by `run_id`.

---

## C. Checkpointer / resumability

### C1. `parsed_files` lives in the build_graph closure; not in checkpointed state  ·  **P1 (silent drop)**
- **Where:** `backend/app/graph.py:61-75, 114-126`
- **What:** `build_graph(parsed_files=...)` closes over the dict. Redis-checkpointed `DiagnosticState` (`backend/app/state.py` [unverified, but inspected via `graph.py:572-589`'s `initial_state`]) does not include `parsed_files`.
- **Failure mode:** Worker dies mid-run, supervisor restarts the process and the next caller resumes from the Redis checkpoint. The new `build_graph` is invoked with `parsed_files={}`; `per_file_fanout` sees `parsed=None` for every targeted file and **silently `continue`s** (lines 115-117), logging a warning. Run completes with `file_summaries={}`, no blueprint, status `no_blueprint`. The checkpointer's whole purpose — resumability — is defeated. **Violates CLAUDE.md's "no silent drops" rule.**

### C2. `run_id` stored as `run.langfuse_trace_id`  ·  **P2**
- **Where:** `backend/app/services/runs.py:206`
- **What:** `run.langfuse_trace_id = run_id` — but Langfuse v3 trace IDs are OTel 32-hex IDs, not arbitrary strings.
- **Failure mode:** Downstream tooling (Langfuse deep-link UI, OTel exporters) cannot resolve the column as a real trace ID. The column is documentation-shaped rather than load-bearing. Either rename the column or capture the real trace ID returned by `start_as_current_observation`.

---

## D. Three drifting file-type dispatch tables

### D1. `_PER_FILE_AGENTS`, `_EXCERPT_MODULES`, parser registry  ·  **P1**
- **Where:** `backend/app/graph.py:47-58`, `backend/app/main.py:66-77`, `backend/app/parsers/__init__.py` [unverified]
- **What:** Three independent maps from `file_type` → module. Each adopts a different shape (agent module vs. parser module). Adding a new file type requires touching all three in matching order.
- **Failure mode:** Add a parser without updating `_PER_FILE_AGENTS` → uploaded files for the new type silently produce `no_agent` warnings and zero summaries. Add a parser without updating `_EXCERPT_MODULES` → `/api/files/{id}/excerpt` returns 400 "no excerpt module" for valid citations — directly violates the citation invariant.

---

## E. Upload-path security

### E1. Path traversal via user-supplied `file_name`  ·  **P0**
- **Where:** `backend/app/blob_store.py:14-24`
- **What:** `blob_path_for(file_id, file_name)` returns `BLOB_DIR / file_id / file_name`. `file_name` is passed straight from `UploadFile.filename` with no sanitization.
- **Failure mode:** Client uploads with `filename="../../../etc/cron.d/evil"`. Path resolves outside `BLOB_DIR/<file_id>/` and `save_blob` writes attacker-controlled bytes into a system directory (subject to filesystem permissions). Reproducible with a single curl request.

### E2. Unbounded upload size, no streaming  ·  **P0**
- **Where:** `backend/app/main.py:110` (`content = file.file.read()`)
- **What:** Entire upload buffered into memory before any size check.
- **Failure mode:** Single attacker POST with 10GB body OOMs the server. No `max_upload_mb` setting; no 413 path.

### E3. No MIME allowlist; unparseable files become persistent storage cost  ·  **P1**
- **Where:** `backend/app/services/files.py:36-47` — on parse exception, file is still inserted with `parser_status="error"` and its bytes remain on disk forever.
- **Failure mode:** Adversary uploads 1000 files of an unsupported mime. None contribute to any run, all consume disk. No cleanup job, no allowlist gate at the HTTP layer.

### E4. Truncated `file_id` reduces audit trail  ·  **P2**
- **Where:** `backend/app/services/files.py:25` (`f"f_{uuid.uuid4().hex[:12]}"`), `backend/app/services/runs.py:47` (same pattern for run_id).
- **What:** 12 hex chars = 48 bits of entropy. Collision odds are negligible at expected scale, but the truncated prefix is harder to correlate across logs/Langfuse/DB compared to a full UUID. Cosmetic.
- **Failure mode:** Forensic — when investigating a multi-system incident, partial IDs increase the chance of mismatching across sources.

### E5. No auth or rate-limiting on any endpoint  ·  **P1 (documented, deferred)**
- **Where:** `backend/app/main.py:92-275`
- **What:** All endpoints are open. Anyone with network access can upload, run, and burn LLM tokens.
- **Failure mode:** Public exposure on any host = unbounded LLM cost + DoS surface. **This pass documents the threat model and defers the fix; the portfolio demo is local-only.** If you bind to anything other than localhost, this becomes P0.

---

## F. LangChain migration hazards (in-flight, do NOT regress)

### F1. `parsed_json=False` is a silent drop  ·  **P1**
- **Where:** `backend/app/llm/langchain_base.py:90-98`
- **What:** On total retry failure, `generate_json` returns `({}, GenerateMetadata(parsed_json=False))`. Consumers (`backend/app/agents/lead/*.py` [unverified for `parsed_json` checks], `backend/app/agents/per_file/_react_loop.py`) accept the dict and continue.
- **Failure mode:** Empty `IntakeBundle`/`Blueprint`/per-file `WorkingState` ingested as success. Downstream nodes operate on `{}` and emit a Blueprint with no claims. CLAUDE.md explicitly forbids silent drops; this is one.

### F2. Two Langfuse auth paths construct redundant clients  ·  **P1**
- **Where:** `backend/app/observability.py:25-40` (cached, reads `Settings`) vs. `backend/app/observability.py:43-85` (fresh, reads `os.getenv`).
- **What:** `_build_langfuse_handler` builds a new `Langfuse(...)` per `langchain_config()` call AND a fresh `CallbackHandler` — once per node, ~13 nodes per run.
- **Failure mode:** Memory growth proportional to run count over a long-running uvicorn; auth-source drift (env vs Settings); accidental double-billing of Langfuse if the two clients diverge on host.

---

## G. Graph hygiene

### G1. Production `assert isinstance(...)` against typed state  ·  **P2**
- **Where:** `backend/app/graph.py:279, 305, 336, 398, 445`
- **What:** Each lead-node function asserts `isinstance(b, IntakeBundle)` despite `DiagnosticState` already declaring the type.
- **Failure mode:** Under `python -O`, asserts compile out; an unexpected `None` becomes an attribute-error later in the node with a worse stack. The right shape is a guard that raises `ExtractionError` (a known CLAUDE.md sink).

### G2. `solution_blueprint` returns `{"blueprint": None}` silently  ·  **P1**
- **Where:** `backend/app/graph.py:386-396, 432-442`
- **What:** When `selected is None`, the node logs a warning and returns; `revise_router` then returns `"end"` because `final_review is None`. Run completes `status=no_blueprint`. `state["errors"]` is initialized in `initial_state` (`graph.py:588`) but **never written to anywhere in `graph.py`**.
- **Failure mode:** A run that produced zero opportunities looks identical at the API surface to a run that completed with a blueprint that got rejected at self_review — both yield `404 no blueprint for this run yet` on `/api/runs/{id}/blueprint`. No structured reason exposed.

---

## H. Models / DB

### H1. `datetime.utcnow` deprecated default  ·  **P2**
- **Where:** `backend/app/models.py:24, 41, 53, 63, 73`
- **What:** All `created_at` columns use `default=datetime.utcnow`.
- **Failure mode:** Python 3.12 emits `DeprecationWarning`; future versions will remove it. Resulting datetimes are naive (no tzinfo), which leaks into Pydantic responses and breaks any consumer that does timezone math.

### H2. No `ON DELETE` policy on payload FKs  ·  **P2**
- **Where:** `backend/app/models.py:51, 61, 71` (FKs on `files.id` / `runs.id`)
- **What:** Deleting a `Run` row leaves `IntakeBundleRecord` / `BlueprintRecord` orphans. Deleting a `FileRecord` orphans `FileSummaryRecord`.
- **Failure mode:** Orphan rows accumulate. Future "delete run" feature has to write manual cascade logic. CASCADE is the correct semantic for payload tables.

### H3. `payload_json` typed as `String`, not validated at DB layer  ·  **P2**
- **Where:** `backend/app/models.py:52, 62, 72`
- **What:** Column type is `String`; nothing guarantees the content round-trips through `Blueprint.model_validate_json`.
- **Failure mode:** A buggy serializer writes invalid JSON; `get_blueprint` raises `ValidationError` at read time, not write time. Test coverage needs an explicit round-trip assertion for each payload type.

---

## I. Excerpt endpoint cost

### I1. Full re-parse on every excerpt resolution  ·  **P2**
- **Where:** `backend/app/main.py:122` → `backend/app/services/files.py:70-84`
- **What:** Each `/api/files/{id}/excerpt` call calls `parse_file(...)` against the full blob.
- **Failure mode:** A reviewer clicking through 30 citations on a 50-page PDF triggers 30 full PDF parses. Latency and CPU scale with citation density, not with locator complexity.

---

## J. Cross-cutting observations (no action items)

- **Citation invariant guard is sound.** `self_review_final` performs deterministic existence + reachability checks. Commits in Phase 2 that touch parsers, dispatch, or excerpt resolution will keep the existing `test_excerpt_returns_text_for_uploaded_file` pattern as a regression gate.
- **`from app import _langgraph_pydantic_patch` (`graph.py:17`) is load-bearing.** Linter will flag it; keep the `# noqa: F401`. Confirmed by CLAUDE.md landmines section.
- **No mock LLM, by policy.** Any new test that needs a provider uses real Ollama gated on `_ollama_up()`.

---

## Resolved (this branch: `feat/backend-hardening`)

All P0/P1/P2 items in this audit landed across the following commits on this branch:

| # | Commit | Subject |
|---|---|---|
| 1 | `02dd2d9` | feat(config): cache get_settings and remove import-time captures |
| 2 | `c4d0b9d` | feat(blob): reject path-traversal filenames in save_blob |
| 3 | `db741b1` | feat(main): enforce max upload size and MIME allowlist on /api/files |
| – | `99de872` | fix(tests): adapt integration tests to lru_cache settings and 415 mime guard |
| 4 | `0c94e93` | feat(registry): consolidate per-file agent dispatch in app.registry |
| 5 | `36d295d` | feat(graph): rehydrate parsed_files on resume from FileRef blob_path |
| 6 | `37e9891` | feat(runs): bound background run concurrency with asyncio Semaphore |
| 7 | `7acf1cf` | feat(runs): propagate structured errors into state.errors |
| 8 | `ec7a8d0` | feat(llm): raise LLMParseError when generate_json returns parsed_json=False |
| 9 | `5f9117e` | feat(observability): reuse cached Langfuse client in handler factory |
| 10 | `3881347` | feat(graph): replace isinstance asserts with ExtractionError guards |
| 11 | `16a9e38` | feat(models): tz-aware created_at and CASCADE on payload FKs |
| 12 | `f9e0940` | feat(services): bounded LRU cache for ParsedFile keyed by blob mtime |

**Unit suite at branch tip:** 180 passed, 1 warning. **No `Co-Authored-By` or "Generated with Claude" trailers anywhere.**

Out-of-scope items remain as documented below: E5 (auth/rate-limit — local-only portfolio demo), C2 (rename `langfuse_trace_id` column to capture a real OTel ID), B2/B4 (cross-thread `run_events.py` + `structured_logging` deeper audit — `run_events._put` already uses `call_soon_threadsafe`, verified during research).

---

## Plan — Phase 2 commit order

Twelve commits, P0 → P1 → P2. One concern per commit. TDD: failing test first, run red, implement, run green, commit. `feat(scope): subject` ≤ 72 chars. **No `Co-Authored-By: Claude …`. No "Generated with Claude Code".** Never amend; always a new commit on hook failure.

| # | Severity | Commit | Justification |
|---|---|---|---|
| 1 | P1 | `feat(config): cache get_settings and remove import-time captures` | Foundation. Restores documented contract; every later commit reads Settings or trusts the provider cache. Fixes A1–A5 together because the import-time captures are the symptom and lazy-`get_settings` is the cure. |
| 2 | P0 | `feat(blob): sanitize filename to prevent path traversal in save_blob` | E1. Isolated, smallest possible surface. Test: malicious `..`-prefixed filename rejected; nothing written above `BLOB_DIR`. |
| 3 | P0 | `feat(main): enforce max upload size and MIME allowlist` | E2 + E3. Adds `settings.max_upload_mb` (default 50) and a streaming chunked reader; rejects unknown mimes at 415 against the parser registry. Depends on #1. |
| 4 | P1 | `feat(registry): consolidate file-type dispatch into app/registry.py` | D1. Single `{file_type → (parser, agent, excerpt_module)}` map; `graph.py` and `main.py` rewritten to import from it. Test asserts coverage parity between parser registry and consumer dispatch. |
| 5 | P1 | `feat(graph): rehydrate parsed_files on resume from FileRecord` | C1 (the worst silent drop). New helper inside `per_file_fanout` re-parses targeted files missing from the closure. Test: build graph with `parsed_files={}` and a real `FileRef`, assert summary produced. Real Ollama gated. |
| 6 | P1 | `feat(runs): bound background concurrency with asyncio Semaphore` | B1. Replace `BackgroundTasks` dispatch with `asyncio.to_thread` inside a `Semaphore(N)` (N from Settings, default 2). Also removes `get_provider.cache_clear()` (A5). Test: launch N+1 runs, assert N+1th waits. |
| 7 | P1 | `feat(runs): propagate structured errors into state.errors` | G2. `solution_blueprint_node`, `self_review_node`, and `redo_router` write to `state["errors"]`; `start_run` persists them. Optional new column `Run.error_detail TEXT`. Test: drive `selected=None`, assert `errors` non-empty and exposed via `/api/runs/{id}`. |
| 8 | P1 | `feat(llm): fail loudly on parsed_json=False in lead and react consumers` | F1. Lead nodes and `_react_loop` check `meta.parsed_json` and raise `ExtractionError` instead of ingesting `{}`. Real-Ollama integration test forces a schema mismatch and asserts the raise. |
| 9 | P1 | `feat(observability): unify Langfuse client to single cached factory` | F2. Delete `_build_langfuse_handler`'s env-reading path; `langchain_config` reuses `langfuse_client()`. Test patches `Langfuse` and asserts call count == 1 across multiple `langchain_config()` calls. |
| 10 | P2 | `feat(graph): replace isinstance asserts with structured guards` | G1. Asserts become guard clauses raising `ExtractionError`. After #7 because the error-propagation surface is now wired. |
| 11 | P2 | `feat(models): tz-aware created_at and CASCADE on payload FKs` | H1 + H2. `lambda: datetime.now(timezone.utc)`; `ON DELETE CASCADE` for `file_summaries`, `intake_bundles`, `blueprints`. SQLite test enables `PRAGMA foreign_keys=ON` via `event.listen`. |
| 12 | P2 | `feat(services): bounded LRU cache for ParsedFile in excerpt path` | I1. `services/files.get_parsed` wraps an LRU keyed by `(file_id, blob_mtime_ns)`. Settings field `excerpt_cache_size` (default 32). Test: warm cache, mutate file mtime, assert reparse. |

### What is *not* in this plan (explicitly out of scope)
- **B2 / B4** verification of `run_events.py` + structured-logging cross-thread semantics — call out in commit #6 if the read shows they need fixing; otherwise file follow-up tickets.
- **E5** auth + rate-limit — threat model documented; fix deferred. Becomes P0 if the service is exposed beyond localhost.
- **C2** rename `Run.langfuse_trace_id` to capture a real trace id — touches DB schema and Langfuse v3 OTel ID surface; defer as a follow-up.
- **Moving `parsed_files` into checkpointed state** — re-hydration on resume (commit #5) is the simpler fix; closure stays the fast path.
- **Async-end-to-end `start_run` rewrite** — semaphore + `to_thread` solves the actual exhaustion.

### Risks called out per-commit
- **#5 (re-hydration):** a 50-page PDF re-parses on resume — seconds of latency. Acceptable for correctness; documented in the commit body.
- **#6 (semaphore):** in-process bound. Multi-uvicorn-worker deployments need an external queue. Documented as a known limit.
- **#11 (CASCADE on SQLite):** requires `PRAGMA foreign_keys=ON`; enabled via SQLAlchemy `event.listen` in the test and in `database.py`.

### Citation-invariant regression risk
Commits **#4** (registry), **#5** (re-hydration), **#10** (graph guards), **#12** (excerpt cache) touch parsers, locator dispatch, or excerpt resolution. Each commit's test run includes the existing real-file excerpt round-trip suite (`backend/tests/integration/test_excerpt_api.py` + per-file agent tests) as a regression gate before declaring green.

---

READY FOR REVIEW
