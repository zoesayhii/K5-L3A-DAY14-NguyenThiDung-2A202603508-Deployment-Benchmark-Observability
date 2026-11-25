"""
Production AI Agent — Part 6 Final Project

    uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
"""
import json
import logging
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import r, redis_healthy
from utils.mock_llm import ask as llm_ask


# ── Structured logging: mỗi dòng log của app là 1 JSON object ──
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "lvl": record.levelname,
            "event": record.getMessage(),
        }
        entry.update(getattr(record, "fields", {}))
        if record.exc_info:
            # Stack trace chỉ nằm trong log nội bộ, không bao giờ trả cho client.
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


logger = logging.getLogger("agent")
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(JsonFormatter())
    logger.addHandler(_handler)


def log(event: str, level: int = logging.INFO, **fields) -> None:
    logger.log(level, event, extra={"fields": fields})


# ── Lifespan: startup / graceful shutdown ──
@asynccontextmanager
async def lifespan(_: FastAPI):
    log("startup", environment=settings.environment, port=settings.port)
    yield
    # Uvicorn nhận SIGTERM thì ngừng nhận kết nối mới, chờ request đang chạy xong,
    # rồi mới chạy phần dưới và thoát với exit code 0.
    log("shutdown", detail="draining finished, closing redis")
    try:
        r.close()
    except Exception:  # noqa: BLE001 — đang tắt, không để lỗi dọn dẹp chặn việc thoát
        pass


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


@app.middleware("http")
async def access_log(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    log(
        "request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        ms=round((time.perf_counter() - start) * 1000, 1),
    )
    return response


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    # Lỗi không lường trước: log đầy đủ, nhưng chỉ trả thông báo chung cho client.
    logger.error("unhandled_error", exc_info=exc, extra={"fields": {"path": request.url.path}})
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health")
def health():
    """Liveness: luôn 200 khi process còn chạy, không phụ thuộc Redis."""
    return {"status": "ok"}


@app.get("/ready")
def ready():
    """Readiness: 200 khi Redis kết nối được, 503 khi không."""
    if redis_healthy():
        return {"status": "ready"}
    return JSONResponse(status_code=503, content={"status": "not ready", "reason": "redis unavailable"})


def _estimate_tokens(text: str) -> int:
    # Ước lượng thô ~1.3 token / từ, đủ để tính chi phí cho mock LLM.
    return max(1, int(len(text.split()) * 1.3))


@app.post("/ask")
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    check_rate_limit(api_key)  # 429
    check_budget()             # 402
    answer = llm_ask(body.question)
    cost = record_cost(_estimate_tokens(body.question), _estimate_tokens(answer))
    log("ask", question_len=len(body.question), cost_usd=round(cost, 8))
    return {"question": body.question, "answer": answer}
