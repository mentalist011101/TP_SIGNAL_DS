#!/usr/bin/env bash
# Préparation d'un Codespace EchoLens, une seule fois à sa création : ffmpeg (D1), uv, les
# dépendances avec les vrais modèles et le clonage, puis le front compilé.
set -euo pipefail

sudo apt-get update
sudo apt-get install -y --no-install-recommends ffmpeg
pip install --user uv
export PATH="$HOME/.local/bin:$PATH"

# torch en version CPU sous Linux (pyproject.toml, [tool.uv.sources]).
uv sync --extra ml --extra tts

npm --prefix web ci
npm --prefix web run build

echo "Codespace prêt. Démo publique : bash .devcontainer/start-demo.sh"
