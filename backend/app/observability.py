from contextlib import contextmanager
from functools import lru_cache
from typing import Any

try:
    from langfuse import Langfuse
except ImportError:  # pragma: no cover
    Langfuse = None  # type: ignore

from app.config import get_settings


@lru_cache(maxsize=1)
def langfuse_client():
    s = get_settings()
    if not (s.langfuse_public_key and s.langfuse_secret_key):
        return None
    if Langfuse is None:
        return None
    return Langfuse(
        public_key=s.langfuse_public_key,
        secret_key=s.langfuse_secret_key,
        host=s.langfuse_base_url,
    )


@contextmanager
def trace_run(run_id: str, *, user_id: str | None = None):
    """Open a top-level Langfuse trace for one diagnostic run.

    Yields the trace handle (or None if Langfuse is not configured).
    """
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
