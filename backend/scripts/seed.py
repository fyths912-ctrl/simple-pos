"""開発・テスト用の初期データ投入（テスト設計書 1.5）。

  python -m scripts.seed            # 既存データがあれば何もしない
  python -m scripts.seed --reset    # マスタ・取引を消して入れ直す（開発環境専用）

注意：ここのパスワードは開発用の固定値。本番の担当者は別手順で登録すること。
"""
import argparse
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, select

from app.config import get_settings
from app.core.security import hash_password
from app.db.engine import SessionFactory, init_engine
from app.models.db_models import Cashier, Member, Product, Session, TaxRate, Transaction, TransactionItem

DEV_PASSWORD = "pos-dev-pass"  # 開発用（8文字以上）

PRODUCTS = [
    ("4900000000011", "カレーライス", 850, True),
    ("4900000000028", "オムライス", 900, True),
    ("4900000000035", "ハンバーグ定食", 1200, True),
    ("4900000000042", "唐揚げ定食", 1000, True),
    ("4900000000059", "ナポリタン", 880, True),
    ("4900000000066", "ミックスサラダ", 450, True),
    ("4900000000073", "コーンスープ", 300, True),
    ("4900000000080", "アイスコーヒー", 350, True),
    ("4900000000097", "プリン", 380, True),
    ("4900000000103", "季節のパフェ（販売終了）", 780, False),  # 無効化商品
]

MEMBERS = [
    ("M000123", "山田 太郎", "090-0000-0001", "大阪府大阪市北区1-1", "男性", 42, True),
    ("M000124", "佐藤 花子", "090-0000-0002", "大阪府大阪市中央区2-2", "女性", 35, True),
    ("M000125", "鈴木 一郎", "090-0000-0003", "大阪府吹田市3-3", "男性", 28, True),
    ("M000900", "高橋 退会", "090-0000-0009", "大阪府堺市9-9", "女性", 50, False),  # 退会会員
]

CASHIERS = [
    ("C001", "山田", True),
    ("C002", "田中", True),
    ("C099", "無効 担当", False),  # 無効化担当者
]

TAX_RATES = [
    ("DINE_IN", Decimal("0.1000"), date(2026, 1, 1)),
    ("TAKEOUT", Decimal("0.0800"), date(2026, 1, 1)),
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="既存データを削除してから投入（開発専用）")
    args = parser.parse_args()

    init_engine(get_settings())
    with SessionFactory() as db:
        if args.reset:
            for model in (TransactionItem, Transaction, Session, TaxRate, Cashier, Member, Product):
                db.execute(delete(model))
            db.commit()
        elif db.execute(select(Product).limit(1)).first():
            print("seed: データが既にあるためスキップしました（入れ直す場合は --reset）")
            return

        db.add_all(Product(product_code=c, product_name=n, unit_price=p, is_active=a) for c, n, p, a in PRODUCTS)
        db.add_all(
            Member(member_id=i, name=n, phone=ph, address=ad, gender=g, age=ag, is_active=a)
            for i, n, ph, ad, g, ag, a in MEMBERS
        )
        pw_hash = hash_password(DEV_PASSWORD)
        db.add_all(Cashier(cashier_id=i, cashier_name=n, password_hash=pw_hash, is_active=a) for i, n, a in CASHIERS)
        db.add_all(TaxRate(sales_mode=m, rate=r, effective_from=f, rounding_method="FLOOR") for m, r, f in TAX_RATES)
        db.commit()
    print(f"seed: 投入しました（担当者 C001 / C002、開発用パスワード: {DEV_PASSWORD}）")


if __name__ == "__main__":
    main()
