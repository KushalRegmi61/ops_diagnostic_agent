"""Teach the langgraph-checkpoint-redis JSON serializer to dump Pydantic models.

The Redis checkpointer writes state as JSON (via orjson). orjson does not know
about Pydantic BaseModel instances; the serializer's fallback `_default_handler`
raises TypeError for them.

We extend that fallback so any BaseModel falls through to its `model_dump()`
dict. The msgpack sidecar handles re-hydration back to the original Pydantic
types on read, so node code keeps seeing the model classes it expects.

Import this module once at process start (we do it from app.graph).
"""
from typing import Any

from pydantic import BaseModel

from langgraph.checkpoint.redis.base import JsonPlusRedisSerializer


_ORIGINAL = JsonPlusRedisSerializer._default_handler


def _patched_default_handler(self: JsonPlusRedisSerializer, obj: Any) -> Any:
    """Serializer fallback: dump Pydantic models via model_dump(); otherwise delegate to original."""
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    return _ORIGINAL(self, obj)


JsonPlusRedisSerializer._default_handler = _patched_default_handler
