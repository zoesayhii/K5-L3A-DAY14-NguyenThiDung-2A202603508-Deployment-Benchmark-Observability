"""
Rate limiting — sliding window 60 giây cho mỗi API key, state trong Redis.

State nằm trong Redis nên mọi worker / instance dùng chung bộ đếm và bộ đếm
vẫn còn sau khi restart agent.
"""
import hashlib
import math
import time
import uuid

import redis
from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

WINDOW_SECONDS = 60


def check_rate_limit(key: str) -> None:
    # Không lưu API key thô trong Redis, chỉ lưu hash rút gọn.
    redis_key = "rl:" + hashlib.sha256(key.encode()).hexdigest()[:16]
    now = time.time()
    member = f"{now}:{uuid.uuid4().hex}"
    try:
        pipe = r.pipeline()  # MULTI/EXEC: 4 lệnh chạy nguyên tử
        pipe.zremrangebyscore(redis_key, 0, now - WINDOW_SECONDS)
        pipe.zadd(redis_key, {member: now})
        pipe.zcard(redis_key)
        pipe.expire(redis_key, WINDOW_SECONDS + 1)
        _, _, count, _ = pipe.execute()

        if count > settings.rate_limit_per_minute:
            # Request bị từ chối không được tính vào cửa sổ, nếu không client
            # cứ thử lại là bị khoá mãi.
            r.zrem(redis_key, member)
            oldest = r.zrange(redis_key, 0, 0, withscores=True)
            retry_after = WINDOW_SECONDS
            if oldest:
                retry_after = max(1, math.ceil(oldest[0][1] + WINDOW_SECONDS - now))
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {settings.rate_limit_per_minute} requests/minute",
                headers={"Retry-After": str(retry_after)},
            )
    except redis.RedisError:
        # Fail closed: không kiểm soát được tốc độ thì không cho đi tiếp.
        raise HTTPException(status_code=503, detail="Rate limiter unavailable")
