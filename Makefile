# Commandes du projet EchoLens. « make help » liste les cibles.
.DEFAULT_GOAL := help
.PHONY: help setup setup-ml lint format test check run web-dev web-build api-types requirements docker clean

UV ?= uv
NPM ?= npm --prefix web

help: ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: ## Installe l'environnement de développement (Python, front, pre-commit)
	$(UV) sync
	$(NPM) ci
	$(UV) run pre-commit install

setup-ml: ## Ajoute les dépendances des modèles (torch, transformers…)
	$(UV) sync --extra ml

lint: ## Vérifie le style et les types (Python et front)
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	$(UV) run mypy
	$(NPM) run lint
	$(NPM) run format:check

format: ## Formate automatiquement le code
	$(UV) run ruff check --fix .
	$(UV) run ruff format .
	$(NPM) run format

test: ## Lance les tests Python avec couverture
	$(UV) run pytest --cov --cov-report=term-missing -m "not slow and not ml"

check: lint test web-build ## Tout ce que la CI vérifie : à lancer avant chaque PR

run: ## Lance le serveur Flask de développement (http://localhost:5000)
	$(UV) run flask --app echolens.api:create_app run --debug --port 5000

web-dev: ## Lance le front avec rechargement à chaud (http://localhost:5173)
	$(NPM) run dev

web-build: ## Compile le front dans web/dist
	$(NPM) run build

api-types: ## Régénère les types TypeScript depuis l'OpenAPI (serveur lancé)
	$(NPM) run gen:api

requirements: ## Régénère requirements.txt (livrable) depuis le verrou uv
	$(UV) export --no-hashes --no-dev --extra ml --format requirements-txt -o requirements.txt

docker: ## Construit l'image et lance l'application (http://localhost:5000)
	docker compose -f docker/docker-compose.yml up --build

clean: ## Supprime les fichiers générés
	rm -rf web/dist .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
