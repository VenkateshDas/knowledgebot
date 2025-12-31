# Use Python 3.12 slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install uv for fast dependency installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies using uv (including production extras for database support)
RUN uv sync --frozen --no-dev --extra production

# Copy application code
COPY . .

# Create directory for SQLite database
RUN mkdir -p /data

# Expose port (not strictly necessary for Telegram bots, but good practice)
EXPOSE 8080

# Run the bot
CMD ["uv", "run", "python", "telegram_bot.py"]
