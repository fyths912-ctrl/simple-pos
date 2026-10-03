"""税率の追加（設計7.4 の管理運用。コード改修なしで税率を切り替える：F-008）。

例）2027-04-01 から店内飲食を 12% にする
  python -m scripts.add_tax_rate --sales-mode DINE_IN --rate 0.12 --from 2027-04-01

同一取引区分で有効期間が重複する登録は拒否する。現行行（終了日なし）は新行の前日で締める。
"""
import argparse
from datetime import date
from decimal import Decimal

from app.config import get_settings
from app.db.engine import SessionFactory, init_engine
from app.services.tax_service import register_tax_rate


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--sales-mode", required=True, choices=["DINE_IN", "TAKEOUT"])
    p.add_argument("--rate", required=True, type=Decimal, help="例: 0.10")
    p.add_argument("--from", dest="effective_from", required=True, type=date.fromisoformat)
    p.add_argument("--to", dest="effective_to", type=date.fromisoformat)
    p.add_argument("--rounding", default="FLOOR", choices=["FLOOR", "HALF_UP", "CEIL"])
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    init_engine(get_settings())
    with SessionFactory() as db:
        try:
            row = register_tax_rate(db, a.sales_mode, a.rate, a.effective_from, a.rounding, a.effective_to)
        except ValueError as e:
            raise SystemExit(f"登録できません: {e}")
        if a.dry_run:
            db.rollback()
            print("dry-run: 問題なし（登録はしていません）")
        else:
            db.commit()
            print(f"登録しました: id={row.tax_rate_id} {row.sales_mode} {row.rate} {row.effective_from}〜")


if __name__ == "__main__":
    main()
