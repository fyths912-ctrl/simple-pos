"""業務エラーと共通エラー応答（設計8.1：{"error": {"code", "message"}}）。"""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("pos.error")


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(code)
        self.status_code = status_code
        self.code = code
        self.message = message


# 画面文言は設計12.1／9.2に合わせる
def unauthorized() -> AppError:
    return AppError(401, "UNAUTHORIZED", "セッションの有効期限が切れました。再度ログインしてください。")


def auth_failed() -> AppError:
    return AppError(401, "AUTH_FAILED", "IDまたはパスワードが正しくありません")


def error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse(status_code=exc.status_code, content=error_body(exc.code, exc.message))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        # 入力値そのもの（パスワード等）を応答・ログに含めない
        fields = sorted({".".join(str(p) for p in e.get("loc", [])[1:]) for e in exc.errors()})
        detail = ", ".join(f for f in fields if f)
        return JSONResponse(
            status_code=422,
            content=error_body("VALIDATION_ERROR", "入力形式が正しくありません" + (f": {detail}" if detail else "")),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(exc.status_code, "HTTP_ERROR")
        return JSONResponse(status_code=exc.status_code, content=error_body(code, "リクエストを処理できません"))

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception):
        # スタックトレースはサーバーログのみ（T-061）。ブラウザへは一般化した応答だけ返す。
        logger.exception("unhandled error request_id=%s", getattr(request.state, "request_id", "-"))
        return JSONResponse(status_code=500, content=error_body("INTERNAL_ERROR", "システムエラーが発生しました"))
