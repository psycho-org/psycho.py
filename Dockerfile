# ============================================
# Stage 1: Builder
# ============================================
FROM python:3.12-slim AS builder

WORKDIR /app

# Build dependencies (curl for uv installation)
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv with pinned version
RUN curl -LsSf https://astral.sh/uv/0.5.14/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies (without project itself)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=cache,target=/root/.cache/pip \
    uv sync --frozen --no-install-project

# ============================================
# Stage 2: Runtime
# ============================================
FROM python:3.12-slim AS runtime

WORKDIR /app

# Runtime dependencies only (no curl)
RUN apt-get update && apt-get install -y \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy uv from builder
COPY --from=builder /root/.local/bin/uv /root/.local/bin/uv
ENV PATH="/root/.local/bin:$PATH"

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY . .

CMD ["uv", "run", "uvicorn", "main:app"]
