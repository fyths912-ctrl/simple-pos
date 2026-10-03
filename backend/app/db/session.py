"""リクエスト単位の DB セッション。処理終了時に必ず close する（接続はプールへ返る）。"""
from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.db.engine import SessionFactory


def get_db() -> Iterator[Session]:
    db = SessionFactory()
    try:
        yield db
    finally:
        db.close()
