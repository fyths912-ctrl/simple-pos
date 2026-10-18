import ssl
"""DB 接続プール（設計11.2／NF-004）。

Engine はアプリ起動時（lifespan）に1つだけ生成し、全リクエストで使い回す。
"""
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings

_engine: Engine | None = None
SessionFactory = sessionmaker(autoflush=False, expire_on_commit=False)


def build_engine(settings: Settings) -> Engine:
connect_args: dict = {
    "ssl": ssl.create_default_context(
        cafile=settings.db_ssl_ca
    )
}  # Azure MySQL は TLS 必須
    return create_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,  # 切断済み接続を利用前に検知
        pool_recycle=settings.db_pool_recycle_seconds,
        connect_args=connect_args,
    )


def init_engine(settings: Settings) -> Engine:
    global _engine
    if _engine is None:
        _engine = build_engine(settings)
        SessionFactory.configure(bind=_engine)
    return _engine


def get_engine() -> Engine | None:
    return _engine


def dispose_engine() -> None:
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None
