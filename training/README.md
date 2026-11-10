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
| `c5_esc50_mfcc_svm.ipynb` | C5 : référence MFCC + SVM sur ESC-50 (P3, P4, P5), sans GPU | `esc50.csv` (→ `data/manifests/`), `esc50_mfcc_svm.json` (→ `training/results/`), matrice en 5 catégories (→ `report/figures/`) |

## Règles

- Les features se calculent uniquement avec `echolens.core.features` (décision R5).
- Les embeddings des encodeurs pré-entraînés sont calculés une seule fois puis publiés comme
  dataset Kaggle (décision R6) : les têtes s'entraînent ensuite en quelques secondes.
- Chaque run est tracé dans Weights & Biases ; chaque modèle retenu reçoit une fiche
  (`/model-card`) et une entrée dans `configs/registry.yaml`.
- Les poids sont publiés sur le Hugging Face Hub, jamais dans git.
