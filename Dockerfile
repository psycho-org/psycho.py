FROM python:3.12-slim

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install uv and dependencies
RUN pip install uv && uv sync --frozen

# Copy application code
COPY . .

# Run bot
CMD ["uv", "run", "python", "-m", "bot.main"]
