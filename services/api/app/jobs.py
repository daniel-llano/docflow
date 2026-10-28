"""Job state changes. The API and the in-process worker both go through here."""

from __future__ import annotations

import json
import logging
from typing import Literal

from sqlalchemy.orm import Session

from app import webhooks
from app.models import Job, utcnow
from app.pipeline import extract
from app.settings import Settings

log = logging.getLogger("docflow.jobs")


def start(db: Session, job_id: str) -> Job | None:
    """Claims a queued job. Returns None when it's gone or another worker already finished it."""
    job = db.get(Job, job_id)
    if job is None or job.status not in ("queued", "processing"):
        return None
    job.status = "processing"
    job.attempts += 1
    job.started_at = utcnow()
    db.commit()
    return job


def complete(db: Session, job: Job, result: dict, settings: Settings) -> Job:
    job.status = "completed"
    job.result_json = json.dumps(result)
    job.error = None
    job.finished_at = utcnow()
    db.commit()
    _notify(job, settings, result)
    return job


def fail(db: Session, job: Job, error: str, settings: Settings) -> Literal["retry", "failed"]:
    job.error = error[:2000]
    if job.attempts < settings.max_attempts:
        job.status = "queued"
        db.commit()
        log.warning("job %s failed on attempt %d, will retry: %s", job.id, job.attempts, error)
        return "retry"
    job.status = "failed"
    job.finished_at = utcnow()
    db.commit()
    log.error("job %s failed for good after %d attempts: %s", job.id, job.attempts, error)
    _notify(job, settings, None)
    return "failed"


def run_extract(db: Session, job_id: str, settings: Settings) -> Literal["completed", "retry", "failed", "skipped"]:
    job = start(db, job_id)
    if job is None:
        return "skipped"
    try:
        result = extract(job.source_text)
    except Exception as ex:  # noqa: BLE001 - any pipeline error counts as a failed attempt
        return fail(db, job, str(ex), settings)
    complete(db, job, result, settings)
    return "completed"


def _notify(job: Job, settings: Settings, result: dict | None) -> None:
    event = {
        "type": f"job.{job.status}",
        "jobId": job.id,
        "title": job.title,
        "status": job.status,
        "language": result.get("language") if result else None,
        "keywords": result.get("keywords", []) if result else [],
        "error": job.error,
    }
    webhooks.send(settings.webhook_url, settings.webhook_secret, event)
