"""ログイン・セッション（F-004 / NF-005 / NF-007）"""
import logging

import pytest
from sqlalchemy import select, update

from app.core.security import hash_password, hash_session_id, verify_password
from app.models.db_models import Cashier, Session
from tests.conftest import PASSWORD, later


def login(client, cashier_id="C001", password=PASSWORD):
    return client.post("/api/auth/login", json={"cashier_id": cashier_id, "password": password})


# --- T-001 パスワード照合関数 ---
def test_T001_verify_password():
    h = hash_password("abcdefgh")
    assert h.startswith("$argon2id$")
    assert verify_password("abcdefgh", h) is True
    assert verify_password("abcdefgX", h) is False
    assert verify_password("abcdefgh", "not-a-hash") is False


# --- T-002 無効化担当者 ---
def test_T002_disabled_cashier(client):
    r = login(client, "C099")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "CASHIER_DISABLED"
    assert "pos_session" not in r.cookies


# --- T-003 入力検証（空文字）---
@pytest.mark.parametrize("body", [
    {"cashier_id": "", "password": PASSWORD},
    {"cashier_id": "C001", "password": ""},
    {"cashier_id": "C001"},
])
def test_T003_empty_input(client, body):
    r = client.post("/api/auth/login", json=body)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert PASSWORD not in r.text


# --- T-004 パスワード文字数境界（8〜64：暫定）---
@pytest.mark.parametrize("length,expected", [(7, 422), (8, 401), (64, 401), (65, 422)])
def test_T004_password_length_boundary(client, length, expected):
    # 8/64 文字は検証を通過し（パスワード違いなので401）、7/65 文字は 422
    r = login(client, password="x" * length)
    assert r.status_code == expected


def test_T004_password_8_and_64_can_login(client, db):
    for pw in ("a" * 8, "b" * 64):
        db.execute(update(Cashier).where(Cashier.cashier_id == "C002").values(password_hash=hash_password(pw)))
        db.commit()
        assert login(client, "C002", pw).status_code == 200


# --- T-005 ログイン成功 ---
def test_T005_login_success_sets_secure_cookie(client):
    r = login(client)
    assert r.status_code == 200
    assert r.json() == {"cashier": {"cashier_id": "C001", "cashier_name": "山田"}}
    set_cookie = r.headers["set-cookie"]
    assert "pos_session=" in set_cookie
    assert "HttpOnly" in set_cookie and "Secure" in set_cookie and "samesite=lax" in set_cookie.lower()

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json() == {"cashier_id": "C001", "cashier_name": "山田"}


def test_T005_session_id_stored_as_hash(client, db):
    r = login(client)
    raw = r.cookies["pos_session"]
    assert db.get(Session, raw) is None                       # 生のIDは保存されない
    assert db.get(Session, hash_session_id(raw)) is not None  # ハッシュで保存される


# --- T-006 失敗時の応答（ID存在有無を推測させない）---
def test_T006_failure_messages_identical(client):
    wrong_pw = login(client, "C001", "wrong-password")
    no_user = login(client, "C777", "wrong-password")
    for r in (wrong_pw, no_user):
        assert r.status_code == 401
        assert r.json() == {"error": {"code": "AUTH_FAILED", "message": "IDまたはパスワードが正しくありません"}}


# --- T-007 連続失敗ロック（暫定5回）---
def test_T007_four_failures_not_locked(client):
    for _ in range(4):
        assert login(client, password="wrong-password").status_code == 401
    assert login(client).status_code == 200


def test_T007_fifth_failure_locks(client, db):
    for _ in range(5):
        assert login(client, password="wrong-password").status_code == 401
    r = login(client)  # 正しい値でもログインできない
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "AUTH_FAILED"
    assert db.get(Cashier, "C001").locked_until is not None


def test_T007_lock_expires(client, set_now):
    for _ in range(5):
        login(client, password="wrong-password")
    set_now(later(minutes=15))
    assert login(client).status_code == 200


def test_T007_success_resets_counter(client, db):
    for _ in range(4):
        login(client, password="wrong-password")
    assert login(client).status_code == 200
    db.expire_all()
    assert db.get(Cashier, "C001").failed_login_count == 0


# --- T-008（API側）未ログインで保護 API は 401 ---
def test_T008_me_requires_login(anon_client):
    r = anon_client.get("/api/auth/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


# --- T-048〜T-050 セッション検証 ---
def test_T048_expired_session(auth_client, set_now):
    set_now(later(hours=9))
    assert auth_client.get("/api/auth/me").status_code == 401


def test_T049_valid_session_resolves_cashier(auth_client):
    assert auth_client.get("/api/auth/me").json()["cashier_id"] == "C001"


def test_T050_no_cookie(anon_client):
    assert anon_client.get("/api/products/4900000000011").status_code == 401


def test_T050_forged_cookie(anon_client):
    anon_client.cookies.set("pos_session", "forged-value", domain="testserver")
    assert anon_client.get("/api/auth/me").status_code == 401


# --- T-051 ログアウト ---
def test_T051_logout(auth_client, db):
    raw = auth_client.cookies["pos_session"]
    r = auth_client.post("/api/auth/logout")
    assert r.status_code == 204
    assert 'pos_session=""' in r.headers["set-cookie"] or "Max-Age=0" in r.headers["set-cookie"]
    assert db.get(Session, hash_session_id(raw)) is None
    # Cookie を手元に残していても失効済み
    auth_client.cookies.set("pos_session", raw, domain="testserver")
    assert auth_client.get("/api/auth/me").status_code == 401


# --- T-052 有効期限の境界（暫定8時間、8:00ちょうどで失効）---
@pytest.mark.parametrize("minutes,expected", [(7 * 60 + 59, 200), (8 * 60, 401), (8 * 60 + 1, 401)])
def test_T052_session_ttl_boundary(auth_client, set_now, minutes, expected):
    set_now(later(minutes=minutes))
    assert auth_client.get("/api/auth/me").status_code == expected


def test_disabled_after_login_is_rejected(auth_client, db):
    db.execute(update(Cashier).where(Cashier.cashier_id == "C001").values(is_active=False))
    db.commit()
    assert auth_client.get("/api/auth/me").status_code == 401


def test_multiple_terminals_same_cashier(client):
    """設計14章 No.5：同一担当者の複数端末ログインは許可（暫定）。"""
    from tests.conftest import make_client
    with make_client() as other:
        assert login(client).status_code == 200
        assert login(other).status_code == 200
        assert client.get("/api/auth/me").status_code == 200
        assert other.get("/api/auth/me").status_code == 200


# --- T-068 認証ログにパスワード・Cookie値が出ない ---
def test_T068_auth_log_contents(client, caplog):
    caplog.set_level(logging.INFO, logger="pos")
    login(client, password="wrong-password")
    r = login(client)
    raw = r.cookies["pos_session"]
    auth_records = [rec for rec in caplog.records if rec.name == "pos.auth"]
    assert [rec.result for rec in auth_records] == ["failure", "success"]
    assert all(rec.cashier_id == "C001" and rec.ip for rec in auth_records)
    full = caplog.text + "".join(str(rec.__dict__) for rec in caplog.records)
    assert PASSWORD not in full and "wrong-password" not in full and raw not in full


def test_csrf_header_required(anon_client):
    r = anon_client.post("/api/auth/login", json={"cashier_id": "C001", "password": PASSWORD},
                         headers={"X-POS-Request": ""})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "CSRF_REJECTED"
