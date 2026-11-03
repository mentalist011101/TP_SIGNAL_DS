from flask.testing import FlaskClient

from echolens import __version__


def test_health(client: FlaskClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "version": __version__}


def test_openapi_spec_is_served(client: FlaskClient) -> None:
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    assert "/api/v1/health" in response.get_json()["paths"]


def test_unknown_api_route_is_404(client: FlaskClient) -> None:
    assert client.get("/api/v1/inexistant").status_code == 404


def test_frontend_missing_build_returns_503(client: FlaskClient) -> None:
    response = client.get("/")
    assert response.status_code == 503
    assert "make web-build" in response.get_data(as_text=True)
