# Entraînement sur Kaggle

Les notebooks de `notebooks/` tournent sur Kaggle (GPU T4 ou P100, quota hebdomadaire par compte).
Chaque membre utilise **son propre compte**.

## Amorçage d'un notebook

```python
# Cellule 1 : récupérer le code du dépôt et l'installer (même cœur que l'application)
!git clone --depth 1 https://github.com/mentalist011101/TP_SIGNAL_DS.git
%pip install -q -e TP_SIGNAL_DS

# Cellule 2 : secrets (Add-ons → Secrets) — jamais en clair dans le notebook
from kaggle_secrets import UserSecretsClient
secrets = UserSecretsClient()
import os
os.environ["WANDB_API_KEY"] = secrets.get_secret("WANDB_API_KEY")
os.environ["HF_TOKEN"] = secrets.get_secret("HF_TOKEN")
```

## Règles

- Les features se calculent uniquement avec `echolens.core.features` (décision R5).
- Les embeddings des encodeurs pré-entraînés sont calculés une seule fois puis publiés comme
  dataset Kaggle (décision R6) : les têtes s'entraînent ensuite en quelques secondes.
- Chaque run est tracé dans Weights & Biases ; chaque modèle retenu reçoit une fiche
  (`/model-card`) et une entrée dans `configs/registry.yaml`.
- Les poids sont publiés sur le Hugging Face Hub, jamais dans git.
