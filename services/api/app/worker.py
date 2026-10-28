"""Pulls job ids off the Redis queue, runs the extract pipeline, and reports back to the API."""

from __future__ import annotations

import logging
import os
import signal
import time

import httpx

from app.pipeline import extract
from app.queue import JobQueue, create_queue
from app.settings import get_settings

log = logging.getLogger("docflow.worker")


class Worker:
    def __init__(self, queue: JobQueue, client: httpx.Client) -> None:
        self.queue = queue
        self.client = client
        self.running = True

    def process_once(self) -> bool:
        job_id = self.queue.take(timeout=2)
        if job_id is None:
            return False
        try:
            start = self.client.post(f"/internal/jobs/{job_id}/start")
            if start.status_code in (404, 409):
                log.info("skipping job %s: %s", job_id, start.json().get("detail"))
                return True
            start.raise_for_status()
            try:
                result = extract(start.json()["text"])
            except Exception as ex:  # noqa: BLE001 - report any pipeline error as a failed attempt
                outcome = self.client.post(f"/internal/jobs/{job_id}/fail", json={"error": str(ex)[:2000]})
                outcome.raise_for_status()
                log.warning("job %s failed: %s (%s)", job_id, ex, outcome.json()["outcome"])
                return True
            self.client.post(f"/internal/jobs/{job_id}/complete", json={"result": result}).raise_for_status()
            log.info("job %s completed", job_id)
            return True
        finally:
            self.queue.ack(job_id)

    def run(self) -> None:
        self.queue.requeue_stale()
        log.info("worker started backend=%s", self.queue.backend())
        while self.running:
            try:
                if not self.process_once():
                    time.sleep(0.1)
            except httpx.HTTPError:
                log.exception("API call failed")
                time.sleep(2)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
    )
    settings = get_settings()
    if not settings.redis_url:
        raise SystemExit("REDIS_URL is required for the worker. Without Redis the API processes jobs itself.")
    client = httpx.Client(
        base_url=os.environ.get("API_URL", "http://localhost:8080"),
        headers={"X-Internal-Key": settings.internal_key},
        timeout=30.0,
    )
    worker = Worker(create_queue(settings.redis_url), client)

    def stop(*_):
        log.info("shutting down")
        worker.running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    worker.run()


if __name__ == "__main__":
    main()
