"""Mot de passe d'accès d'une instance publique (S6) : authentification HTTP Basic."""

import base64
from pathlib import Path

from flask.testing import FlaskClient

from echolens.api import create_app
from echolens.config import AppSettings

PASSWORD = "mot-de-passe-de-test"


def protected_client(tmp_path: Path) -> FlaskClient:
    settings = AppSettings(
        data_dir=tmp_path, web_dist_dir=tmp_path / "dist", access_password=PASSWORD
    )
    return create_app(settings, TESTING=True).test_client()


def basic(password: str) -> dict[str, str]:
    token = base64.b64encode(f"jury:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def test_without_password_setting_everything_is_open(client: FlaskClient) -> None:
    assert client.get("/api/v1/models").status_code == 200


def test_missing_or_wrong_password_is_refused(tmp_path: Path) -> None:
    client = protected_client(tmp_path)

    missing = client.get("/api/v1/models")
    wrong = client.get("/api/v1/models", headers=basic("faux"))

    assert missing.status_code == 401
    assert missing.headers["WWW-Authenticate"].startswith("Basic")
    assert wrong.status_code == 401


def test_right_password_opens_the_api_and_the_pages(tmp_path: Path) -> None:
    client = protected_client(tmp_path)

    assert client.get("/api/v1/models", headers=basic(PASSWORD)).status_code == 200
    # Front non compilé dans ce test : 503, mais la requête a bien passé le mot de passe.
    assert client.get("/locuteurs", headers=basic(PASSWORD)).status_code == 503


def test_health_stays_open_for_the_hosting_platform(tmp_path: Path) -> None:
    client = protected_client(tmp_path)

    assert client.get("/api/v1/health").status_code == 200
