"""FastAPI エントリポイント。起動: uvicorn app.main:app"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging_setup import setup_logging
from app.core.middleware import RequestContextMiddleware
from app.db.engine import dispose_engine, init_engine
from app.routers import auth, health, members, products, transactions


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Engine（接続プール）は起動時に1つだけ作る（設計11.2／T-065）
    init_engine(get_settings())
    yield
    dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)

    if "*" in settings.cors_allow_origins:
        raise RuntimeError("CORS_ALLOW_ORIGINS に * は指定できません（credentials を使うため）")

    app = FastAPI(
        title="簡易POS API", version="1.0.0", lifespan=lifespan,
        docs_url=None, redoc_url=None, openapi_url=None,  # 本番で API 仕様を公開しない
    )
    register_error_handlers(app)
    if settings.cors_allow_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allow_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "X-POS-Request"],
        )
    app.add_middleware(RequestContextMiddleware, force_https=settings.force_https)

    for r in (auth.router, members.router, products.router, transactions.router, health.router):
        app.include_router(r)
    return app


app = create_app()
