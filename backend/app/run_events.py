"""In-process run event hub for WebSocket progress updates."""
import asyncio
from collections import defaultdict, deque
from datetime import UTC, datetime
from threading import RLock
from typing import Any


class RunEventHub:
    """Stores recent run events and fans out live updates to WebSocket subscribers."""

    def __init__(self, *, history_limit: int = 250) -> None:
        self._history_limit = history_limit
        self._history: dict[str, deque[dict[str, Any]]] = defaultdict(lambda: deque(maxlen=history_limit))
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._seq: dict[str, int] = defaultdict(int)
        self._lock = RLock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Bind the asyncio loop used by WebSocket connections."""
        self._loop = loop

    def history(self, run_id: str) -> list[dict[str, Any]]:
        """Return buffered events for a run."""
        with self._lock:
            return list(self._history[run_id])

    def subscribe(self, run_id: str) -> asyncio.Queue:
        """Create a live subscriber queue for a run."""
        queue: asyncio.Queue = asyncio.Queue()
        with self._lock:
            self._subscribers[run_id].add(queue)
        return queue

    def subscribe_with_history(self, run_id: str) -> tuple[asyncio.Queue, list[dict[str, Any]]]:
        """Subscribe and snapshot buffered events without a replay/live race."""
        queue: asyncio.Queue = asyncio.Queue()
        with self._lock:
            history = list(self._history[run_id])
            self._subscribers[run_id].add(queue)
        return queue, history

    def unsubscribe(self, run_id: str, queue: asyncio.Queue) -> None:
        """Remove a live subscriber queue."""
        with self._lock:
            self._subscribers[run_id].discard(queue)

    def publish(
        self,
        run_id: str,
        *,
        type: str,
        message: str,
        stage: str,
        level: str = "info",
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Publish one event to history and connected subscribers."""
        with self._lock:
            self._seq[run_id] += 1
            event = {
                "seq": self._seq[run_id],
                "run_id": run_id,
                "type": type,
                "level": level,
                "stage": stage,
                "message": message,
                "data": data or {},
                "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            }
            self._history[run_id].append(event)
            subscribers = list(self._subscribers[run_id])

        for queue in subscribers:
            self._put(queue, event)
        return event

    def _put(self, queue: asyncio.Queue, event: dict[str, Any]) -> None:
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(queue.put_nowait, event)
        else:
            queue.put_nowait(event)


run_event_hub = RunEventHub()
