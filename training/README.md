# Entraînement sur Kaggle

Les notebooks de `notebooks/` tournent sur Kaggle (GPU T4 ou P100, quota hebdomadaire par compte).
Chaque membre utilise **son propre compte**.

## Amorçage d'un notebook

```python
# Cellule 1 : récupérer le code du dépôt et l'installer (même cœur que l'application).
# BRANCH = "main" sauf pour tester une branche pas encore fusionnée.
import sys

BRANCH = "main"
REPO_URL = "https://github.com/mentalist011101/TP_SIGNAL_DS.git"
CLONE_DIR = "/kaggle/working/TP_SIGNAL_DS"

!rm -rf {CLONE_DIR}
!git clone --depth 1 --branch {BRANCH} {REPO_URL} {CLONE_DIR}
# Kaggle tourne sous Python 3.13, au-delà de requires-python (<3.13) du dépôt.
%pip install -q --ignore-requires-python -e {CLONE_DIR}

# L'installation éditable n'est visible qu'après un redémarrage du noyau : on ajoute src/
# au chemin d'import pour utiliser echolens tout de suite.
sys.path.insert(0, CLONE_DIR + "/src")

# Cellule 2 : secrets (Add-ons → Secrets) — jamais en clair dans le notebook
from kaggle_secrets import UserSecretsClient
secrets = UserSecretsClient()
import os
os.environ["WANDB_API_KEY"] = secrets.get_secret("WANDB_API_KEY")
os.environ["HF_TOKEN"] = secrets.get_secret("HF_TOKEN")
```

## Notebooks

| Notebook | Tâche | Ce qu'il produit |
| --- | --- | --- |
| `c3_manifests_emotions.ipynb` | C3 : manifestes de CREMA-D et de RAVDESS (P1, P9), sans GPU ni ffmpeg | `cremad.csv` et `ravdess.csv` (→ `data/manifests/`) |
| `c5_esc50_mfcc_svm.ipynb` | C5 : référence MFCC + SVM sur ESC-50 (P3, P4, P5), sans GPU | `esc50.csv` (→ `data/manifests/`), `esc50_mfcc_svm.json` (→ `training/results/`), matrice en 5 catégories (→ `report/figures/`) |
| `c10_embeddings.ipynb` | C10 : moyennes par couche des encodeurs gelés de la famille B (Brique 4, R6, R7), GPU T4 | datasets Kaggle privés `echolens-emb-wav2vec2-base`, `echolens-emb-mhubert-147`, `echolens-emb-whisper-base` (avec `padded/`), jamais sur GitHub |
| `c9_family_a_esc50.ipynb` | C9 : CNN et CRNN de la famille A sur le log-Mel d'ESC-50 (Brique 4, R4, R6, P3, P6, P8), GPU T4 | `esc50_family_a_cnn.json` et `esc50_family_a_crnn.json` (→ `training/results/`), matrices en 5 catégories et exemples d'attention (→ `report/figures/`) ; en sortie Kaggle seulement : log-Mel, prédictions, probabilités, poids d'attention et poids des 15 modèles finaux par réseau |

## Règles

- Les features se calculent uniquement avec `echolens.core.features` (décision R5).
- Les embeddings des encodeurs pré-entraînés sont calculés une seule fois puis publiés comme
  dataset Kaggle (décision R6) : les têtes s'entraînent ensuite en quelques secondes.
- Chaque run est tracé dans Weights & Biases ; chaque modèle retenu reçoit une fiche
  (`/model-card`) et une entrée dans `configs/registry.yaml`.
- Les poids sont publiés sur le Hugging Face Hub, jamais dans git.
