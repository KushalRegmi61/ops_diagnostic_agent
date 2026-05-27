"""Redis-backed LangGraph checkpointer wiring.

Wraps `langgraph-checkpoint-redis` to persist every graph step under a
thread_id (= run_id), so the parent workflow can resume across the bounded
redo/revision loops. Requires Redis Stack (RedisJSON + RediSearch) — plain
redis-server will fail with `unknown command 'JSON.SET'`. No in-memory
fallback by design.
"""
import redis as redis_lib

try:
    from langgraph.checkpoint.redis import RedisSaver
except ImportError:  # pragma: no cover
    RedisSaver = None  # type: ignore

from app.config import get_settings


def redis_healthcheck() -> bool:
    """Return True if Redis at REDIS_URL is reachable; False otherwise."""
    settings = get_settings()
    try:
        client = redis_lib.Redis.from_url(settings.redis_url, socket_timeout=2)
        return client.ping() is True
    except Exception:
        return False


def build_checkpointer():
    """Return a Redis-backed LangGraph checkpointer.

    Raises RuntimeError if Redis is not reachable — no in-memory fallback in v1.

    Probe results (langgraph-checkpoint-redis installed in this project):
      - RedisSaver.__init__ accepts redis_url as a positional/keyword arg.
      - .setup() exists and initialises the Redis schema/indexes.
      - from_conn_string() class method also available, but direct constructor used here.
    """
    if not redis_healthcheck():
        raise RuntimeError(
            f"Redis unreachable at {get_settings().redis_url}; "
            "the LangGraph checkpointer is required in v1. "
            "Start Redis or set REDIS_URL."
        )
    if RedisSaver is None:
        raise RuntimeError("langgraph-checkpoint-redis is not installed")

    settings = get_settings()
    # langgraph-checkpoint-redis requires Redis Stack (RedisJSON + RediSearch
    # modules) — plain redis-server is not sufficient. See backend/README.md.
    # TTL is hard-capped at 10 min defensively: Redis Cloud free tier is 30 MB,
    # and config drift must not silently bloat retention.
    ttl_minutes = min(settings.langgraph_checkpoint_ttl_minutes, 10)
    ttl_config = {
        "default_ttl": ttl_minutes,
        "refresh_on_read": settings.langgraph_checkpoint_refresh_on_read,
    }
    saver = RedisSaver(redis_url=settings.redis_url, ttl=ttl_config)
    if hasattr(saver, "setup"):
        saver.setup()
    return saver
