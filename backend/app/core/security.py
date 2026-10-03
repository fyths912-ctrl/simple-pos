"""パスワードハッシュ（Argon2id）とセッションID（設計9.1/9.2）。"""
import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

# argon2-cffi の既定は Argon2id（RFC 9106 の推奨パラメータ）
_hasher = PasswordHasher()

# 存在しないIDでも照合と同程度の時間をかけ、応答時間からID有無を推測させない
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def burn_verify_time(password: str) -> None:
    verify_password(password, _DUMMY_HASH)


def new_session_id() -> str:
    """256bit のランダム値（URL-safe 文字列）。"""
    return secrets.token_urlsafe(32)


def hash_session_id(session_id: str) -> str:
    """DB には生のセッションIDではなく SHA-256 を保存する。"""
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()
