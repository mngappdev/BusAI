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


def test_serves_speech_errors_module():
    response = client.get("/static/js/speech-errors.js")
    assert response.status_code == 200
    assert "classify" in response.text


def test_index_loads_speech_errors_before_use():
    """onerror calls KioskSpeechErrors; if the tag is missing the handler
    throws and the kiosk shows nothing at all."""
    body = client.get("/").text
    assert '<script src="/static/js/speech-errors.js"></script>' in body
    assert "KioskSpeechErrors.classify" in body
