# Image EchoLens en deux étapes (S5, ENF-08) : Node compile le front, puis une image Python
# sert l'API et le front compilé avec Gunicorn. Ni GPU ni Node à l'exécution.
#
# Deux variantes, choisies au build :
# - complète (par défaut) : vrais modèles du registre, extra [ml], torch CPU ;
#     docker build -f docker/Dockerfile -t echolens .
# - démo : faux prédicteur, sans torch, image légère (environ 10 fois plus petite) ;
#     docker build -f docker/Dockerfile --build-arg UV_EXTRAS="" \
#       --build-arg INFERENCE_BACKEND=demo -t echolens-demo .
# Le clonage (XTTS-v2, extra [tts]) s'ajoute avec UV_EXTRAS="--extra ml --extra tts" ; il
# demande environ 2,5 Go de mémoire de plus et l'acceptation de sa licence (voir README).

# --- Étape 1 : compilation du front React ---
FROM node:22-slim AS web
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# --- Étape 2 : application Flask ---
FROM python:3.11-slim AS app
ARG UV_EXTRAS="--extra ml"
ARG INFERENCE_BACKEND=models
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    ECHOLENS_INFERENCE_BACKEND=${INFERENCE_BACKEND} \
    # Poids téléchargés depuis Hugging Face (révisions figées du registre), rangés dans le
    # volume des données : ils ne sont téléchargés qu'une fois.
    HF_HOME=/app/var/huggingface
# ffmpeg : décodage de tous les formats audio par le cœur (D1).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
# Dépendances d'abord, sans le code : cette couche reste en cache tant que uv.lock ne change pas.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project ${UV_EXTRAS}
COPY src/ src/
RUN uv sync --frozen --no-dev ${UV_EXTRAS}

COPY configs/ configs/
# Résultats des notebooks : chiffres des fiches des modèles (EF-16).
COPY training/results/ training/results/
COPY --from=web /app/web/dist web/dist

# Utilisateur sans droits d'administration ; seul var/ (base, audios, poids) lui est ouvert.
RUN useradd --create-home --uid 1000 echolens \
    && mkdir -p /app/var \
    && chown -R echolens:echolens /app/var
USER echolens

EXPOSE 5000
# Mode threads : requis par le WebSocket du flux micro (flask-sock). Un seul processus : les
# modèles ne sont chargés qu'une fois en mémoire. PORT : imposé par certaines plateformes
# (Render) ; 5000 sinon.
CMD ["sh", "-c", "exec /app/.venv/bin/gunicorn --bind 0.0.0.0:${PORT:-5000} --worker-class gthread --threads 8 --workers 1 --timeout 120 echolens.wsgi:app"]
