import time
from fastapi import Request, HTTPException, status
from redis.asyncio import Redis

class SlidingWindowRateLimiter:
    """
    Task T5-1: High-speed sliding-window rate limit checker backed by Redis.
    Supports anonymous dynamic boundaries alongside credentialed boundaries.
    """
    def __init__(self, redis_client: Redis):
        self.redis = redis_client

    async def check_rate_limit(self, identifier: str, limit: int, window_seconds: int = 60):
        """
        Evaluates sliding counter capacity using Sorted Sets (ZSET) inside Redis.
        """
        current_time = time.time()
        key = f"ratelimit:{identifier}"
        clear_before = current_time - window_seconds

        # Execute transactional multi-blocks atomically
        async with self.redis.pipeline(transaction=True) as pipe:
            # 1. Clear timestamps preceding current sliding time window boundary
            pipe.zremrangebyscore(key, 0, clear_before)
            # 2. Append current unique request instance timestamp
            pipe.zadd(key, {str(current_time): current_time})
            # 3. Retrieve active counter total for the current range scope
            pipe.zcard(key)
            # 4. Renew expiration boundary to prevent memory leakage
            pipe.expire(key, window_seconds + 5)
            
            # Execute pipeline
            _, _, total_requests, _ = await pipe.execute()

        if total_requests > limit:
            retry_after = int(window_seconds - (current_time % window_seconds))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(retry_after)},
                detail=f"Rate limit exceeded. Please try again in {retry_after} seconds."
            )