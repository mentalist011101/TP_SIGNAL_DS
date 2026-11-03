# Image EchoLens en deux étapes : Node compile le front, puis une image Python légère sert le tout.

# --- Étape 1 : compilation du front React ---
FROM node:22-slim AS web
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# --- Étape 2 : application Flask ---
FROM python:3.11-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src/ src/
RUN uv sync --frozen --no-dev --extra ml

COPY configs/ configs/
COPY --from=web /app/web/dist web/dist

EXPOSE 5000
# Mode threads : requis par le WebSocket du flux micro (flask-sock).
CMD ["uv", "run", "--no-sync", "gunicorn", "--bind", "0.0.0.0:5000", "--worker-class", "gthread", "--threads", "8", "--workers", "1", "echolens.wsgi:app"]
