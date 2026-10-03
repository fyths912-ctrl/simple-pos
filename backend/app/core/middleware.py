"""リクエストID・APIログ・セキュリティヘッダー・HTTPS強制（設計10章/12.2）。"""
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response

api_log = logging.getLogger("pos.api")

SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    # API は JSON しか返さないため最も厳しい CSP にする
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Cache-Control": "no-store",
}


class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, force_https: bool = False):
        super().__init__(app)
        self.force_https = force_https

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()

        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        if self.force_https and proto != "https":
            if request.method in ("GET", "HEAD"):
                response: Response = RedirectResponse(str(request.url.replace(scheme="https")), status_code=308)
            else:
                response = JSONResponse(status_code=400, content={"error": {"code": "HTTPS_REQUIRED", "message": "HTTPSで接続してください"}})
        else:
            try:
                response = await call_next(request)
            except Exception:
                # 想定外の例外：スタックトレースはサーバーログのみ、応答は一般化（T-061）
                logging.getLogger("pos.error").exception("unhandled error", extra={"request_id": request_id})
                response = JSONResponse(status_code=500, content={"error": {"code": "INTERNAL_ERROR", "message": "システムエラーが発生しました"}})

        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        response.headers["X-Request-ID"] = request_id

        route = request.scope.get("route")
        # 会員ID・商品コード等を含む実パスではなく、ルートのテンプレートを記録する
        endpoint = getattr(route, "path", "unmatched")
        api_log.info("api", extra={
            "request_id": request_id, "method": request.method, "endpoint": endpoint,
            "status": response.status_code, "duration_ms": round((time.perf_counter() - started) * 1000, 1),
        })
        return response
