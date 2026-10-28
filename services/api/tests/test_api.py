from fastapi.testclient import TestClient

from app.main import create_app
from app.queue import MemoryQueue
from tests.conftest import make_settings, signup

INVOICE = (
    "Invoice 4471 from Acme Corp is due on 2026-11-15. Please pay $1,250.00 to the account below. "
    "Questions go to billing@acme.test or +1 (415) 555-0199. Card on file: 4111 1111 1111 1111."
)


def test_health(client):
    assert client.get("/health/live").json() == {"status": "ok"}
    ready = client.get("/health/ready").json()
    assert ready["status"] == "ok" and ready["queue"] == "memory" and ready["inline"] is True


def test_register_login_and_me(client):
    headers = signup(client)
    assert client.get("/api/auth/me", headers=headers).json()["email"] == "ann@example.com"

    r = client.post("/api/auth/login", json={"email": "ANN@example.com", "password": "Secret123"})
    assert r.status_code == 200 and r.json()["token"]


def test_register_rejects_duplicates_and_weak_passwords(client):
    signup(client)
    assert client.post("/api/auth/register", json={"email": "ann@example.com", "password": "Secret123"}).status_code == 409
    assert client.post("/api/auth/register", json={"email": "bob@example.com", "password": "password"}).status_code == 422


def test_login_wrong_password(client):
    signup(client)
    assert client.post("/api/auth/login", json={"email": "ann@example.com", "password": "nope"}).status_code == 401


def test_jobs_need_a_token(client):
    assert client.get("/api/jobs").status_code == 401
    assert client.get("/api/jobs", headers={"Authorization": "Bearer junk"}).status_code == 401


def test_text_job_completes_with_extract(client):
    headers = signup(client)
    r = client.post("/api/jobs", json={"title": "Acme invoice", "text": INVOICE}, headers=headers)
    assert r.status_code == 201

    job = client.get(f"/api/jobs/{r.json()['id']}", headers=headers).json()
    assert job["status"] == "completed"
    result = job["result"]
    assert result["language"] == "en"
    assert "$1,250.00" in result["amounts"]
    assert "2026-11-15" in result["dates"]
    assert result["pii"] == {"email": 1, "phone": 1, "card": 1, "iban": 0}
    assert "billing@acme.test" not in result["masked_preview"]


def test_upload_text_file(client):
    headers = signup(client)
    r = client.post(
        "/api/jobs/upload",
        files={"file": ("notes.md", b"# Meeting\nWe agreed to ship the release on 2026-12-01.", "text/markdown")},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    assert r.json()["filename"] == "notes.md"
    assert client.get(f"/api/jobs/{r.json()['id']}", headers=headers).json()["status"] == "completed"


def test_upload_rejects_unsupported_and_oversized_files():
    with TestClient(create_app(make_settings(max_upload_mb=1), MemoryQueue())) as c:
        headers = signup(c)
        assert c.post("/api/jobs/upload", files={"file": ("x.exe", b"MZ", "application/octet-stream")}, headers=headers).status_code == 422
        big = b"a" * (1024 * 1024 + 10)
        assert c.post("/api/jobs/upload", files={"file": ("big.txt", big, "text/plain")}, headers=headers).status_code == 413


def test_users_only_see_their_own_jobs(client):
    ann = signup(client, "ann@example.com")
    bob = signup(client, "bob@example.com")
    job_id = client.post("/api/jobs", json={"title": "Private", "text": INVOICE}, headers=ann).json()["id"]

    assert client.get(f"/api/jobs/{job_id}", headers=bob).status_code == 404
    assert client.delete(f"/api/jobs/{job_id}", headers=bob).status_code == 404
    assert client.get("/api/jobs", headers=bob).json() == {"items": [], "total": 0}


def test_list_paginates_and_filters(client):
    headers = signup(client)
    for i in range(3):
        client.post("/api/jobs", json={"title": f"Doc {i}", "text": INVOICE}, headers=headers)

    page = client.get("/api/jobs?limit=2&offset=0", headers=headers).json()
    assert page["total"] == 3 and len(page["items"]) == 2
    assert client.get("/api/jobs?status=failed", headers=headers).json()["total"] == 0


def test_delete_job(client):
    headers = signup(client)
    job_id = client.post("/api/jobs", json={"title": "Temp", "text": INVOICE}, headers=headers).json()["id"]

    assert client.delete(f"/api/jobs/{job_id}", headers=headers).status_code == 204
    assert client.get(f"/api/jobs/{job_id}", headers=headers).status_code == 404


def test_failed_job_can_be_retried(client):
    headers = signup(client)
    # Whitespace-only text passes request validation but the pipeline refuses it.
    job_id = client.post("/api/jobs", json={"title": "Blank", "text": "   "}, headers=headers).json()["id"]
    job = client.get(f"/api/jobs/{job_id}", headers=headers).json()
    assert job["status"] == "failed" and job["attempts"] == 3 and job["error"]

    retried = client.post(f"/api/jobs/{job_id}/retry", headers=headers)
    assert retried.status_code == 200
    assert client.post(f"/api/jobs/{job_id}/retry", headers=headers).status_code in (200, 409)


def test_retry_only_for_failed_jobs(client):
    headers = signup(client)
    job_id = client.post("/api/jobs", json={"title": "Fine", "text": INVOICE}, headers=headers).json()["id"]
    assert client.post(f"/api/jobs/{job_id}/retry", headers=headers).status_code == 409


def test_internal_endpoints_need_the_key(client):
    assert client.post("/internal/jobs/x/start").status_code == 401
    assert client.post("/internal/jobs/x/start", headers={"X-Internal-Key": "wrong"}).status_code == 401


def test_bootstrap_user_is_created():
    settings = make_settings(bootstrap_email="ops@example.com", bootstrap_password="Bootstrap123")
    with TestClient(create_app(settings, MemoryQueue())) as c:
        assert c.post("/api/auth/login", json={"email": "ops@example.com", "password": "Bootstrap123"}).status_code == 200


def test_no_default_user_is_seeded(client):
    assert client.post("/api/auth/login", json={"email": "admin@example.com", "password": "Admin@1234"}).status_code == 401
