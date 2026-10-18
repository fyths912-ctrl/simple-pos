import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.db.engine import get_engine

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/api/health")
def health():
    """死活監視用。接続先などの内部情報は返さない。"""
    engine = get_engine()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "db": "ok"}
    except Exception as exc:
        db_error = exc.orig if isinstance(exc, DBAPIError) else exc
        error_args = getattr(db_error, "args", ())
        error_code = (
            error_args[0]
            if error_args and isinstance(error_args[0], int)
            else "unknown"
        )
        logger.error(
            "Database health check failed: %s, mysql_code=%s",
            type(exc).__name__,
            error_code,
        )
        return JSONResponse(
            status_code=503,
            content={"status": "ng", "db": "ng"},
        )
