#!/usr/bin/env bash
# Préparation d'un Codespace EchoLens, une seule fois à sa création : ffmpeg (D1), uv, les
# dépendances avec les vrais modèles et le clonage, puis le front compilé. Chaque étape
# s'annonce : en cas d'échec, le journal de création dit laquelle.
set -euo pipefail

echo "== 1/4 ffmpeg"
# Un dépôt tiers de l'image (Yarn, ajouté avec Node) peut avoir une clé expirée et faire
# échouer « apt-get update » ; les paquets Debian, dont ffmpeg, restent installables.
sudo apt-get update || echo "apt-get update incomplet (dépôt tiers) : on continue avec Debian."
sudo apt-get install -y --no-install-recommends ffmpeg

echo "== 2/4 uv"
python -m pip install --user --upgrade uv
export PATH="$HOME/.local/bin:$PATH"

echo "== 3/4 dépendances (torch CPU, modèles, clonage)"
uv sync --extra ml --extra tts

echo "== 4/4 front"
npm --prefix web ci
npm --prefix web run build

echo "Codespace prêt. Démo publique : bash .devcontainer/start-demo.sh"
