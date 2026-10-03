"""消費税率の取得・税計算・税率登録（設計7章、F-007/F-008）。

税率はコードに持たず tax_rates テーブルから取得する。
1取引=1取引区分=1税率（設計14章 No.10）なので、税額は取引合計に対して1回だけ端数処理し、
明細の税額はその合計を税抜小計の比率で按分する（明細税額の合計＝取引の税額になる）。
"""
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session as DbSession

from app.core.errors import AppError
from app.models.db_models import ROUNDING_METHODS, SALES_MODES, TaxRate
from app.repositories import tax_rate_repository as repo

_ROUNDING = {"FLOOR": ROUND_FLOOR, "HALF_UP": ROUND_HALF_UP, "CEIL": ROUND_CEILING}


def get_effective_rate(db: DbSession, sales_mode: str, on: date) -> TaxRate:
    rate = repo.find_effective(db, sales_mode, on)
    if rate is None:
        raise AppError(500, "TAX_RATE_NOT_CONFIGURED", "税率が設定されていません。管理者に連絡してください。")
    return rate


def round_yen(amount: Decimal, rounding_method: str) -> int:
    if rounding_method not in _ROUNDING:
        raise ValueError(f"unknown rounding_method: {rounding_method}")
    return int(amount.quantize(Decimal("1"), rounding=_ROUNDING[rounding_method]))


@dataclass(frozen=True)
class TaxBreakdown:
    subtotal_excl_tax: int
    tax_amount: int
    total_incl_tax: int
    line_taxes: list[int]


def calculate(line_subtotals: list[int], rate: Decimal, rounding_method: str) -> TaxBreakdown:
    """税抜小計 → 税額 → 税込合計（設計7.3）。金額はすべて整数円。"""
    subtotal = sum(line_subtotals)
    tax = round_yen(Decimal(subtotal) * Decimal(rate), rounding_method)

    # 最大剰余法で按分（各明細の税額は0以上、合計は tax と一致）
    if subtotal == 0:
        line_taxes = [0] * len(line_subtotals)
    else:
        bases = [tax * s // subtotal for s in line_subtotals]
        remainders = [tax * s % subtotal for s in line_subtotals]
        rest = tax - sum(bases)
        for i in sorted(range(len(line_subtotals)), key=lambda i: (-remainders[i], i))[:rest]:
            bases[i] += 1
        line_taxes = bases
    return TaxBreakdown(subtotal, tax, subtotal + tax, line_taxes)


def register_tax_rate(
    db: DbSession, sales_mode: str, rate: Decimal, effective_from: date,
    rounding_method: str = "FLOOR", effective_to: date | None = None,
) -> TaxRate:
    """税率の追加（管理運用：scripts/add_tax_rate.py から使う）。

    同一 sales_mode で有効期間が重複する登録は拒否する（設計6.3）。
    ただし「終了日未設定の現行行」より後の開始日で登録する場合は、現行行の effective_to を
    新行の前日で締めてから追加する（税率・開始日など既存の値は書き換えない）。
    """
    if sales_mode not in SALES_MODES:
        raise ValueError("sales_mode は DINE_IN / TAKEOUT のいずれか")
    if rounding_method not in ROUNDING_METHODS:
        raise ValueError("rounding_method は FLOOR / HALF_UP / CEIL のいずれか")
    if not (Decimal("0") <= rate < Decimal("1")):
        raise ValueError("rate は 0 以上 1 未満（例: 0.1000）")
    if effective_to is not None and effective_to < effective_from:
        raise ValueError("effective_to は effective_from 以降")

    new_end = effective_to or date.max
    for row in repo.list_by_mode(db, sales_mode):
        row_end = row.effective_to or date.max
        overlaps = row.effective_from <= new_end and effective_from <= row_end
        if not overlaps:
            continue
        if row.effective_to is None and effective_to is None and row.effective_from < effective_from:
            row.effective_to = effective_from - timedelta(days=1)  # 現行行を締める
            continue
        raise ValueError(
            f"有効期間が既存の税率（id={row.tax_rate_id}, {row.effective_from}〜{row.effective_to or ''}）と重複します"
        )
    new_row = TaxRate(
        sales_mode=sales_mode, rate=rate, effective_from=effective_from,
        effective_to=effective_to, rounding_method=rounding_method,
    )
    db.add(new_row)
    db.flush()
    return new_row
