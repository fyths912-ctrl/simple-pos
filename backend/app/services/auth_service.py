"""ログイン・セッション検証（設計9.1/9.2、F-004、NF-005/NF-007）。"""
import logging
from datetime import timedelta

from sqlalchemy.orm import Session as DbSession

from app.config import Settings
from app.core import clock
from app.core.errors import AppError, auth_failed, unauthorized
from app.core.security import burn_verify_time, hash_session_id, new_session_id, verify_password
from app.models.db_models import Cashier
from app.repositories import cashier_repository as repo

auth_log = logging.getLogger("pos.auth")


def _log(cashier_id: str, success: bool, ip: str | None, reason: str = "") -> None:
    # 記録するのは cashier_id・成否・IP のみ。パスワード・Cookie 値は記録しない（12.2／T-068）
    auth_log.info(
        "login", extra={"cashier_id": cashier_id, "result": "success" if success else "failure", "ip": ip, "reason": reason}
    )


def login(db: DbSession, settings: Settings, cashier_id: str, password: str, ip: str | None) -> tuple[Cashier, str]:
    """認証に成功したら (担当者, 生のセッションID) を返す。"""
    now = clock.utcnow()
    cashier = repo.get_for_update(db, cashier_id)

    if cashier is None:
        burn_verify_time(password)
        db.rollback()
        _log(cashier_id, False, ip, "unknown_id")
        raise auth_failed()

    # ロック期限が過ぎていれば失敗回数をリセットしてから判定する
    if cashier.locked_until is not None and cashier.locked_until <= now:
        cashier.locked_until = None
        cashier.failed_login_count = 0

    if cashier.locked_until is not None:
        burn_verify_time(password)
        db.commit()
        _log(cashier_id, False, ip, "locked")
        # ロック中であることも ID 存在有無の手掛かりになるため、通常の認証失敗と同じ応答にする
        raise auth_failed()

    if not verify_password(password, cashier.password_hash):
        cashier.failed_login_count += 1
        if cashier.failed_login_count >= settings.login_lock_threshold:
            cashier.locked_until = now + timedelta(minutes=settings.login_lock_minutes)
        db.commit()
        _log(cashier_id, False, ip, "bad_password")
        raise auth_failed()

    if not cashier.is_active:
        db.commit()
        _log(cashier_id, False, ip, "disabled")
        raise AppError(403, "CASHIER_DISABLED", "この担当者IDは利用できません。管理者に確認してください。")

    cashier.failed_login_count = 0
    cashier.locked_until = None
    repo.delete_expired_sessions(db, cashier.cashier_id, now)
    raw_session_id = new_session_id()
    repo.add_session(
        db, hash_session_id(raw_session_id), cashier.cashier_id, now,
        now + timedelta(minutes=settings.session_ttl_minutes),
    )
    db.commit()
    _log(cashier_id, True, ip)
    return cashier, raw_session_id


def resolve_session(db: DbSession, raw_session_id: str | None) -> Cashier:
    """Cookie のセッションIDから担当者を解決する。無効なら 401 UNAUTHORIZED（T-048〜T-050）。"""
    if not raw_session_id:
        raise unauthorized()
    session = repo.get_session(db, hash_session_id(raw_session_id))
    if session is None:
        raise unauthorized()
    # expires_at ちょうどで失効（8時間0分で401）
    if session.expires_at <= clock.utcnow() or not session.cashier.is_active:
        repo.delete_session(db, session.session_id_hash)
        db.commit()
        raise unauthorized()
    return session.cashier


def logout(db: DbSession, raw_session_id: str | None) -> None:
    if raw_session_id:
        repo.delete_session(db, hash_session_id(raw_session_id))
        db.commit()
