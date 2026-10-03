from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session as DbSession

from app.models.db_models import TaxRate


def find_effective(db: DbSession, sales_mode: str, on: date) -> TaxRate | None:
    """on の日に有効な行のうち effective_from が最も新しいものを返す（設計6.3 の優先ルール）。"""
    return db.execute(
        select(TaxRate)
        .where(
            TaxRate.sales_mode == sales_mode,
            TaxRate.effective_from <= on,
            or_(TaxRate.effective_to.is_(None), TaxRate.effective_to >= on),
        )
        .order_by(TaxRate.effective_from.desc(), TaxRate.tax_rate_id.desc())
        .limit(1)
    ).scalar_one_or_none()


def list_by_mode(db: DbSession, sales_mode: str) -> list[TaxRate]:
    return list(
        db.execute(select(TaxRate).where(TaxRate.sales_mode == sales_mode).order_by(TaxRate.effective_from)).scalars()
    )
