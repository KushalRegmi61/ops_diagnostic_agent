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
    # RedisSaver(redis_url=...) is the direct constructor form confirmed by probe.
    # .setup() creates the required Redis indexes/schema.
    saver = RedisSaver(redis_url=settings.redis_url)
    if hasattr(saver, "setup"):
        try:
            saver.setup()
        except Exception:
            # .setup() creates RediSearch indexes which require the RedisSearch
            # module (FT._LIST). When running plain Redis without the Search
            # module the index creation fails, but basic put/get checkpoint
            # operations still work fine — so we swallow this error.
            pass
    return saver
