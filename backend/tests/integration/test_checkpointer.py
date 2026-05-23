"""Redis Stack checkpointer: healthcheck + saver construction.

Touches the real Redis Stack instance (requires RedisJSON + RediSearch modules).
Skipped when Redis is not reachable on the configured URL.
"""
import pytest
import redis as redis_lib

from app.checkpointer import build_checkpointer, redis_healthcheck
from app.config import get_settings


def _redis_up() -> bool:
    """Return True if a Redis client can PING the configured redis_url."""
    try:
        r = redis_lib.Redis.from_url(get_settings().redis_url, socket_timeout=1)
        return r.ping() is True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _redis_up(), reason="Redis not reachable")


def test_redis_healthcheck_passes_when_up():
    """redis_healthcheck() returns True against a reachable Redis Stack."""
    assert redis_healthcheck() is True


def test_build_checkpointer_returns_a_saver():
    """build_checkpointer() yields a LangGraph saver with put/aput methods."""
    cp = build_checkpointer()
    assert cp is not None
    # LangGraph BaseCheckpointSaver exposes put / aput (we accept either, since the
    # exact method names differ by langgraph-checkpoint-redis version).
    assert hasattr(cp, "put") or hasattr(cp, "aput")
