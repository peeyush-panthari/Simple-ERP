"""The caller's IP, honouring TRUSTED_PROXY_HOPS (the original applied
werkzeug's ProxyFix with the same setting).

With 0 hops the app is reached directly, so X-Forwarded-For is whatever the
caller typed and is ignored - otherwise anyone could pick a fresh identity per
request and walk past the login limiter and the public-intake throttle. With N
hops, the N-th entry from the RIGHT of X-Forwarded-For is the address our
outermost trusted proxy saw; anything to its left is caller-supplied.
"""

from __future__ import annotations

from starlette.requests import Request

from app.core.config import settings


def client_ip(request: Request) -> str | None:
    hops = settings.trusted_proxy_hops
    if hops > 0:
        forwarded = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
        if forwarded:
            if len(forwarded) >= hops:
                return forwarded[-hops]
    return request.client.host if request.client else None
