"""GET /health smoke test for the FastAPI app."""
from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok():
    """/health responds 200 with {"status": "ok"}."""
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
