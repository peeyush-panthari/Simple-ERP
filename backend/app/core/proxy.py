"""TRUSTED_PROXY_HOPS for the ASGI app - the equivalent of werkzeug's ProxyFix, which the original applied.

Behind N reverse proxies the caller's address, scheme and host arrive in X-Forwarded-For / -Proto /
-Host; the N-th entry from the RIGHT is what our outermost trusted proxy saw (anything to its left was
supplied by the caller). With 0 hops the app is reached directly, these headers are attacker-controlled
and are not touched. When a header carries fewer entries than hops there is no trusted value, and the
socket's own address / scheme is kept.
"""

from __future__ import annotations


def _nth_from_right(headers: dict[bytes, bytes], name: bytes, hops: int) -> str | None:
    values = [v.strip() for v in headers.get(name, b"").decode("latin-1").split(",") if v.strip()]
    return values[-hops] if len(values) >= hops else None


class ProxyFixMiddleware:
    def __init__(self, app, hops: int):
        self.app = app
        self.hops = hops

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket") and self.hops > 0:
            headers = dict(scope["headers"])
            ip = _nth_from_right(headers, b"x-forwarded-for", self.hops)
            proto = _nth_from_right(headers, b"x-forwarded-proto", self.hops)
            host = _nth_from_right(headers, b"x-forwarded-host", self.hops)
            scope = dict(scope)
            if ip:
                scope["client"] = (ip, scope["client"][1] if scope.get("client") else 0)
            if proto:
                scope["scheme"] = proto if scope["type"] == "http" else {"https": "wss", "http": "ws"}.get(proto, proto)
            if host:
                scope["headers"] = [(k, v) for k, v in scope["headers"] if k != b"host"] + [(b"host", host.encode("latin-1"))]
        await self.app(scope, receive, send)
