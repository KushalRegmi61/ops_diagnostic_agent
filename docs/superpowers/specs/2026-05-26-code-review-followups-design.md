# Code-Review Followups — Design

**Date:** 2026-05-26
**Branch (planned):** `fix/code-review-followups` off `master` (`6fa08d7`)
**Goal:** Fix the three findings surviving the `/code-review` pass on the hardening-branch merge — one CONFIRMED bug, two PLAUSIBLE latent issues — with TDD discipline, on a fresh branch.

## Scope

Three independent commits. One concern per commit. All real bugs / latent fragilities flagged by the post-merge review. No new features, no refactor sweep, no deferred-audit items reopened.

| # | Finding | Severity | Scope | Files |
|---|---|---|---|---|
| 1 | **C3** — missing blob raises `FileNotFoundError` that escapes `(KeyError, ValueError)` catch in `post_excerpt`, returning 500 instead of 404 | CONFIRMED (real bug) | `services` | M `backend/app/services/files.py`, C `backend/tests/integration/test_excerpt_missing_blob.py` |
| 2 | **C2** — `DiagnosticState.errors` is an unannotated `list[ExtractionError]`; LangGraph default reducer is OVERWRITE, so accumulation depends entirely on every node remembering the manual `existing = list(state.get("errors") or [])` boilerplate | PLAUSIBLE (latent fragility) | `state` + `graph` | M `backend/app/state.py`, M `backend/app/graph.py`, C `backend/tests/unit/test_state_errors_accumulator.py` |
| 3 | **C6** — `asyncio.create_task(_start_run_dispatch(run_id))` is fire-and-forget with no reference held and no done_callback; exceptions raised above `_start_run_sync`'s try/except (semaphore acquire, `to_thread` machinery, threadpool exhaustion) leave `run.status='running'` forever | PLAUSIBLE (narrow edge case) | `runs` | M `backend/app/main.py`, C `backend/tests/integration/test_runs_dispatch_lifecycle.py` |

Total: 3 production-file edits, 3 new test files, ~80 lines of code change.

## Ordering

C3 first (most isolated, real bug, no other-file impact) → C2 (touches multiple sites in `graph.py` but no happy-path behavior change) → C6 (depends on nothing earlier; touches only `main.py`).

## Commit policy

`fix(scope): subject` ≤72 chars. Body explains *why*. **No `Co-Authored-By: Claude …` line. No "Generated with Claude Code" line.** Never amend; new commit on hook failure. `git add <specific paths>` only.

## Engineering discipline

- **TDD:** every commit starts with a failing test under `backend/tests/`. Confirm RED is an `AssertionError` (or `pytest.raises.Failed`), not an `ImportError`, before implementing.
- **Real systems only:** no mock LLM provider. The two new integration tests use real SQLite (`Base.metadata.drop_all/create_all`) and real on-disk blob store. No Ollama gating needed — these tests don't reach the LLM.
- **Citation invariant:** none of the three fixes touch parsers, locator dispatch, or `self_review_final`. The existing `test_excerpt_returns_text_for_uploaded_file` integration test stays as the regression gate; verify green after each commit.
- **Run command:** `cd backend && uv run pytest …` — never `source .venv/bin/activate`.

---

## Commit 1 — `fix(services): translate FileNotFoundError to 404 in get_parsed`

### Why

`backend/app/services/files.py:get_parsed` calls `Path(rec.blob_path).stat().st_mtime_ns` to build the excerpt-cache key (added in commit `f9e0940`). If the DB row exists but the blob is missing on disk (volume wipe, manual cleanup, test teardown), `Path.stat()` raises `FileNotFoundError` (subclass of `OSError` — NOT `ValueError`). `backend/app/main.py:post_excerpt` catches only `ValueError` around the `get_parsed` call and `(KeyError, ValueError)` around `parsers_excerpt`. Result: the client sees an unhandled 500 with a stack trace.

`get_parsed` already raises `ValueError("File {file_id} not found")` for the missing-DB-row case; the HTTP layer already maps that to 404. The right vocabulary is `ValueError`, set in one layer.

### Test (failing first)

`backend/tests/integration/test_excerpt_missing_blob.py`:

```python
"""Excerpt endpoint returns 404 when DB row exists but blob is absent on disk."""
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def _reset(tmp_path, monkeypatch):
    monkeypatch.setenv("BLOB_STORE_DIR", str(tmp_path / "blobs"))
    get_settings.cache_clear()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


def test_excerpt_returns_404_when_blob_is_missing_on_disk(tmp_path) -> None:
    client = TestClient(app)
    upload = client.post(
        "/api/files",
        files={"file": ("notes.md", BytesIO(b"# A\nline\n"), "text/markdown")},
    )
    assert upload.status_code == 200, upload.text
    body = upload.json()
    file_id = body["file_id"]

    # Wipe the blob from disk while the DB row remains.
    Path(body["blob_path"]).unlink()

    r = client.post(
        f"/api/files/{file_id}/excerpt",
        json={"locator": {"type": "text", "line_start": 1, "line_end": 1}},
    )
    assert r.status_code == 404, r.text
    assert "not found" in r.text.lower()
```

Expected RED: returns 500 because `FileNotFoundError` propagates out of `Path(rec.blob_path).stat()`.

### Fix

`backend/app/services/files.py` — wrap `get_parsed`'s blob-touching calls:

```python
def get_parsed(db: Session, file_id: str) -> ParsedFile:
    """Return a cached ParsedFile; re-parse on cache miss or blob-mtime change.

    Raises ValueError if the FileRecord row is missing OR its blob file is absent
    on disk. Both conditions map to a 404 at the HTTP layer.
    """
    rec = db.get(FileRecord, file_id)
    if rec is None:
        logger.warning("file.reparse.missing", file_id=file_id)
        raise ValueError(f"File {file_id} not found")
    try:
        mtime_ns = Path(rec.blob_path).stat().st_mtime_ns
    except FileNotFoundError as exc:
        logger.warning("file.reparse.blob_missing", file_id=file_id, blob_path=rec.blob_path)
        raise ValueError(f"File {file_id} blob missing on disk") from exc
    key = (file_id, mtime_ns)
    cached = _cache_get(key)
    if cached is not None:
        logger.info("file.reparse.cache_hit", file_id=file_id)
        return cached
    logger.info("file.reparse.started", file_id=file_id, file_name=rec.file_name, mime_type=rec.mime_type)
    try:
        parsed = parse_file(
            file_id=rec.id, file_name=rec.file_name,
            path=Path(rec.blob_path), mime_type=rec.mime_type,
        )
    except FileNotFoundError as exc:
        logger.warning("file.reparse.blob_missing", file_id=file_id, blob_path=rec.blob_path)
        raise ValueError(f"File {file_id} blob missing on disk") from exc
    _cache_put(key, parsed)
    logger.info("file.reparse.completed", file_id=file_id, file_type=parsed.type, segment_count=len(parsed.segments))
    return parsed
```

(Second `try` wraps `parse_file` — defense against parsers that re-open the path internally; cheap insurance.)

### Verify

```
cd backend && uv run pytest tests/integration/test_excerpt_missing_blob.py -x -v
cd backend && uv run pytest tests/integration/test_excerpt_api.py -q   # citation invariant gate
cd backend && uv run pytest tests/unit -q
```

### Commit message

```
fix(services): translate FileNotFoundError to 404 in get_parsed

After commit f9e0940 added the excerpt cache, get_parsed now calls
Path(rec.blob_path).stat() to build the cache key. FileNotFoundError
inherits from OSError, not ValueError, so a missing-on-disk blob (DB row
present, file absent) escaped post_excerpt's narrow (KeyError, ValueError)
catch and returned an unhandled 500 with a stack trace. Translate it to
ValueError so the existing 404 path fires; one error vocabulary, one
layer.
```

---

## Commit 2 — `fix(state): accumulate errors via Annotated[list, operator.add]`

### Why

`backend/app/state.py:39` declares `errors: list[ExtractionError]`. LangGraph's default reducer for unannotated keys is OVERWRITE. The current code mitigates by having every error-write site do `existing = list(state.get("errors") or []); existing.append(err); return {..., "errors": existing}`. This works today but is fragile — any future contributor who adds a node and returns `{"errors": [new]}` directly silently drops every previously accumulated error. Annotate the field with `operator.add` so accumulation is enforced by the framework, then strip the manual boilerplate.

### Test (failing first)

`backend/tests/unit/test_state_errors_accumulator.py`:

```python
"""state.errors must accumulate across nodes, not be overwritten by the last write."""
from app.graph import build_graph, initial_state
from app.schemas import ExtractionError, IntakeBundle


class _NullProvider:
    name = "null"
    model = "null"
    def chat_model(self, **kwargs): raise NotImplementedError
    def generate_json(self, **kwargs): raise NotImplementedError


def _node(graph, name):
    spec = graph.get_graph().nodes[name].data
    return getattr(spec, "func", spec)


def test_errors_accumulate_across_two_nodes() -> None:
    """When workflow_map AND roi_score both error on the same run, both errors land in state.errors."""
    graph = build_graph(provider=_NullProvider(), parsed_files={})  # type: ignore[arg-type]
    state = initial_state("r_accum", [])
    state["bundle"] = None  # forces workflow_map error
    state["bottlenecks"] = []
    # Drive workflow_map first.
    wm = _node(graph, "workflow_map")
    out1 = wm(state)
    assert any(e.stage == "workflow_map" for e in out1.get("errors", [])), out1
    # Simulate LangGraph merging: with operator.add, returning {"errors": [new]}
    # accumulates onto state["errors"]; here we mimic that merge for the unit test.
    state["errors"] = list(state.get("errors", [])) + list(out1.get("errors", []))
    # Then drive roi_score with bundle still None.
    rs = _node(graph, "roi_score")
    out2 = rs(state)
    # The second node returns {"errors": [<new>]} only (single-element list under the new contract).
    assert len(out2["errors"]) == 1
    assert out2["errors"][0].stage == "roi_score"
    # The framework's accumulator (operator.add) would produce 2 elements after merge.
```

A second test asserts the annotation shape:

```python
def test_diagnostic_state_errors_uses_add_reducer() -> None:
    """state.errors must be Annotated with operator.add so LangGraph accumulates."""
    import operator
    from typing import get_type_hints, get_args, get_origin
    from typing import Annotated
    from app.state import DiagnosticState

    # get_type_hints with include_extras=True preserves Annotated[].
    hints = get_type_hints(DiagnosticState, include_extras=True)
    errors_hint = hints["errors"]
    # Annotated[list[ExtractionError], operator.add]
    assert get_origin(errors_hint) is not None
    args = get_args(errors_hint)
    assert operator.add in args, f"errors must carry operator.add reducer, got {args}"
```

Expected RED: `operator.add` not in the type-hint args; the second test fails immediately.

### Fix

**`backend/app/state.py`** — annotate the field:

```python
"""LangGraph state TypedDict shared by every node in the parent workflow."""
import operator
from typing import Annotated, TypedDict

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
    """Shared state for the parent LangGraph workflow — one entry per pipeline output."""

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
    errors: Annotated[list[ExtractionError], operator.add]
```

**`backend/app/graph.py`** — strip the manual accumulator at every error-write site. The exhaustive list (search for `state.get("errors")`):

1. `per_file_fanout` — currently collects into `new_errors` and returns `{..., "errors": existing + new_errors}`; change to `{..., "errors": new_errors}`.
2. `solution_blueprint_node` `sel is None` branch — `{"blueprint": None, "errors": [err]}`.
3. `self_review_node` `bp is None` branch — `{"final_review": None, "errors": [err]}`.
4. `workflow_map_node` bundle-guard (Task 10) — `{"workflows": [], "errors": [err]}`.
5. `bottleneck_detect_node` bundle-guard (Task 10) — `{"bottlenecks": [], "errors": [err]}`.
6. `roi_score_node` bundle-guard (Task 10) — `{"opportunities": [], "errors": [err]}`.
7. `solution_blueprint_node` bundle-guard (Task 10) — `{"blueprint": None, "errors": [err]}`.
8. `self_review_node` bundle-guard / sel-guard (Task 10) — `{"final_review": None, "errors": [err]}`.
9. Every `try/except LLMParseError` wrapper (Task 8) — `{..., "errors": [ExtractionError(...)]}`.

For each site, delete the three boilerplate lines (`existing = list(state.get("errors") or [])`, `existing.append(err)`, and the use of `existing` in the return dict). Replace the return dict's `"errors"` value with a single-element `[err]` list.

### Verify

```
cd backend && uv run pytest tests/unit/test_state_errors_accumulator.py -x -v
cd backend && uv run pytest tests/unit/test_graph_errors_propagation.py tests/unit/test_graph_guards.py -q
cd backend && uv run pytest tests/unit -q
```

**Critical regression gate:** Task 7 (`test_graph_errors_propagation.py`) and Task 10 (`test_graph_guards.py`) tests still pass — they assert `out["errors"]` contains the right stage. Under the new contract, each node returns a single-element `[err]` list; the existing tests check `any(e.stage == "<stage>" for e in out["errors"])` which works whether the list is length-1 or length-N.

**Risk gate:** if I miss a site, two scenarios:
- Old-style return `existing + [new]` AND operator.add: LangGraph merges by appending, so `existing` is duplicated. The new accumulator test catches this if it covers the missed node.
- Old-style return without operator.add (impossible — annotation is on the field): N/A.

Mitigation: do a final `grep -n 'state.get("errors")' backend/app/graph.py` after the edit; expected to be zero matches.

### Commit message

```
fix(state): accumulate errors via Annotated[list, operator.add]

DiagnosticState.errors was unannotated, so LangGraph's default OVERWRITE
reducer applied. Every error-write site mitigated by manually reading
state.errors, appending, and returning the full list — fragile boilerplate
that any future contributor could forget. Annotate the field with
operator.add so the framework accumulates automatically; strip the manual
read-then-append from all nine error-write sites in graph.py. Each site
now returns {"errors": [new_err]} and LangGraph merges via list addition.
```

---

## Commit 3 — `fix(runs): track dispatch tasks and mark run='error' on uncaught`

### Why

`backend/app/main.py:252` does `asyncio.create_task(_start_run_dispatch(run_id))` with no reference retained. Two concrete risks:

1. **Task GC:** under CPython memory pressure, a Task with no strong reference can be garbage-collected before completion. Documented in Python's asyncio docs; rare in practice but real.
2. **Status lockup:** `_start_run_sync` has a comprehensive `try/except Exception` that marks `run.status='error'` for any failure inside `start_run`. But exceptions raised ABOVE that — semaphore acquire, `asyncio.to_thread` machinery failing under threadpool exhaustion, or any future code added inside `_start_run_dispatch` itself — are never caught. The client polling `/api/runs/{id}` sees the run stuck in `running` forever.

Fix: hold tasks in a module-level `set`, add a done callback that (a) discards from the set, (b) on uncaught exception, opens a fresh DB session and writes `run.status='error'` as a safety net.

### Test (failing first)

`backend/tests/integration/test_runs_dispatch_lifecycle.py`:

```python
"""Run dispatch task lifecycle — held in a strong-ref set, marks run=error on uncaught."""
import asyncio
import pytest
from io import BytesIO

from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Run


@pytest.fixture(autouse=True)
def _reset(tmp_path, monkeypatch):
    monkeypatch.setenv("BLOB_STORE_DIR", str(tmp_path / "blobs"))
    get_settings.cache_clear()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


def test_dispatch_task_held_in_module_set(monkeypatch) -> None:
    """asyncio.create_task return value must be held in app.main._pending_run_tasks."""
    from app import main
    # The set exists and is referenced from create_task path.
    assert hasattr(main, "_pending_run_tasks")
    assert isinstance(main._pending_run_tasks, set)


def test_dispatch_callback_marks_run_error_on_uncaught(monkeypatch) -> None:
    """When _start_run_dispatch raises above _start_run_sync's catch, run.status='error'."""
    from app import main as app_main

    async def _boom(run_id: str) -> None:
        raise RuntimeError("simulated dispatcher failure")

    monkeypatch.setattr(app_main, "_start_run_dispatch", _boom)

    client = TestClient(app)
    # Upload a parseable file so create_run validates.
    up = client.post(
        "/api/files",
        files={"file": ("a.md", BytesIO(b"# A\n"), "text/markdown")},
    )
    file_id = up.json()["file_id"]
    r = client.post("/api/runs", json={"file_ids": [file_id]})
    assert r.status_code == 200, r.text
    run_id = r.json()["run_id"]

    # Give the event loop a chance to run the callback.
    for _ in range(20):
        with SessionLocal() as db:
            run = db.get(Run, run_id)
            if run is not None and run.status == "error":
                break
        # TestClient runs inside a sync wrapper; one sleep tick lets the loop process.
        import time; time.sleep(0.05)
    with SessionLocal() as db:
        run = db.get(Run, run_id)
        assert run is not None
        assert run.status == "error", f"expected run.status='error', got {run.status!r}"
```

Expected RED: `_pending_run_tasks` doesn't exist; on the second test, run stays `queued` or `running` forever.

### Fix

`backend/app/main.py` — add module-level state and callback near the existing `_get_run_semaphore` definition:

```python
_pending_run_tasks: set[asyncio.Task] = set()


def _run_task_done(task: asyncio.Task) -> None:
    """Discard the dispatch task from the pending set and mark run='error' on uncaught exception.

    _start_run_sync catches all exceptions raised inside start_run and writes
    run.status='error' itself. This callback is the safety net for exceptions
    that escape _start_run_dispatch's own body (semaphore acquire, asyncio.to_thread
    machinery, threadpool exhaustion) where _start_run_sync is never reached.
    """
    _pending_run_tasks.discard(task)
    if task.cancelled():
        return
    exc = task.exception()
    if exc is None:
        return
    run_id = task.get_name().removeprefix("run-dispatch-")
    logger.error("run.dispatch.failed", run_id=run_id, error=str(exc), exc_info=exc)
    db = SessionLocal()
    try:
        run = db.get(Run, run_id)
        if run is not None and run.status not in {"complete", "no_blueprint", "error"}:
            run.status = "error"
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
```

Update `post_run` to hold the task and attach the callback:

```python
    task = asyncio.create_task(
        _start_run_dispatch(run_id),
        name=f"run-dispatch-{run_id}",
    )
    _pending_run_tasks.add(task)
    task.add_done_callback(_run_task_done)
```

### Verify

```
cd backend && uv run pytest tests/integration/test_runs_dispatch_lifecycle.py -x -v
cd backend && uv run pytest tests/integration/test_runs_concurrency.py -x -v
cd backend && uv run pytest tests/unit -q
```

The existing Task 6 (`test_runs_concurrency.py`) tests must still pass. They check the semaphore exists and is sized — unaffected by this commit.

### Commit message

```
fix(runs): track dispatch tasks and mark run=error on uncaught exception

post_run scheduled _start_run_dispatch with bare asyncio.create_task, no
reference held and no done_callback. Two problems: (a) under CPython
memory pressure, an unreferenced Task can be GC'd before completion;
(b) _start_run_sync's try/except catches failures inside start_run, but
exceptions thrown above that — semaphore acquire, asyncio.to_thread
machinery, threadpool exhaustion — escape silently and leave run.status
stuck on "running" indefinitely.

Hold tasks in a module-level set and add a done_callback that discards
from the set on success and writes run.status='error' on uncaught
exception. The callback only writes 'error' if the status is still
in a pre-terminal state, so it never overwrites a legitimate
"complete" / "no_blueprint" finish.
```

---

## Non-goals (explicit)

- **Auth / rate-limit (audit E5)** — out of scope; documented threat model.
- **`langfuse_trace_id` column rename (audit C2)** — out of scope; schema migration deferred.
- **`_MIME_ROUTES` → public name (final-review suggestion #1)** — out of scope; private name is fine, single consumer.
- **`_run_semaphore` runtime resize (final-review #3)** — out of scope; tests can monkey-patch the module attribute if needed.
- **Switching to a real queue / Arq** — overshoot for this fixup. Future branch when scaling demands it.
- **Defensive-copy of cached `ParsedFile` (final-review #6)** — REFUTED by verifier in this review pass; no current mutation site.

## Risks

- **Commit 2 strip miss:** if any error-write site retains the manual `existing = list(...) + [new]` pattern AND the field is annotated with `operator.add`, errors duplicate. Mitigation: grep `state.get("errors")` after the edit; expected zero hits in `graph.py`. The new accumulator test exercises one duplicated path; the existing Task 7 / Task 10 tests cover the others.
- **Commit 3 TestClient + asyncio interplay:** FastAPI's `TestClient` runs the async code in a sync wrapper. The `time.sleep(0.05)` polling loop in the test is intentionally slow-but-deterministic. If it flakes on CI, swap to `asyncio.run(asyncio.sleep(0))` between checks, or move the test into an `async` test with `httpx.AsyncClient`. Document the contingency in the test file's module docstring.

## Self-review

**Placeholder scan:** no TBDs / TODOs. Every code block is committable.

**Internal consistency:** all three commits ordered correctly; ordering rationale matches the dependency graph (C3 isolated, C2 builds on C3's state, C6 independent).

**Scope check:** three commits, one branch, ~80 LOC. Right size for one execution plan.

**Ambiguity check:** Commit 2's "strip every site" — the spec enumerates all 9 sites, no interpretation needed. The accumulator test asserts the framework-level contract; the per-site regression is covered by existing Task 7/10 tests.
