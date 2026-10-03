from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession

from app.models.db_models import Cashier, Session


def get_for_update(db: DbSession, cashier_id: str) -> Cashier | None:
    # 失敗回数の加算が同時ログインで競合しないよう行ロックを取る
    return db.execute(select(Cashier).where(Cashier.cashier_id == cashier_id).with_for_update()).scalar_one_or_none()


def add_session(db: DbSession, session_id_hash: str, cashier_id: str, now: datetime, expires_at: datetime) -> None:
    db.add(Session(session_id_hash=session_id_hash, cashier_id=cashier_id, created_at=now, expires_at=expires_at))


def get_session(db: DbSession, session_id_hash: str) -> Session | None:
    return db.get(Session, session_id_hash)


def delete_session(db: DbSession, session_id_hash: str) -> None:
    db.execute(delete(Session).where(Session.session_id_hash == session_id_hash))


def delete_expired_sessions(db: DbSession, cashier_id: str, now: datetime) -> None:
    db.execute(delete(Session).where(Session.cashier_id == cashier_id, Session.expires_at <= now))
