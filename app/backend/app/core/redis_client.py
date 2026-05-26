import json
import logging
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_redis: Any = None
_redis_available: bool = False


async def _init_redis():
    global _redis, _redis_available
    settings = get_settings()
    if not settings.redis_enabled or not settings.redis_url:
        _redis_available = False
        logger.info("Redis caching disabled (redis_enabled=%s)", settings.redis_enabled)
        return
    try:
        from redis.asyncio import Redis

        _redis = Redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
        await _redis.ping()
        _redis_available = True
        logger.info("Redis connected: %s", settings.redis_url)
    except Exception as exc:
        _redis = None
        _redis_available = False
        logger.warning("Redis unavailable, caching disabled: %s", exc)


async def get_redis():
    global _redis, _redis_available
    if not _redis_available or _redis is None:
        return None
    try:
        await _redis.ping()
        return _redis
    except Exception:
        _redis_available = False
        logger.warning("Redis ping failed, falling back to no-cache mode")
        return None


async def init_app_redis():
    await _init_redis()


async def close_redis():
    global _redis
    if _redis is not None:
        try:
            await _redis.aclose()
        except Exception:
            pass
        _redis = None


def is_redis_available() -> bool:
    return _redis_available


class RedisCache:
    CACHE_TTLS = {
        "llm": 7 * 24 * 3600,
        "auth:jwt": 900,
        "auth:apikey": 300,
        "tenant:slug": 600,
        "tenant:id": 600,
        "jobs:list": 600,
        "job:detail": 300,
        "profile": 600,
        "evidence": 600,
    }

    @staticmethod
    def _key(prefix: str, *parts: str) -> str:
        return f"dachjob:{prefix}:{':'.join(str(p) for p in parts if p)}"

    async def get(self, prefix: str, *parts: str) -> str | None:
        client = await get_redis()
        if client is None:
            return None
        key = self._key(prefix, *parts)
        try:
            return await client.get(key)
        except Exception:
            return None

    async def set(self, prefix: str, *parts: str, value: str = "1", ttl: int | None = None) -> bool:
        client = await get_redis()
        if client is None:
            return False
        key = self._key(prefix, *parts)
        ttl = ttl or self.CACHE_TTLS.get(prefix, 300)
        try:
            await client.set(key, value, ex=ttl)
            return True
        except Exception:
            return False

    async def get_json(self, prefix: str, *parts: str) -> Any | None:
        raw = await self.get(prefix, *parts)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

    async def set_json(self, prefix: str, *parts: str, value: Any, ttl: int | None = None) -> bool:
        return await self.set(prefix, *parts, value=json.dumps(value), ttl=ttl)

    async def delete(self, prefix: str, *parts: str) -> bool:
        client = await get_redis()
        if client is None:
            return False
        key = self._key(prefix, *parts)
        try:
            await client.delete(key)
            return True
        except Exception:
            return False

    async def delete_pattern(self, pattern: str) -> int:
        client = await get_redis()
        if client is None:
            return 0
        full = self._key(pattern, "*")
        try:
            keys = await client.keys(full)
            if keys:
                return await client.delete(*keys)
            return 0
        except Exception:
            return 0

    async def invalidate_tenant(self, prefix: str, tenant_id: str) -> int:
        return await self.delete_pattern(f"{prefix}:*:{tenant_id}:*")

    async def health_check(self) -> dict[str, str]:
        client = await get_redis()
        if client is None:
            return {"redis": "disabled"}
        try:
            await client.ping()
            return {"redis": "ok"}
        except Exception as e:
            return {"redis": f"error: {e}"}


cache = RedisCache()
