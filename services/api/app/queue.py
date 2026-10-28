"""Job queue. Redis in production, an in-process deque for tests and single-process runs.

The Redis queue moves each job to a processing list while a worker holds it, so a job isn't lost
if the worker dies halfway. `requeue_stale` puts those orphans back on startup.
"""

from __future__ import annotations

import json
import logging
import time
from collections import deque
from typing import Any, Protocol

log = logging.getLogger("docflow.queue")


class JobQueue(Protocol):
    def enqueue(self, job_id: str) -> None: ...
    def take(self, timeout: int = 2) -> str | None: ...
    def ack(self, job_id: str) -> None: ...
    def requeue_stale(self) -> int: ...
    def backend(self) -> str: ...
    def ping(self) -> bool: ...


class MemoryQueue:
    def __init__(self) -> None:
        self._pending: deque[str] = deque()
        self._processing: set[str] = set()

    def enqueue(self, job_id: str) -> None:
        self._pending.append(job_id)

    def take(self, timeout: int = 2) -> str | None:
        if not self._pending:
            return None
        job_id = self._pending.popleft()
        self._processing.add(job_id)
        return job_id

    def ack(self, job_id: str) -> None:
        self._processing.discard(job_id)

    def requeue_stale(self) -> int:
        count = len(self._processing)
        self._pending.extendleft(self._processing)
        self._processing.clear()
        return count

    def backend(self) -> str:
        return "memory"

    def ping(self) -> bool:
        return True


class RedisQueue:
    PENDING = "docflow:jobs:pending"
    PROCESSING = "docflow:jobs:processing"

    def __init__(self, client: Any) -> None:
        self._r = client

    @classmethod
    def from_url(cls, url: str) -> "RedisQueue":
        import redis

        return cls(redis.from_url(url, decode_responses=True, health_check_interval=30))

    def enqueue(self, job_id: str) -> None:
        self._r.lpush(self.PENDING, json.dumps({"id": job_id, "at": time.time()}))

    def take(self, timeout: int = 2) -> str | None:
        raw = self._r.blmove(self.PENDING, self.PROCESSING, timeout, "RIGHT", "LEFT")
        if raw is None:
            return None
        return json.loads(raw)["id"]

    def ack(self, job_id: str) -> None:
        for raw in self._r.lrange(self.PROCESSING, 0, -1):
            if json.loads(raw)["id"] == job_id:
                self._r.lrem(self.PROCESSING, 1, raw)
                return

    def requeue_stale(self) -> int:
        moved = 0
        while self._r.lmove(self.PROCESSING, self.PENDING, "RIGHT", "RIGHT") is not None:
            moved += 1
        if moved:
            log.warning("requeued %d job(s) left in processing", moved)
        return moved

    def backend(self) -> str:
        return "redis"

    def ping(self) -> bool:
        try:
            return bool(self._r.ping())
        except Exception:
            return False


def create_queue(redis_url: str) -> JobQueue:
    if redis_url.strip():
        return RedisQueue.from_url(redis_url)
    return MemoryQueue()
