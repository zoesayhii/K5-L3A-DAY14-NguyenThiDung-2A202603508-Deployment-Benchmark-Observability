"""
Kết nối Redis dùng chung cho rate limiter và cost guard.

redis.from_url() chỉ tạo client, không mở kết nối, nên app vẫn khởi động được
khi Redis chưa sẵn sàng. Kết nối thật chỉ xảy ra ở lần gọi lệnh đầu tiên.
"""
import redis

from app.config import settings

r = redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=2,
)


def redis_healthy() -> bool:
    """Dùng cho GET /ready: ping được Redis thì True, lỗi kết nối thì False."""
    try:
        return bool(r.ping())
    except redis.RedisError:
        return False
