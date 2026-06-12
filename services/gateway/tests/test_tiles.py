"""Tile proxy: OSM base + OpenAIP overlay caching, key handling (R2)."""

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.errors import install_error_handlers
from app.api.tiles import make_tiles_router

PNG = b"\x89PNG\r\n\x1a\n" + b"fake-tile-bytes"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAIP_API_KEY", raising=False)
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(make_tiles_router(tile_dir=tmp_path))
    return TestClient(app), tmp_path, monkeypatch


@respx.mock
def test_osm_tile_fetched_then_cached(client):
    c, tile_dir, _ = client
    route = respx.get("https://tile.openstreetmap.org/8/121/98.png").mock(
        return_value=httpx.Response(200, content=PNG)
    )
    r1 = c.get("/tiles/8/121/98.png")
    assert r1.status_code == 200 and r1.content == PNG
    assert (tile_dir / "osm" / "8" / "121" / "98.png").exists()
    # second hit served from cache — upstream called only once
    r2 = c.get("/tiles/8/121/98.png")
    assert r2.status_code == 200
    assert route.call_count == 1


@respx.mock
def test_osm_offline_miss_404(client):
    c, _td, _ = client
    respx.get(url__startswith="https://tile.openstreetmap.org").mock(side_effect=httpx.ConnectError)
    assert c.get("/tiles/7/10/20.png").status_code == 404


def test_openaip_404_without_key(client):
    c, _td, _ = client  # OPENAIP_API_KEY unset
    r = c.get("/tiles/openaip/8/121/98.png")
    assert r.status_code == 404
    assert "not configured" in r.json()["title"]


@respx.mock
def test_openaip_uses_key_and_caches(client):
    c, tile_dir, monkeypatch = client
    monkeypatch.setenv("OPENAIP_API_KEY", "secret123")
    captured = {}

    def handler(request):
        captured["auth_header"] = request.headers.get("x-openaip-api-key")
        captured["url"] = str(request.url)
        return httpx.Response(200, content=PNG)

    respx.get(url__startswith="https://api.tiles.openaip.net").mock(side_effect=handler)
    r = c.get("/tiles/openaip/9/250/170.png")
    assert r.status_code == 200 and r.content == PNG
    assert captured["auth_header"] == "secret123"  # key sent in header
    assert "apiKey=secret123" in captured["url"]  # and query (legacy)
    assert (tile_dir / "openaip" / "9" / "250" / "170.png").exists()


def test_openaip_key_never_in_config_only_flag(client, monkeypatch):
    # the key must not leak to clients — config exposes only a boolean (tested in
    # test_ws_flow via /api/v1/config); here we assert the route gates on presence
    c, _td, mp = client
    mp.setenv("OPENAIP_API_KEY", "k")
    # out-of-range still 404 even with key (no upstream call)
    assert c.get("/tiles/openaip/20/1/1.png").status_code == 404
