"""ルーター共通の依存関数。"""
from fastapi import Depends, Request
from sqlalchemy.orm import Session as DbSession

from app.config import Settings, get_settings
from app.core.errors import AppError
from app.db.session import get_db
from app.models.db_models import Cashier
from app.services import auth_service

CSRF_HEADER = "X-POS-Request"


def current_cashier(request: Request, db: DbSession = Depends(get_db), settings: Settings = Depends(get_settings)) -> Cashier:
    """認証必須 API の入口。画面側の制御に頼らず API で必ず検証する（NF-007）。"""
    return auth_service.resolve_session(db, request.cookies.get(settings.session_cookie_name))


def require_csrf_header(request: Request) -> None:
    """状態を変える POST に独自ヘッダーを要求する（CSRF 対策の多層防御）。

    独自ヘッダー付きのクロスオリジン要求はプリフライトが必要になり、
    許可 Origin 以外からは送信できないため、SameSite Cookie と合わせて CSRF を防ぐ。
    """
    if request.headers.get(CSRF_HEADER) != "1":
        raise AppError(403, "CSRF_REJECTED", "不正なリクエストです")


def client_ip(request: Request) -> str | None:
    """App Service 配下では X-Forwarded-For の先頭が接続元（"IPv4:port" 形式のことがある）。"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first.count(":") == 1:  # IPv4:port
            first = first.split(":")[0]
        return first
    return request.client.host if request.client else None
