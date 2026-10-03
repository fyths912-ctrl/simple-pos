"""非機能（セキュリティヘッダー・エラー非開示・接続プール・ログ・CORS）"""
import logging

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import engine as engine_module
from tests.conftest import P_CURRY


# --- T-060 セキュリティヘッダー ---
def test_T060_security_headers(auth_client):
    r = auth_client.get(f"/api/products/{P_CURRY}")
    h = r.headers
    assert h["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in h["content-security-policy"]
    assert h["referrer-policy"] == "strict-origin-when-cross-origin"
    assert h["strict-transport-security"].startswith("max-age=")


# --- T-061 詳細エラーの非開示 ---
def test_T061_internal_error_is_generic(auth_client, monkeypatch):
    from app.repositories import product_repository

    def boom(*_):
        raise RuntimeError("SELECT * FROM secret_table /home/app/internal.py")

    monkeypatch.setattr(product_repository, "get_active", boom)
    r = auth_client.get(f"/api/products/{P_CURRY}")
    assert r.status_code == 500
    assert r.json() == {"error": {"code": "INTERNAL_ERROR", "message": "システムエラーが発生しました"}}
    for leak in ("Traceback", "secret_table", "/home/app", "RuntimeError"):
        assert leak not in r.text


def test_api_docs_not_exposed(anon_client):
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert anon_client.get(path).status_code == 404


# --- T-065 接続プール設定 ---
def test_T065_engine_pool_settings():
    s = Settings(database_url="mysql+pymysql://u:p@localhost/x", db_pool_recycle_seconds=1500)
    eng = engine_module.build_engine(s)
    try:
        assert eng.pool._pre_ping is True
        assert eng.pool._recycle == 1500
        assert eng.pool.size() == 5
    finally:
        eng.dispose()


def test_T065_engine_created_once():
    first = engine_module.init_engine(Settings())
    assert engine_module.init_engine(Settings()) is first


# --- T-066 接続の使い回し ---
def test_T066_connections_are_reused(auth_client):
    eng = engine_module.get_engine()
    for _ in range(10):
        auth_client.get(f"/api/products/{P_CURRY}")
    # 10リクエストしても、プールが保持する接続は数本で済む
    assert eng.pool.checkedin() <= 2
    assert eng.pool.checkedout() == 0


# --- T-069 API ログの内容 ---
def test_T069_api_log_has_no_pii(auth_client, caplog):
    caplog.set_level(logging.INFO, logger="pos")
    auth_client.get("/api/members/M000123")
    rec = [r for r in caplog.records if r.name == "pos.api"][-1]
    assert rec.endpoint == "/api/members/{member_id}"  # 実際の会員IDはログに残さない
    assert rec.status == 200 and rec.request_id and rec.duration_ms >= 0
    text_all = caplog.text + "".join(str(r.__dict__) for r in caplog.records)
    for pii in ("M000123", "山田 太郎", "090-0000-0001", "大阪府", auth_client.cookies["pos_session"]):
        assert pii not in text_all


def test_json_log_formatter_drops_unknown_fields():
    from app.core.logging_setup import JsonFormatter
    rec = logging.LogRecord("pos.api", logging.INFO, __file__, 1, "api", None, None)
    rec.request_id = "abc"
    rec.cookie = "SECRET"
    out = JsonFormatter().format(rec)
    assert "abc" in out and "SECRET" not in out


# --- T-056/T-057 CORS ---
def test_T056_wildcard_origin_rejected(monkeypatch):
    from app import main
    monkeypatch.setattr(main, "get_settings", lambda: Settings(cors_allow_origins=["*"]))
    with pytest.raises(RuntimeError):
        main.create_app()


def test_T057_disallowed_origin(monkeypatch):
    from app import main
    monkeypatch.setattr(main, "get_settings", lambda: Settings(cors_allow_origins=["https://pos.example.com"]))
    app = main.create_app()
    with TestClient(app, base_url="https://testserver") as c:
        ok = c.options("/api/auth/login", headers={"Origin": "https://pos.example.com", "Access-Control-Request-Method": "POST"})
        ng = c.options("/api/auth/login", headers={"Origin": "https://evil.example.com", "Access-Control-Request-Method": "POST"})
    assert ok.headers.get("access-control-allow-origin") == "https://pos.example.com"
    assert ng.status_code == 400 and "access-control-allow-origin" not in ng.headers


# --- T-055（アプリ側）HTTPS 強制 ---
def test_T055_force_https(monkeypatch):
    from app import main
    monkeypatch.setattr(main, "get_settings", lambda: Settings(force_https=True))
    app = main.create_app()
    with TestClient(app, base_url="http://testserver") as c:
        r = c.get("/api/health", follow_redirects=False)
        assert r.status_code == 308 and r.headers["location"].startswith("https://")
        assert c.post("/api/auth/login", json={}).status_code == 400
        assert c.get("/api/health", headers={"X-Forwarded-Proto": "https"}).status_code == 200


def test_health(anon_client):
    r = anon_client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "db": "ok"}
