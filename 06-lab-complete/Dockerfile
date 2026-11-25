# ============================================================
# Production Dockerfile — multi-stage, slim, non-root
# ============================================================

# ── Stage 1: builder — cài dependencies vào virtualenv ──
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# requirements đứng trước source để Docker cache được layer cài dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# ── Stage 2: runtime — chỉ chứa venv + source ──
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8000

RUN groupadd --system appuser && useradd --system --gid appuser --no-create-home appuser

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser utils ./utils

USER appuser

EXPOSE 8000

# Dùng python (có sẵn trong image) thay vì cài thêm curl
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT','8000'), timeout=2)" || exit 1

# `exec` để uvicorn thay thế shell và làm PID 1 → nhận SIGTERM khi `docker stop`
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2"]
