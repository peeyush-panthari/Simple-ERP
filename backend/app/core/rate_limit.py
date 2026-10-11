"""Rate limiting, backed by Redis so the limit is shared by every API worker
and survives deploys (the Flask original counted in each worker's memory, so
its real login limit was workers x the configured number).

The limiter object has to exist at import time for the `@limiter.limit(...)`
decorators; whether it is active is switched in `create_app` from
`settings.rate_limit_enabled`. `swallow_errors=True`: if Redis is unreachable
the request is allowed and the failure logged, rather than turning a cache
outage into a login outage.
"""

from __future__ import annotations

import logging

from slowapi import Limiter
from starlette.requests import Request

from app.core.client_ip import client_ip
from app.core.config import settings

logger = logging.getLogger("app.rate_limit")


def _key(request: Request) -> str:
    return client_ip(request) or "unknown"


def storage_uri() -> str:
    if not settings.rate_limit_enabled:
        return "memory://"
    return settings.rate_limit_storage_uri or settings.redis_url


limiter = Limiter(key_func=_key, storage_uri=storage_uri(), enabled=settings.rate_limit_enabled, swallow_errors=True)

LOGIN_LIMIT = f"{settings.rate_limit_login_per_minute}/minute"
