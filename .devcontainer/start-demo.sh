#!/usr/bin/env bash
# Démo publique d'EchoLens depuis un Codespace : vrais modèles, mot de passe obligatoire (S6).
#
#   bash .devcontainer/start-demo.sh            # sans le clonage
#   ACCEPT_CPML=true bash .devcontainer/start-demo.sh
#                                               # avec le clonage : la personne qui lance la
#                                               # démo accepte la Coqui Public Model License
#                                               # (usage non commercial, https://coqui.ai/cpml)
#
# L'adresse publique est https://<nom du codespace>-5000.app.github.dev. Elle ne répond que
# tant que le Codespace tourne : il s'arrête après le délai d'inactivité du compte GitHub.
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"

if [ -z "${ECHOLENS_ACCESS_PASSWORD:-}" ]; then
  echo "Définissez d'abord le secret Codespaces ECHOLENS_ACCESS_PASSWORD (voir README)." >&2
  exit 1
fi

if ! command -v uv > /dev/null || [ ! -f web/dist/index.html ]; then
  echo "Codespace pas encore prêt (uv ou front absent) : lancez bash .devcontainer/post-create.sh" >&2
  exit 1
fi

export ECHOLENS_INFERENCE_BACKEND=models
# Modèles chargés et chauffés au démarrage : la première analyse du jury n'attend pas.
export ECHOLENS_PRELOAD_MODELS=true
export ECHOLENS_VOICE_CLONING_LICENSE_ACCEPTED="${ACCEPT_CPML:-false}"

# Le port devient public : sans cela, seul le propriétaire du Codespace pourrait ouvrir la page.
if [ -n "${CODESPACE_NAME:-}" ] && command -v gh > /dev/null; then
  gh codespace ports visibility 5000:public -c "$CODESPACE_NAME" \
    || echo "Rendez le port 5000 public à la main (onglet Ports, clic droit, Port Visibility)."
fi

# Mêmes réglages que l'image Docker (docker/Dockerfile) : un processus, des threads.
exec uv run --no-sync gunicorn --bind 0.0.0.0:5000 --worker-class gthread --threads 8 \
  --workers 1 --timeout 300 echolens.wsgi:app
