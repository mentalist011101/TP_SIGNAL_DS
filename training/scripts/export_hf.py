"""C13 : publie les modèles de production sur Hugging Face, un dépôt public par modèle (I7, S1).

Pour chaque modèle de configs/production.yaml, on envoie dans <utilisateur>/<identifiant> :
- model.safetensors (poids, sans pickle) et config.json, tels que produits par le notebook
  c13_production_models.ipynb (sorties Kaggle, téléchargées à part) ;
- README.md : la fiche docs/models/<identifiant>.md, précédée de l'en-tête de Hugging Face
  (licence non commerciale héritée des données).

L'identification est celle déjà en place sur la machine (hf auth login) : aucun jeton n'est
lu, écrit ni passé par ce script. Il affiche la révision (hash du commit, 40 caractères) de
chaque dépôt, à recopier dans configs/registry.yaml.

Usage, depuis la racine du dépôt :
    uv run python training/scripts/export_hf.py --production-dir <dossier> --username <nom>
    (ajouter --dry-run pour tout préparer et vérifier sans rien envoyer)
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from huggingface_hub import HfApi

from echolens.config import REPO_ROOT
from echolens.core.models.production_config import (
    CONFIG_FILE,
    WEIGHTS_FILE,
    load_production_config,
)
from echolens.training.production import huggingface_readme, load_production_plan

CARDS_DIR = REPO_ROOT / "docs" / "models"
README_FILE = "README.md"


def main() -> None:
    arguments = _parse_arguments()
    plan = load_production_plan()
    api = HfApi()
    if not arguments.dry_run:
        # Vérifie l'identification avant d'envoyer quoi que ce soit.
        account = api.whoami()["name"]
        print("Connecté à Hugging Face :", account)
    revisions = {}
    with tempfile.TemporaryDirectory() as staging:
        for planned in plan.models:
            # Étape 1 : un dossier par modèle, avec les trois fichiers du dépôt.
            folder = Path(staging) / planned.id
            _prepare_folder(arguments.production_dir / planned.id, folder, planned.license)
            repo_id = f"{arguments.username}/{planned.id}"
            if arguments.dry_run:
                print(f"{repo_id} : prêt ({sorted(path.name for path in folder.iterdir())})")
                continue
            # Étape 2 : dépôt public, puis envoi du dossier en un seul commit.
            api.create_repo(repo_id, repo_type="model", private=False, exist_ok=True)
            commit = api.upload_folder(
                repo_id=repo_id,
                folder_path=str(folder),
                commit_message=f"Publie {planned.id} (EchoLens, C13)",
            )
            revisions[planned.id] = {"weights": f"hf://{repo_id}", "revision": commit.oid}
            print(f"{repo_id} : révision {commit.oid}")
    if revisions:
        print(json.dumps(revisions, indent=2))


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publie les modèles de production (I7)")
    parser.add_argument("--production-dir", type=Path, required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _prepare_folder(source: Path, folder: Path, license_id: str) -> None:
    # config.json est relu et validé : un fichier abîmé ne doit jamais être publié.
    config = load_production_config(source / CONFIG_FILE)
    folder.mkdir(parents=True)
    shutil.copy(source / WEIGHTS_FILE, folder / WEIGHTS_FILE)
    shutil.copy(source / CONFIG_FILE, folder / CONFIG_FILE)
    base_model = None
    if config.encoder is not None:
        base_model = config.encoder.checkpoint
    card = (CARDS_DIR / f"{config.model_id}.md").read_text(encoding="utf-8")
    readme = huggingface_readme(card, license_id, base_model)
    (folder / README_FILE).write_text(readme, encoding="utf-8")


if __name__ == "__main__":
    main()
