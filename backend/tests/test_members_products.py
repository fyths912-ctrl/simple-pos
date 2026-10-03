"""会員照会（F-005 / NF-008）・商品検索（F-001）"""
from urllib.parse import quote

import pytest

from tests.conftest import P_CURRY, P_INACTIVE, P_UNKNOWN


# --- T-010 会員ID 入力検証（暫定書式 M+6桁）---
@pytest.mark.parametrize("member_id,expected", [
    ("M000123", 200),   # 正常値
    ("M12345", 422),    # 1桁不足
    ("M1234567", 422),  # 1桁超過
    ("m000123", 422),   # 小文字
    ("X000123", 422),
])
def test_T010_member_id_format(auth_client, member_id, expected):
    assert auth_client.get(f"/api/members/{member_id}").status_code == expected


# --- T-011 登録済み会員：表示名だけ返す ---
def test_T011_member_found_minimal_fields(auth_client):
    r = auth_client.get("/api/members/M000123")
    assert r.status_code == 200
    assert r.json() == {"member_id": "M000123", "display_name": "山田 太郎"}
    for pii in ("090-0000-0001", "大阪府", "男性", "42"):
        assert pii not in r.text


# --- T-012 未登録・退会済み ---
@pytest.mark.parametrize("member_id", ["M999999", "M000900"])
def test_T012_member_not_found(auth_client, member_id):
    r = auth_client.get(f"/api/members/{member_id}")
    assert r.status_code == 404
    assert r.json() == {"error": {
        "code": "MEMBER_NOT_FOUND", "message": "会員IDが見つかりません。再入力するか、非会員を選択してください。"}}


# --- T-013 未認証 ---
def test_T013_members_requires_auth(anon_client):
    r = anon_client.get("/api/members/M000123")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


# --- T-018 商品コード入力検証 ---
@pytest.mark.parametrize("code,expected", [
    (P_CURRY, 200),               # 13桁
    ("490000000001", 422),        # 12桁
    ("49000000000111", 422),      # 14桁
    ("49000000000A1", 422),       # 英字混在
    ("４９00000000011", 422),      # 全角数字混在
])
def test_T018_product_code_validation(auth_client, code, expected):
    r = auth_client.get(f"/api/products/{quote(code)}")
    assert r.status_code == expected
    if expected == 422:
        assert r.json()["error"]["code"] == "VALIDATION_ERROR"


# --- T-019 登録済み（前後空白は除去）---
@pytest.mark.parametrize("code", [P_CURRY, f" {P_CURRY} ", f"\t{P_CURRY}"])
def test_T019_product_found(auth_client, code):
    r = auth_client.get(f"/api/products/{quote(code)}")
    assert r.status_code == 200
    assert r.json() == {"product_code": P_CURRY, "product_name": "カレーライス", "unit_price": 850}


# --- T-020 未登録・無効化 ---
@pytest.mark.parametrize("code", [P_UNKNOWN, P_INACTIVE])
def test_T020_product_not_found(auth_client, code):
    r = auth_client.get(f"/api/products/{code}")
    assert r.status_code == 404
    assert r.json() == {"error": {
        "code": "PRODUCT_NOT_FOUND", "message": "商品がマスタ未登録です。商品コードを確認してください。"}}


# --- T-021 未認証 ---
def test_T021_products_requires_auth(anon_client):
    assert anon_client.get(f"/api/products/{P_CURRY}").status_code == 401


# --- T-058 SQL インジェクション試行 ---
@pytest.mark.parametrize("payload", ["' OR '1'='1", "1; DROP TABLE products;--", "4900000000011' --"])
def test_T058_sql_injection_is_harmless(auth_client, db, payload):
    r1 = auth_client.get(f"/api/products/{quote(payload, safe='')}")
    r2 = auth_client.get(f"/api/members/{quote(payload, safe='')}")
    assert r1.status_code in (404, 422) and r2.status_code in (404, 422)
    # テーブルは無事
    assert auth_client.get(f"/api/products/{P_CURRY}").status_code == 200


def test_T058_login_injection(client):
    r = client.post("/api/auth/login", json={"cashier_id": "C001' OR '1'='1", "password": "x' OR '1'='1"})
    assert r.status_code in (401, 422)
