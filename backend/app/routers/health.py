from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db.engine import get_engine

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health():
    """死活監視用。接続先などの内部情報は返さない。"""
    engine = get_engine()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "db": "ok"}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "ng", "db": "ng"})
