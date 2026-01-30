FROM python:3.12-slim

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install uv and dependencies
RUN pip install uv && uv sync --frozen

# Copy application code
COPY . .

# EXAONE 등 Hugging Face 모델 캐시: 볼륨 마운트 + HF_HUB_CACHE 환경변수 사용 권장
# 예: -v hf-cache:/cache/huggingface -e HF_HUB_CACHE=/cache/huggingface/hub
# docker-compose.yml 참고

# Run bot
CMD ["uv", "run", "python", "-m", "bot.main"]
