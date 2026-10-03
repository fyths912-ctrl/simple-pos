from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session as DbSession

from app.config import Settings, get_settings
from app.core.deps import client_ip, current_cashier, require_csrf_header
from app.db.session import get_db
from app.models.db_models import Cashier
from app.models.schemas import CashierOut, LoginRequest, LoginResponse
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _cookie_args(settings: Settings) -> dict:
    return {
        "key": settings.session_cookie_name, "httponly": True, "secure": settings.cookie_secure,
        "samesite": settings.cookie_samesite, "path": "/",
    }


@router.post("/login", response_model=LoginResponse, dependencies=[Depends(require_csrf_header)])
def login(body: LoginRequest, request: Request, response: Response,
          db: DbSession = Depends(get_db), settings: Settings = Depends(get_settings)):
    cashier, raw_session_id = auth_service.login(db, settings, body.cashier_id, body.password, client_ip(request))
    response.set_cookie(value=raw_session_id, max_age=settings.session_ttl_minutes * 60, **_cookie_args(settings))
    return LoginResponse(cashier=CashierOut(cashier_id=cashier.cashier_id, cashier_name=cashier.cashier_name))


@router.post("/logout", status_code=204, dependencies=[Depends(require_csrf_header)])
def logout(request: Request, _: Cashier = Depends(current_cashier),
           db: DbSession = Depends(get_db), settings: Settings = Depends(get_settings)):
    auth_service.logout(db, request.cookies.get(settings.session_cookie_name))
    result = Response(status_code=204)
    result.delete_cookie(**_cookie_args(settings))
    return result


@router.get("/me", response_model=CashierOut)
def me(cashier: Cashier = Depends(current_cashier)):
    return CashierOut(cashier_id=cashier.cashier_id, cashier_name=cashier.cashier_name)
