import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_serves_i18n_js_from_static():
    response = client.get("/static/js/i18n.js")
    assert response.status_code == 200
    assert "translate" in response.text


@pytest.mark.parametrize(
    "path",
    [
        "/static/js/i18n.js",
        "/static/js/view-router.js",
        "/static/js/accessibility.js",
    ],
)
def test_serves_static_js_modules(path):
    response = client.get(path)
    assert response.status_code == 200


def test_index_references_all_static_js_modules():
    response = client.get("/")
    assert response.status_code == 200
    body = response.text
    assert '<script src="/static/js/i18n.js"></script>' in body
    assert '<script src="/static/js/view-router.js"></script>' in body
    assert '<script src="/static/js/accessibility.js"></script>' in body
