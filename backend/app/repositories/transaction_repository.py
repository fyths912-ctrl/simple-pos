from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.models.db_models import Transaction, TransactionItem


def find_by_idempotency_key(db: DbSession, key: str) -> Transaction | None:
    return db.execute(select(Transaction).where(Transaction.idempotency_key == key)).scalar_one_or_none()


def insert_header(db: DbSession, header: Transaction) -> Transaction:
    db.add(header)
    db.flush()  # AUTO_INCREMENT の transaction_id を確定させる
    return header


def insert_items(db: DbSession, items: list[TransactionItem]) -> None:
    db.add_all(items)
    db.flush()
