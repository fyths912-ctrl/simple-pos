"""時刻の取得を1か所に集約する（テストで時刻を差し替えられるようにする）。

DB には UTC（タイムゾーンなし DATETIME）で保存し、営業日・表示は JST で扱う（設計8.1）。
"""
from datetime import date, datetime, timedelta, timezone

JST = timezone(timedelta(hours=9), name="JST")


def utcnow() -> datetime:
    """UTC の現在時刻（tzinfo なし）。DB 保存用。"""
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def to_jst(dt_utc_naive: datetime) -> datetime:
    return dt_utc_naive.replace(tzinfo=timezone.utc).astimezone(JST)


def business_date(dt_utc_naive: datetime) -> date:
    """税率の適用判定に使う営業日（JST の日付）。"""
    return to_jst(dt_utc_naive).date()
