"""Gateway smoke test: app factory boots with a valid config and serves /healthz."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import load_config
from app.main import create_app

EXAMPLE = Path(__file__).parents[3] / "shared" / "config" / "config.example.yaml"


def test_healthz():
    app = create_app(config=load_config(EXAMPLE))
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "service": "gateway"}
