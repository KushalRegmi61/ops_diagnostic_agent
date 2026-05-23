"""Langfuse observability — no-op when keys are unset or the SDK errors out.

The diagnostic run is the product, not the trace. Setup failures degrade to
no-op spans; runtime exceptions inside the user code still propagate so the
caller sees them.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from typing import Any

try:
    from langfuse import Langfuse
except ImportError:  # pragma: no cover
    Langfuse = None  # type: ignore

from app.config import get_settings

current_trace: ContextVar[Any] = ContextVar("current_trace", default=None)


@lru_cache(maxsize=1)
def langfuse_client():
    """Return a cached Langfuse v3 client, or None if keys/SDK are unavailable."""
    s = get_settings()
    if not (s.langfuse_public_key and s.langfuse_secret_key):
        return None
    if Langfuse is None:
        return None
    try:
        return Langfuse(
            public_key=s.langfuse_public_key,
            secret_key=s.langfuse_secret_key,
            host=s.langfuse_base_url,
        )
    except Exception:
        return None


@contextmanager
def trace_run(run_id: str, *, user_id: str | None = None):
    """Open the top-level Langfuse span for a diagnostic run.

    Uses the v3 OpenTelemetry-style `start_as_current_observation` API.
    Falls back to a no-op context when Langfuse is unavailable.
    """
    client = langfuse_client()
    if client is None:
        token = current_trace.set(None)
        try:
            yield None
        finally:
            current_trace.reset(token)
        return

    try:
        cm = client.start_as_current_observation(
            as_type="span", name="parent_graph",
            input={"run_id": run_id, "user_id": user_id},
        )
    except Exception:
        token = current_trace.set(None)
        try:
            yield None
        finally:
            current_trace.reset(token)
        return

    with cm as root:
        token = current_trace.set(root)
        try:
            yield root
        finally:
            current_trace.reset(token)
            try:
                client.flush()
            except Exception:
                pass


@contextmanager
def node_span(name: str, *, input: dict | None = None):
    """Open a nested span under the current trace (no-op if absent)."""
    client = langfuse_client()
    parent = current_trace.get()
    if client is None or parent is None:
        yield None
        return
    try:
        cm = client.start_as_current_observation(
            as_type="span", name=name, input=input or {},
        )
    except Exception:
        yield None
        return
    with cm as s:
        yield s
