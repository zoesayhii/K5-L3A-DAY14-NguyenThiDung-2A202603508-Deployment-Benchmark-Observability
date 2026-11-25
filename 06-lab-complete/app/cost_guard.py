"""
Cost guard.

  • Cộng dồn chi phí LLM (tính theo token) vào Redis, theo ngày và theo tháng
  • Tổng chi phí vượt DAILY_BUDGET_USD hoặc MONTHLY_BUDGET_USD → HTTP 402
"""
from datetime import datetime, timezone

import redis
from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

# Giá USD / 1K tokens (tham khảo gpt-4o-mini)
PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006

_DAY_TTL = 2 * 24 * 3600
_MONTH_TTL = 32 * 24 * 3600


def _keys() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    return f"cost:day:{now:%Y-%m-%d}", f"cost:month:{now:%Y-%m}"


def check_budget() -> None:
    """Gọi TRƯỚC khi gọi LLM. Hết budget → HTTPException 402."""
    day_key, month_key = _keys()
    try:
        day_spent, month_spent = r.mget(day_key, month_key)
    except redis.RedisError:
        raise HTTPException(status_code=503, detail="Cost guard unavailable")

    if float(day_spent or 0) >= settings.daily_budget_usd:
        raise HTTPException(status_code=402, detail="Daily budget exhausted")
    if float(month_spent or 0) >= settings.monthly_budget_usd:
        raise HTTPException(status_code=402, detail="Monthly budget exhausted")


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí của request vào tổng, trả về chi phí request."""
    cost = (input_tokens / 1000) * PRICE_INPUT_PER_1K + (output_tokens / 1000) * PRICE_OUTPUT_PER_1K
    day_key, month_key = _keys()
    try:
        pipe = r.pipeline()
        pipe.incrbyfloat(day_key, cost)
        pipe.expire(day_key, _DAY_TTL)
        pipe.incrbyfloat(month_key, cost)
        pipe.expire(month_key, _MONTH_TTL)
        pipe.execute()
    except redis.RedisError:
        # Request đã chạy xong, không làm hỏng response chỉ vì ghi sổ lỗi.
        pass
    return cost
