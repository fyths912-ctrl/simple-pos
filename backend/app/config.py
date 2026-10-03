"""アプリ設定。秘密情報・環境依存値は環境変数（App Service のアプリ設定 / Key Vault 参照）から読む。

注意（F-008）：消費税率はここに置かない。税率は tax_rates テーブルで管理する。
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # DB（例: mysql+pymysql://user:pass@host:3306/pos_app?charset=utf8mb4）
    database_url: str = "mysql+pymysql://pos:pospass@127.0.0.1:3306/pos_app?charset=utf8mb4"
    db_ssl_ca: str | None = None  # Azure MySQL へTLS接続する際のCA証明書パス
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_recycle_seconds: int = 1800  # Azure 側のアイドルタイムアウトより短くする（設計11.2）

    # セッション（設計9.1／暫定値）
    session_cookie_name: str = "pos_session"
    session_ttl_minutes: int = 8 * 60
    cookie_secure: bool = True
    cookie_samesite: str = "lax"  # 同一オリジン構成（SWA の /api 転送）前提

    # ログイン失敗ロック（設計9.2／暫定値）
    login_lock_threshold: int = 5
    login_lock_minutes: int = 15

    # 購入（暫定値）
    max_quantity_per_item: int = 99
    max_cart_lines: int = 100

    # CORS：同一オリジン構成では空でよい。別オリジン時のみ本番フロントURLを列挙（* 禁止）
    cors_allow_origins: list[str] = []

    # HTTPS（App Service の HTTPS Only と併用。プロキシ配下では X-Forwarded-Proto を見る）
    force_https: bool = False

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
