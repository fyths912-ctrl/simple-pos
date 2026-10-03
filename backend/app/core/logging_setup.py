"""JSON 形式のログ（Application Insights / App Service ログで検索しやすくする）。

記録してよい項目だけを extra で渡す運用とし、Cookie・Authorization・パスワード・会員の住所/電話番号は
ログに載せない（設計12.2／T-068・T-069）。
"""
import json
import logging
import sys

_ALLOWED_EXTRA = {
    "request_id", "method", "endpoint", "status", "duration_ms",
    "cashier_id", "result", "ip", "reason", "transaction_id",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in _ALLOWED_EXTRA:
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            # スタックトレースはサーバー側ログにのみ残す（障害調査用、ブラウザには返さない）
            payload["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
            payload["stack"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger("pos")
    root.handlers = [handler]
    root.setLevel(level)
    root.propagate = True
