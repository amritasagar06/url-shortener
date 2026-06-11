from redis import asyncio as aioredis
from app.config import settings
import logging

logger = logging.getLogger(__name__)

class RedisCache:
    def __init__(self):
        self.redis = None

    def connect(self):
        """Initialize an async Redis connection pool."""
        self.redis = aioredis.from_url(
            settings.REDIS_URL, 
            encoding="utf-8", 
            decode_responses=True
        )

    async def get(self, key: str) -> str | None:
        try:
            if not self.redis:
                self.connect()
            return await self.redis.get(key)
        except Exception as e:
            logger.error(f"Redis GET exception: {e}")
            return None

    async def set(self, key: str, value: str, expire_seconds: int = 86400) -> bool:
        """Sets a key with a default expiration of 24 hours."""
        try:
            if not self.redis:
                self.connect()
            await self.redis.set(key, value, ex=expire_seconds)
            return True
        except Exception as e:
            logger.error(f"Redis SET exception: {e}")
            return False

    async def close(self):
        if self.redis:
            await self.redis.close()

# Global single instance wrapper
cache = RedisCache()
cache.connect()  # 1. Force pool initialization right on app boot

# --- 2. Expose 'redis' variable directly ---
# This matches the exact import name expected by your main.py file!
redis = cache.redis