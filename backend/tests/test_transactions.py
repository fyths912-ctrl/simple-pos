"""購入確定（F-003 / F-005 / F-006 / F-007 / NF-002、設計8.6/11.3）"""
import threading
import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text, update

from app.config import get_settings
from app.db.engine import SessionFactory
from app.models.db_models import Product, TaxRate, Transaction, TransactionItem
from app.models.schemas import TransactionCreate
from app.repositories import transaction_repository
from app.services import transaction_service
from tests.conftest import PASSWORD, FIXED_NOW, P_CURRY, P_INACTIVE, P_OMU, P_SALAD, P_UNKNOWN


def body(items=None, member_id=None, sales_mode="DINE_IN", key=None, **extra):
    return {
        "member_id": member_id, "sales_mode": sales_mode,
        "idempotency_key": key or str(uuid.uuid4()),
        "items": items if items is not None else [{"product_code": P_CURRY, "quantity": 2}, {"product_code": P_SALAD, "quantity": 1}],
        **extra,
    }


def count(db, model):
    db.rollback()  # REPEATABLE READ のスナップショットを捨てて最新を読む
    return db.scalar(select(func.count()).select_from(model))


# --- T-036 正常系：ヘッダ1行＋明細N行、スナップショット ---
def test_T036_create_transaction(auth_client, db):
    r = auth_client.post("/api/transactions", json=body())
    assert r.status_code == 201, r.text
    data = r.json()
    # 850×2 + 450×1 = 2150、税 215、税込 2365
    assert (data["subtotal_excl_tax"], data["tax_amount"], data["total_incl_tax"]) == (2150, 215, 2365)
    assert data["transaction_id"].startswith("T20260915")
    assert data["transaction_at"] == "2026-09-15T12:00:00+09:00"

    t = db.scalar(select(Transaction))
    assert (t.cashier_id, t.sales_mode, t.member_id, t.transaction_at) == ("C001", "DINE_IN", None, FIXED_NOW)
    items = db.scalars(select(TransactionItem).order_by(TransactionItem.line_no)).all()
    assert [(i.product_code, i.product_name_snapshot, i.unit_price_snapshot, i.quantity, i.tax_rate_snapshot)
            for i in items] == [
        (P_CURRY, "カレーライス", 850, 2, Decimal("0.1000")),
        (P_SALAD, "ミックスサラダ", 450, 1, Decimal("0.1000")),
    ]
    assert sum(i.line_tax for i in items) == t.tax_amount
    assert all(i.line_total == i.line_subtotal + i.line_tax for i in items)


# --- T-014/T-041 会員あり／非会員 ---
def test_T041_member_and_non_member(auth_client, db):
    assert auth_client.post("/api/transactions", json=body(member_id="M000123")).status_code == 201
    assert auth_client.post("/api/transactions", json=body(member_id=None)).status_code == 201
    rows = db.scalars(select(Transaction.member_id).order_by(Transaction.transaction_id)).all()
    assert rows == ["M000123", None]


# --- T-015/T-017 取引区分は送信された値が適用される ---
def test_T015_sales_mode_takeout_uses_8_percent(auth_client):
    r = auth_client.post("/api/transactions", json=body(sales_mode="TAKEOUT"))
    assert r.json()["tax_amount"] == 172  # 2150 × 8% = 172


# --- T-016 取引区分未選択 ---
@pytest.mark.parametrize("mode", [None, "", "DELIVERY"])
def test_T016_sales_mode_required(auth_client, db, mode):
    r = auth_client.post("/api/transactions", json=body(sales_mode=mode))
    assert r.status_code == 422
    assert count(db, Transaction) == 0


# --- T-031 空カート ---
def test_T031_empty_cart(auth_client, db):
    r = auth_client.post("/api/transactions", json=body(items=[]))
    assert r.status_code == 400
    assert r.json() == {"error": {"code": "EMPTY_CART", "message": "商品を1件以上追加してください。"}}
    assert count(db, Transaction) == 0


# --- T-032 存在しない会員 ---
@pytest.mark.parametrize("member_id", ["M999999", "M000900"])
def test_T032_unknown_member(auth_client, db, member_id):
    r = auth_client.post("/api/transactions", json=body(member_id=member_id))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "MEMBER_NOT_FOUND"
    assert count(db, Transaction) == 0


# --- T-033 商品の消失 ---
@pytest.mark.parametrize("code", [P_UNKNOWN, P_INACTIVE])
def test_T033_product_gone(auth_client, db, code):
    r = auth_client.post("/api/transactions", json=body(items=[{"product_code": P_CURRY, "quantity": 1},
                                                                {"product_code": code, "quantity": 1}]))
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "PRODUCT_CHANGED_OR_NOT_FOUND"
    assert count(db, Transaction) == 0 and count(db, TransactionItem) == 0


def test_T033_product_disabled_after_search(auth_client, db):
    assert auth_client.get(f"/api/products/{P_OMU}").status_code == 200
    db.execute(update(Product).where(Product.product_code == P_OMU).values(is_active=False))
    db.commit()
    r = auth_client.post("/api/transactions", json=body(items=[{"product_code": P_OMU, "quantity": 1}]))
    assert r.status_code == 409


# --- T-034 単価改ざん耐性 ---
def test_T034_client_prices_ignored(auth_client, db):
    tampered = body(
        items=[{"product_code": P_CURRY, "quantity": 1, "unit_price": 1, "line_total": 1}],
        subtotal_excl_tax=1, total_incl_tax=1, cashier_id="C002",
    )
    r = auth_client.post("/api/transactions", json=tampered)
    assert r.status_code == 201
    assert r.json()["subtotal_excl_tax"] == 850
    t = db.scalar(select(Transaction))
    assert t.cashier_id == "C001"  # セッションの担当者


# --- T-035/T-038 冪等性 ---
def test_T035_same_key_returns_same_result(auth_client, db):
    key = str(uuid.uuid4())
    r1 = auth_client.post("/api/transactions", json=body(key=key))
    r2 = auth_client.post("/api/transactions", json=body(key=key))
    assert r1.status_code == r2.status_code == 201
    assert r1.json() == r2.json()
    assert count(db, Transaction) == 1
    r3 = auth_client.post("/api/transactions", json=body())
    assert r3.json()["transaction_id"] != r1.json()["transaction_id"]
    assert count(db, Transaction) == 2


def test_T038_concurrent_same_key_single_row(db):
    """確定ボタンの連打で同じキーが同時に届いても1件だけ保存される。"""
    key = str(uuid.uuid4())
    req = TransactionCreate.model_validate(body(key=key))
    results, errors = [], []
    barrier = threading.Barrier(5)

    def worker():
        with SessionFactory() as s:
            barrier.wait()
            try:
                results.append(transaction_service.create_transaction(s, get_settings(), "C001", req).transaction_id)
            except Exception as e:  # pragma: no cover
                errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors
    assert len(set(results)) == 1
    assert count(db, Transaction) == 1


# --- T-037 明細 INSERT 失敗で全体 ROLLBACK ---
def test_T037_item_insert_failure_rolls_back(auth_client, db, monkeypatch):
    original = transaction_repository.insert_items

    def broken(session, items):
        items[-1].quantity = 0  # CHECK 制約違反で DB に拒否させる
        return original(session, items)

    monkeypatch.setattr(transaction_repository, "insert_items", broken)
    r = auth_client.post("/api/transactions", json=body())
    assert r.status_code == 500
    assert r.json() == {"error": {"code": "TRANSACTION_SAVE_FAILED", "message": "購入を確定できませんでした。再度お試しください。"}}
    assert count(db, Transaction) == 0 and count(db, TransactionItem) == 0


def test_T037_retry_after_failure_succeeds(auth_client, db, monkeypatch):
    key = str(uuid.uuid4())
    original = transaction_repository.insert_items
    monkeypatch.setattr(transaction_repository, "insert_items",
                        lambda s, items: (_ for _ in ()).throw(__import__("sqlalchemy").exc.OperationalError("x", {}, Exception())))
    assert auth_client.post("/api/transactions", json=body(key=key)).status_code == 500
    monkeypatch.setattr(transaction_repository, "insert_items", original)
    assert auth_client.post("/api/transactions", json=body(key=key)).status_code == 201
    assert count(db, Transaction) == 1


# --- T-028（API）税率なし ---
def test_tax_rate_missing_returns_500(auth_client, db):
    db.execute(text("DELETE FROM tax_rates WHERE sales_mode='TAKEOUT'"))
    db.commit()
    r = auth_client.post("/api/transactions", json=body(sales_mode="TAKEOUT"))
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "TAX_RATE_NOT_CONFIGURED"


# --- T-039 税率適用開始日の境界（時刻依存）---
@pytest.mark.parametrize("now_utc,expected_tax", [
    (datetime(2026, 9, 30, 14, 59, 59), 215),  # JST 9/30 23:59:59（前日）→ 旧 10%
    (datetime(2026, 9, 30, 15, 0, 0), 258),    # JST 10/1 0:00（当日）→ 新 12%
])
def test_T039_effective_from_boundary(client, db, set_now, now_utc, expected_tax):
    db.add(TaxRate(sales_mode="DINE_IN", rate=Decimal("0.1200"), effective_from=date(2026, 10, 1), rounding_method="FLOOR"))
    db.commit()
    set_now(now_utc)
    assert client.post("/api/auth/login", json={"cashier_id": "C001", "password": PASSWORD}).status_code == 200
    r = client.post("/api/transactions", json=body())
    assert r.status_code == 201
    assert r.json()["tax_amount"] == expected_tax


# --- T-040 過去取引のスナップショット固定 ---
def test_T040_snapshots_do_not_change(auth_client, db):
    assert auth_client.post("/api/transactions", json=body()).status_code == 201
    db.execute(update(Product).where(Product.product_code == P_CURRY).values(unit_price=999, product_name="新カレー"))
    db.execute(update(TaxRate).values(rate=Decimal("0.2000")))
    db.commit()
    db.expire_all()
    item = db.scalar(select(TransactionItem).where(TransactionItem.product_code == P_CURRY))
    assert (item.unit_price_snapshot, item.product_name_snapshot, item.tax_rate_snapshot) == (850, "カレーライス", Decimal("0.1000"))
    assert db.scalar(select(Transaction.total_incl_tax)) == 2365


# --- T-042 未認証 ---
def test_T042_requires_auth(anon_client, db):
    r = anon_client.post("/api/transactions", json=body())
    assert r.status_code == 401
    assert count(db, Transaction) == 0


# --- T-025（サーバー側）数量の上限 99 ---
@pytest.mark.parametrize("qty,expected", [(0, 422), (1, 201), (5, 201), (99, 201), (100, 422)])
def test_T025_quantity_boundary(auth_client, qty, expected):
    r = auth_client.post("/api/transactions", json=body(items=[{"product_code": P_CURRY, "quantity": qty}]))
    assert r.status_code == expected


def test_duplicate_lines_are_merged(auth_client, db):
    r = auth_client.post("/api/transactions", json=body(items=[{"product_code": P_CURRY, "quantity": 1},
                                                                {"product_code": P_CURRY, "quantity": 2}]))
    assert r.status_code == 201
    assert db.scalar(select(TransactionItem.quantity)) == 3
    over = auth_client.post("/api/transactions", json=body(items=[{"product_code": P_CURRY, "quantity": 60},
                                                                   {"product_code": P_CURRY, "quantity": 40}]))
    assert over.status_code == 422


# --- T-073 取引ID採番：同時アクセスでも重複しない ---
def test_T073_transaction_numbers_unique_under_concurrency(db):
    n = 8
    barrier = threading.Barrier(n)
    ids, errors = [], []

    def worker():
        req = TransactionCreate.model_validate(body())
        with SessionFactory() as s:
            barrier.wait()
            try:
                ids.append(transaction_service.create_transaction(s, get_settings(), "C001", req).transaction_id)
            except Exception as e:  # pragma: no cover
                errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(n)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors
    assert len(ids) == len(set(ids)) == n
    assert all(i.startswith("T20260915") for i in ids)
    assert count(db, Transaction) == n
