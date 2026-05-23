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
    # LangGraph BaseCheckpointSaver exposes put / aput (we accept either, since the
    # exact method names differ by langgraph-checkpoint-redis version).
    assert hasattr(cp, "put") or hasattr(cp, "aput")
