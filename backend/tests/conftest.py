"""テスト共通設定。

実 MySQL（Docker / CI のサービスコンテナ）に専用DB `pos_app_test` を作って実行する。
接続先は TEST_DATABASE_URL で変更できる。
"""
import os
from datetime import date, datetime, timedelta
from decimal import Decimal

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "mysql+pymysql://pos:pospass@127.0.0.1:3306/pos_app_test?charset=utf8mb4"
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.core import clock  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.engine import SessionFactory, init_engine  # noqa: E402
from app.models.db_models import Cashier, Member, Product, TaxRate  # noqa: E402

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASSWORD = "correct-pass-01"
TABLES = ["transaction_items", "transactions", "sessions", "tax_rates", "cashiers", "members", "products"]

# 固定の「現在時刻」（UTC）。JST では 2026-09-15 12:00
FIXED_NOW = datetime(2026, 9, 15, 3, 0, 0)

P_CURRY = "4900000000011"      # 850円
P_OMU = "4900000000028"        # 900円
P_SALAD = "4900000000066"      # 450円
P_INACTIVE = "4900000000103"   # 無効化商品
P_UNKNOWN = "4999999999999"    # 未登録


@pytest.fixture(scope="session", autouse=True)
def _database():
    url = make_url(TEST_DATABASE_URL)
    server = create_engine(url.set(database="mysql"))
    with server.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS `{url.database}`"))
        conn.execute(text(f"CREATE DATABASE `{url.database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin"))
    server.dispose()

    # マイグレーション自体もテスト対象にする
    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "alembic"))
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL.replace("%", "%%"))
    command.upgrade(cfg, "head")

    from app.config import get_settings
    init_engine(get_settings())
    yield


@pytest.fixture(scope="session")
def password_hash():
    return hash_password(PASSWORD)


@pytest.fixture(autouse=True)
def seed(password_hash, monkeypatch):
    monkeypatch.setattr(clock, "utcnow", lambda: FIXED_NOW)
    with SessionFactory() as db:
        db.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for t in TABLES:
            db.execute(text(f"TRUNCATE TABLE {t}"))
        db.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        db.add_all([
            Product(product_code=P_CURRY, product_name="カレーライス", unit_price=850, is_active=True),
            Product(product_code=P_OMU, product_name="オムライス", unit_price=900, is_active=True),
            Product(product_code=P_SALAD, product_name="ミックスサラダ", unit_price=450, is_active=True),
            Product(product_code=P_INACTIVE, product_name="販売終了品", unit_price=780, is_active=False),
            Member(member_id="M000123", name="山田 太郎", phone="090-0000-0001", address="大阪府大阪市北区1-1",
                   gender="男性", age=42, is_active=True),
            Member(member_id="M000900", name="高橋 退会", phone="090-0000-0009", address="大阪府堺市",
                   gender="女性", age=50, is_active=False),
            Cashier(cashier_id="C001", cashier_name="山田", password_hash=password_hash, is_active=True),
            Cashier(cashier_id="C002", cashier_name="田中", password_hash=password_hash, is_active=True),
            Cashier(cashier_id="C099", cashier_name="無効", password_hash=password_hash, is_active=False),
            TaxRate(sales_mode="DINE_IN", rate=Decimal("0.1000"), effective_from=date(2026, 1, 1), rounding_method="FLOOR"),
            TaxRate(sales_mode="TAKEOUT", rate=Decimal("0.0800"), effective_from=date(2026, 1, 1), rounding_method="FLOOR"),
        ])
        db.commit()
    yield


@pytest.fixture
def set_now(monkeypatch):
    def _set(dt: datetime):
        monkeypatch.setattr(clock, "utcnow", lambda: dt)
    return _set


@pytest.fixture
def db():
    with SessionFactory() as s:
        yield s


def make_client() -> TestClient:
    from app.main import app
    # https にしないと Secure Cookie が送られない
    return TestClient(app, base_url="https://testserver", headers={"X-POS-Request": "1"})


@pytest.fixture
def client():
    with make_client() as c:
        yield c


@pytest.fixture
def anon_client():
    """ログインしていないクライアント（未認証 API 直打ち用）。"""
    with make_client() as c:
        yield c


@pytest.fixture
def auth_client(client):
    r = client.post("/api/auth/login", json={"cashier_id": "C001", "password": PASSWORD})
    assert r.status_code == 200, r.text
    return client


def later(minutes: int = 0, hours: int = 0, days: int = 0) -> datetime:
    return FIXED_NOW + timedelta(minutes=minutes, hours=hours, days=days)
