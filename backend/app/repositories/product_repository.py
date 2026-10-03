from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.models.db_models import Product


def get_active(db: DbSession, product_code: str) -> Product | None:
    return db.execute(
        select(Product).where(Product.product_code == product_code, Product.is_active.is_(True))
    ).scalar_one_or_none()


def get_active_many(db: DbSession, product_codes: list[str]) -> dict[str, Product]:
    rows = db.execute(
        select(Product).where(Product.product_code.in_(product_codes), Product.is_active.is_(True))
    ).scalars()
    return {p.product_code: p for p in rows}
