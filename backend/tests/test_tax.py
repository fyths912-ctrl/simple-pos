"""税率取得・税計算・税率登録（F-007 / F-008、設計7章）"""
from datetime import date
from decimal import Decimal

import pytest

from app.core.errors import AppError
from app.models.db_models import TaxRate
from app.services import tax_service


# --- T-027 税率取得 ---
@pytest.mark.parametrize("mode,rate", [("DINE_IN", Decimal("0.1000")), ("TAKEOUT", Decimal("0.0800"))])
def test_T027_effective_rate(db, mode, rate):
    assert tax_service.get_effective_rate(db, mode, date(2026, 9, 15)).rate == rate


# --- T-028 税率未設定 ---
def test_T028_rate_not_configured(db):
    with pytest.raises(AppError) as e:
        tax_service.get_effective_rate(db, "DINE_IN", date(2025, 12, 31))  # 適用開始前
    assert (e.value.status_code, e.value.code) == (500, "TAX_RATE_NOT_CONFIGURED")


def test_T028_rate_ended(db):
    db.query(TaxRate).filter_by(sales_mode="TAKEOUT").update({"effective_to": date(2026, 9, 1)})
    db.commit()
    with pytest.raises(AppError):
        tax_service.get_effective_rate(db, "TAKEOUT", date(2026, 9, 15))


# --- T-029 重複行は effective_from が新しい方を優先 ---
def test_T029_newest_effective_from_wins(db):
    db.add(TaxRate(sales_mode="DINE_IN", rate=Decimal("0.1200"), effective_from=date(2026, 9, 1), rounding_method="FLOOR"))
    db.commit()
    assert tax_service.get_effective_rate(db, "DINE_IN", date(2026, 9, 15)).rate == Decimal("0.1200")
    assert tax_service.get_effective_rate(db, "DINE_IN", date(2026, 8, 31)).rate == Decimal("0.1000")


# --- T-030 税計算 ---
def test_T030_basic_example():
    # 設計8.6 の例：税抜 2300 → 税額 230 → 税込 2530
    b = tax_service.calculate([1700, 600], Decimal("0.1000"), "FLOOR")
    assert (b.subtotal_excl_tax, b.tax_amount, b.total_incl_tax) == (2300, 230, 2530)
    assert sum(b.line_taxes) == b.tax_amount


@pytest.mark.parametrize("method,expected", [("FLOOR", 100), ("HALF_UP", 101), ("CEIL", 101)])
def test_T030_rounding_exact_half(method, expected):
    # 1005 × 10% = 100.5 円（ちょうど .5）
    assert tax_service.calculate([1005], Decimal("0.1000"), method).tax_amount == expected


@pytest.mark.parametrize("method", ["FLOOR", "HALF_UP", "CEIL"])
def test_T030_rounding_no_fraction(method):
    assert tax_service.calculate([1000], Decimal("0.1000"), method).tax_amount == 100


@pytest.mark.parametrize("method,expected", [("FLOOR", 80), ("HALF_UP", 80), ("CEIL", 81)])
def test_T030_rounding_takeout(method, expected):
    # 8% は整数円の税抜額でちょうど .5 にならないため、端数 .48 で確認（1006 × 8% = 80.48）
    assert tax_service.calculate([1006], Decimal("0.0800"), method).tax_amount == expected


def test_T030_max_configuration_no_overflow():
    # 99個 × 100行 × 単価 9,999,999 円
    lines = [99 * 9_999_999] * 100
    b = tax_service.calculate(lines, Decimal("0.1000"), "FLOOR")
    assert b.subtotal_excl_tax == 98_999_990_100
    assert b.tax_amount == 9_899_999_010
    assert b.total_incl_tax == b.subtotal_excl_tax + b.tax_amount
    assert sum(b.line_taxes) == b.tax_amount


def test_line_tax_allocation_sums_to_header():
    b = tax_service.calculate([333, 333, 334], Decimal("0.0800"), "FLOOR")  # 80
    assert sum(b.line_taxes) == b.tax_amount == 80
    assert all(t >= 0 for t in b.line_taxes)


def test_zero_subtotal():
    assert tax_service.calculate([0], Decimal("0.1"), "FLOOR").line_taxes == [0]


# --- 税率登録（設計6.3：期間重複の防止）---
def test_register_closes_current_row(db):
    new = tax_service.register_tax_rate(db, "DINE_IN", Decimal("0.12"), date(2027, 4, 1))
    db.commit()
    rows = db.query(TaxRate).filter_by(sales_mode="DINE_IN").order_by(TaxRate.effective_from).all()
    assert rows[0].effective_to == date(2027, 3, 31) and rows[0].rate == Decimal("0.1000")
    assert rows[1].tax_rate_id == new.tax_rate_id and rows[1].effective_to is None


def test_register_rejects_overlap(db):
    tax_service.register_tax_rate(db, "DINE_IN", Decimal("0.12"), date(2027, 4, 1))
    db.commit()
    with pytest.raises(ValueError, match="重複"):
        tax_service.register_tax_rate(db, "DINE_IN", Decimal("0.15"), date(2027, 4, 1))
    with pytest.raises(ValueError, match="重複"):
        tax_service.register_tax_rate(db, "DINE_IN", Decimal("0.15"), date(2026, 6, 1), effective_to=date(2026, 6, 30))


@pytest.mark.parametrize("kwargs", [
    dict(sales_mode="DELIVERY", rate=Decimal("0.1")),
    dict(sales_mode="DINE_IN", rate=Decimal("10")),
    dict(sales_mode="DINE_IN", rate=Decimal("0.1"), rounding_method="BANKERS"),
])
def test_register_rejects_bad_values(db, kwargs):
    with pytest.raises(ValueError):
        tax_service.register_tax_rate(db, effective_from=date(2027, 1, 1), **kwargs)
