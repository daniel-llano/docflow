import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.queue import MemoryQueue
from app.settings import Settings


def make_settings(**overrides) -> Settings:
    base = dict(
        database_url="sqlite://",
        jwt_secret="test-signing-key-that-is-long-enough",
        internal_key="test-internal-key-long-enough",
        webhook_url="",
    )
    base.update(overrides)
    return Settings(_env_file=None, **base)


@pytest.fixture
def client():
    with TestClient(create_app(make_settings(), MemoryQueue())) as c:
        yield c


def signup(c: TestClient, email: str = "ann@example.com") -> dict[str, str]:
    r = c.post("/api/auth/register", json={"email": email, "password": "Secret123"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}
