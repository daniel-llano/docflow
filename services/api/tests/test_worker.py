import hashlib
import hmac
import json

import fakeredis
import httpx
from fastapi.testclient import TestClient

from app import webhooks
from app.main import create_app
from app.queue import RedisQueue
from app.worker import Worker
from tests.conftest import make_settings, signup


def test_redis_queue_keeps_jobs_until_acked():
    q = RedisQueue(fakeredis.FakeRedis(decode_responses=True))
    q.enqueue("job-1")

    assert q.take(timeout=1) == "job-1"
    assert q.take(timeout=1) is None
    # The worker "crashed" without acking, so the job comes back on the next start.
    assert q.requeue_stale() == 1
    assert q.take(timeout=1) == "job-1"
    q.ack("job-1")
    assert q.requeue_stale() == 0


def test_worker_processes_queued_jobs_through_the_api():
    queue = RedisQueue(fakeredis.FakeRedis(decode_responses=True))
    settings = make_settings(inline_worker=False)
    with TestClient(create_app(settings, queue), headers={"X-Internal-Key": settings.internal_key}) as api:
        headers = signup(api)
        job_id = api.post("/api/jobs", json={"title": "Memo", "text": "Ship the release on 2026-12-01."}, headers=headers).json()["id"]
        assert api.get(f"/api/jobs/{job_id}", headers=headers).json()["status"] == "queued"

        assert Worker(queue, api).process_once() is True

        job = api.get(f"/api/jobs/{job_id}", headers=headers).json()
        assert job["status"] == "completed"
        assert job["result"]["dates"] == ["2026-12-01"]


def test_worker_retries_then_marks_failed():
    queue = RedisQueue(fakeredis.FakeRedis(decode_responses=True))
    settings = make_settings(inline_worker=False, max_attempts=2)
    with TestClient(create_app(settings, queue), headers={"X-Internal-Key": settings.internal_key}) as api:
        headers = signup(api)
        job_id = api.post("/api/jobs", json={"title": "Blank", "text": "  "}, headers=headers).json()["id"]
        worker = Worker(queue, api)

        worker.process_once()
        assert api.get(f"/api/jobs/{job_id}", headers=headers).json()["status"] == "queued"
        worker.process_once()
        job = api.get(f"/api/jobs/{job_id}", headers=headers).json()
        assert job["status"] == "failed" and job["attempts"] == 2


def test_worker_skips_deleted_jobs():
    queue = RedisQueue(fakeredis.FakeRedis(decode_responses=True))
    settings = make_settings(inline_worker=False)
    with TestClient(create_app(settings, queue), headers={"X-Internal-Key": settings.internal_key}) as api:
        headers = signup(api)
        job_id = api.post("/api/jobs", json={"title": "Gone", "text": "Some text here."}, headers=headers).json()["id"]
        api.delete(f"/api/jobs/{job_id}", headers=headers)

        assert Worker(queue, api).process_once() is True
        assert queue.requeue_stale() == 0


def test_webhooks_are_signed(monkeypatch):
    sent = {}

    def fake_post(url, content, headers, timeout):
        sent.update(url=url, body=content, headers=headers)
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(webhooks.httpx, "post", fake_post)
    webhooks.send("http://hooks.test/jobs", "shh-secret", {"type": "job.completed", "jobId": "1"})

    expected = "sha256=" + hmac.new(b"shh-secret", sent["body"], hashlib.sha256).hexdigest()
    assert sent["headers"]["X-DocFlow-Signature"] == expected
    assert json.loads(sent["body"])["jobId"] == "1"
