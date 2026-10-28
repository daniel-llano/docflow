import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated, Literal

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app import jobs as job_service
from app.db import make_engine, make_session_factory
from app.documents import UnreadableDocument, read_text
from app.models import Job, User
from app.queue import JobQueue, MemoryQueue, create_queue
from app.security import create_token, current_user_id, hash_password, keys_match, verify_password
from app.settings import Settings, get_settings

log = logging.getLogger("docflow.api")


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def letters_and_digits(cls, value: str) -> str:
        if not (any(c.isalpha() for c in value) and any(c.isdigit() for c in value)):
            raise ValueError("Use at least one letter and one digit.")
        return value


class LoginBody(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class TokenOut(BaseModel):
    token: str
    expiresAt: datetime
    email: str


class CreateJob(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=200_000)


class JobOut(BaseModel):
    id: str
    title: str
    filename: str | None
    status: str
    attempts: int
    result: dict | None
    error: str | None
    createdAt: datetime
    finishedAt: datetime | None


class JobPage(BaseModel):
    items: list[JobOut]
    total: int


class FailBody(BaseModel):
    error: str = Field(max_length=2000)


def _job_out(job: Job) -> JobOut:
    return JobOut(
        id=job.id,
        title=job.title,
        filename=job.filename,
        status=job.status,
        attempts=job.attempts,
        result=json.loads(job.result_json) if job.result_json else None,
        error=job.error if job.status == "failed" else None,
        createdAt=job.created_at,
        finishedAt=job.finished_at,
    )


def create_app(settings: Settings | None = None, queue: JobQueue | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = make_engine(settings.database_url)
    SessionLocal = make_session_factory(engine)
    job_queue = queue if queue is not None else create_queue(settings.redis_url)
    inline = settings.inline_worker if settings.inline_worker is not None else isinstance(job_queue, MemoryQueue)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logging.basicConfig(
            level=logging.INFO,
            format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
        )
        if settings.database_url.startswith("sqlite"):
            # SQLite is for tests and single-box runs. PostgreSQL gets its schema from Alembic.
            from app.models import Base

            Base.metadata.create_all(engine)
        _bootstrap_user(SessionLocal, settings)
        yield
        engine.dispose()

    app = FastAPI(
        title="DocFlow API",
        version="2.0.0",
        description="Upload documents, queue them, and get keywords, language, amounts, dates, and masked PII back.",
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
    )
    app.state.settings = settings
    app.state.queue = job_queue
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_list,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    def get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    DB = Annotated[Session, Depends(get_db)]
    UserId = Annotated[str, Depends(current_user_id)]

    def require_internal(x_internal_key: Annotated[str | None, Header()] = None) -> None:
        if not keys_match(x_internal_key, settings.internal_key):
            raise HTTPException(status_code=401, detail="Invalid internal key.")

    def process_inline(job_id: str) -> None:
        db = SessionLocal()
        try:
            while job_service.run_extract(db, job_id, settings) == "retry":
                pass
        finally:
            db.close()

    def submit(db: Session, job: Job, background: BackgroundTasks) -> JobOut:
        db.add(job)
        db.commit()
        if inline:
            background.add_task(process_inline, job.id)
        else:
            job_queue.enqueue(job.id)
        return _job_out(job)

    def owned_job(db: Session, job_id: str, user_id: str) -> Job:
        job = db.get(Job, job_id)
        if job is None or job.user_id != user_id:
            raise HTTPException(status_code=404, detail="Job not found.")
        return job

    @app.get("/health/live")
    def live():
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready(db: DB):
        db.execute(text("SELECT 1"))
        if not job_queue.ping():
            return JSONResponse({"status": "degraded", "queue": job_queue.backend()}, status_code=503)
        return {"status": "ok", "queue": job_queue.backend(), "inline": inline}

    @app.post("/api/auth/register", status_code=201, response_model=TokenOut)
    def register(body: Credentials, db: DB):
        email = body.email.lower()
        if db.scalar(select(User).where(User.email == email)):
            raise HTTPException(status_code=409, detail="That email is already registered. Sign in instead.")
        user = User(id=str(uuid.uuid4()), email=email, password_hash=hash_password(body.password))
        db.add(user)
        db.commit()
        token, expires = create_token(user.id, user.email, settings.jwt_secret, settings.jwt_minutes)
        return TokenOut(token=token, expiresAt=expires, email=user.email)

    @app.post("/api/auth/login", response_model=TokenOut)
    def login(body: LoginBody, db: DB):
        user = db.scalar(select(User).where(User.email == body.email.lower()))
        if user is None or not verify_password(body.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Wrong email or password.")
        token, expires = create_token(user.id, user.email, settings.jwt_secret, settings.jwt_minutes)
        return TokenOut(token=token, expiresAt=expires, email=user.email)

    @app.get("/api/auth/me")
    def me(user_id: UserId, db: DB):
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=401, detail="Sign in again.")
        return {"id": user.id, "email": user.email}

    @app.post("/api/jobs", status_code=201, response_model=JobOut)
    def create_job(body: CreateJob, user_id: UserId, db: DB, background: BackgroundTasks):
        job = Job(id=str(uuid.uuid4()), user_id=user_id, title=body.title.strip(), source_text=body.text)
        return submit(db, job, background)

    @app.post("/api/jobs/upload", status_code=201, response_model=JobOut)
    async def upload_job(
        user_id: UserId,
        db: DB,
        background: BackgroundTasks,
        file: Annotated[UploadFile, File()],
        title: Annotated[str | None, Form(max_length=200)] = None,
    ):
        limit = settings.max_upload_mb * 1024 * 1024
        data = await file.read(limit + 1)
        if len(data) > limit:
            raise HTTPException(status_code=413, detail=f"Files can be up to {settings.max_upload_mb} MB.")
        try:
            content = read_text(file.filename or "", data)
        except UnreadableDocument as ex:
            raise HTTPException(status_code=422, detail=str(ex)) from ex
        name = (file.filename or "document")[:255]
        job = Job(id=str(uuid.uuid4()), user_id=user_id, title=(title or name).strip()[:200], filename=name, source_text=content)
        return submit(db, job, background)

    @app.get("/api/jobs", response_model=JobPage)
    def list_jobs(
        user_id: UserId,
        db: DB,
        status: Literal["queued", "processing", "completed", "failed"] | None = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        offset: Annotated[int, Query(ge=0)] = 0,
    ):
        query = select(Job).where(Job.user_id == user_id)
        if status:
            query = query.where(Job.status == status)
        total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = db.scalars(query.order_by(Job.created_at.desc()).limit(limit).offset(offset)).all()
        return JobPage(items=[_job_out(j) for j in rows], total=total)

    @app.get("/api/jobs/{job_id}", response_model=JobOut)
    def get_job(job_id: str, user_id: UserId, db: DB):
        return _job_out(owned_job(db, job_id, user_id))

    @app.delete("/api/jobs/{job_id}", status_code=204)
    def delete_job(job_id: str, user_id: UserId, db: DB):
        db.delete(owned_job(db, job_id, user_id))
        db.commit()

    @app.post("/api/jobs/{job_id}/retry", response_model=JobOut)
    def retry_job(job_id: str, user_id: UserId, db: DB, background: BackgroundTasks):
        job = owned_job(db, job_id, user_id)
        if job.status != "failed":
            raise HTTPException(status_code=409, detail="Only failed jobs can be retried.")
        job.status, job.attempts, job.error, job.finished_at = "queued", 0, None, None
        return submit(db, job, background)

    # The worker process talks to these. They're never exposed through the web app.
    @app.post("/internal/jobs/{job_id}/start", dependencies=[Depends(require_internal)])
    def internal_start(job_id: str, db: DB):
        job = job_service.start(db, job_id)
        if job is None:
            raise HTTPException(status_code=409, detail="Job is gone or already finished.")
        return {"id": job.id, "text": job.source_text, "attempt": job.attempts}

    @app.post("/internal/jobs/{job_id}/complete", dependencies=[Depends(require_internal)], response_model=JobOut)
    def internal_complete(job_id: str, body: dict, db: DB):
        job = db.get(Job, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found.")
        return _job_out(job_service.complete(db, job, body.get("result", {}), settings))

    @app.post("/internal/jobs/{job_id}/fail", dependencies=[Depends(require_internal)])
    def internal_fail(job_id: str, body: FailBody, db: DB):
        job = db.get(Job, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found.")
        outcome = job_service.fail(db, job, body.error, settings)
        if outcome == "retry":
            job_queue.enqueue(job.id)
        return {"outcome": outcome}

    return app


def _bootstrap_user(SessionLocal, settings: Settings) -> None:
    if not settings.bootstrap_email or not settings.bootstrap_password:
        return
    db = SessionLocal()
    try:
        email = settings.bootstrap_email.lower()
        if db.scalar(select(User).where(User.email == email)) is None:
            db.add(User(id=str(uuid.uuid4()), email=email, password_hash=hash_password(settings.bootstrap_password)))
            db.commit()
            log.info("created bootstrap user %s", email)
    finally:
        db.close()


def __getattr__(name: str):
    # `uvicorn app.main:app` builds the app on first access, so importing the module stays cheap for tests.
    if name == "app":
        return create_app()
    raise AttributeError(name)
