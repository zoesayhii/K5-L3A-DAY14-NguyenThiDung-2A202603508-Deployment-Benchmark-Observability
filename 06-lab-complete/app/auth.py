"""
API Key authentication.

  • Client gửi header  X-API-Key: <key>
  • Key phải trùng biến môi trường AGENT_API_KEY
  • Thiếu hoặc sai key → HTTP 401
"""
import secrets

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import settings

# auto_error=False để tự trả 401 (mặc định FastAPI trả 403 khi thiếu header).
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str | None = Security(_api_key_header)) -> str:
    """Dependency cho /ask. Trả về key hợp lệ (dùng làm định danh cho rate limit)."""
    expected = settings.agent_api_key
    # Chưa cấu hình AGENT_API_KEY thì từ chối tất cả, không mở công khai.
    # compare_digest chống timing attack khi so sánh key.
    if not expected or not api_key or not secrets.compare_digest(api_key, expected):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key
