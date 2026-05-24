"""GET /health smoke test for the FastAPI app."""
from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok():
    """/health responds 200 with {"status": "ok"}."""
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_cors_allows_local_frontend_origin():
    """CORS preflight accepts the default local Next.js frontend origin."""
    client = TestClient(app)
    r = client.options(
        "/api/files",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"
