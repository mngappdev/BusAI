from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_serves_i18n_js_from_static():
    response = client.get("/static/js/i18n.js")
    assert response.status_code == 200
    assert "translate" in response.text
