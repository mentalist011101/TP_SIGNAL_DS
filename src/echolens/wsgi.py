"""Point d'entrée WSGI pour Gunicorn : ``gunicorn echolens.wsgi:app``."""

from echolens.api import create_app

app = create_app()
