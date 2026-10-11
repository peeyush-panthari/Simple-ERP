"""Small Redis read-through cache. Every failure mode (Redis down, slow,
corrupt entry) degrades to "compute it live" - the cache can make a request
faster but never make it fail."""

from __future__ import annotations

import json
import logging
from typing import Callable

import redis

from app.core.config import settings

logger = logging.getLogger("app.cache")

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(settings.redis_url, socket_timeout=1, socket_connect_timeout=1, decode_responses=True)
    return _client


def cached_json(key: str, ttl_seconds: int, loader: Callable[[], dict]) -> dict:
    if ttl_seconds <= 0:
        return loader()
    try:
        hit = get_redis().get(key)
        if hit is not None:
            return json.loads(hit)
    except Exception as exc:  # noqa: BLE001
        logger.warning("cache read failed for %s: %s", key, exc)
    value = loader()
    try:
        get_redis().set(key, json.dumps(value), ex=ttl_seconds)
    except Exception as exc:  # noqa: BLE001
        logger.warning("cache write failed for %s: %s", key, exc)
    return value


def healthy() -> bool:
    try:
        return bool(get_redis().ping())
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis health check failed: %s", exc)
        return False
