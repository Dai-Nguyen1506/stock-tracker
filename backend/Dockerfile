FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Cài build dependencies cho acsylla và build wheel
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ cmake libuv1-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Build wheel trước để image runtime không cần toolchain C/C++
COPY requirements.txt .
RUN pip install --upgrade pip && pip wheel --wheel-dir /wheels -r requirements.txt

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Chỉ giữ runtime libs cần thiết để chạy extension đã build
RUN apt-get update && apt-get install -y --no-install-recommends \
    libuv1t64 libssl3t64 ca-certificates libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

# Copy toàn bộ code
COPY . .

# Chạy app bằng non-root user để giảm rủi ro bảo mật
RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]