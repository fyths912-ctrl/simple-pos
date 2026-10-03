from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.models.db_models import Member


def get_active(db: DbSession, member_id: str) -> Member | None:
    return db.execute(
        select(Member).where(Member.member_id == member_id, Member.is_active.is_(True))
    ).scalar_one_or_none()
