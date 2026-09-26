from unittest.mock import MagicMock

import ai_features
import main
from main import app
from fastapi.testclient import TestClient

client = TestClient(app)

# main.py calls ai_features.extract_voice_intent(...) / ai_features.narrate_trip(...)
# through the module reference (never `from ai_features import extract_voice_intent`)
# specifically so that patching ai_features.<name> here actually takes effect. A
# bare-name import would bind its own copy at import time and silently ignore
# these patches — the endpoint would call the real function instead of the fake
# one, and a happy-path test could pass for the wrong reason.


def test_voice_intent_endpoint_returns_extraction(monkeypatch):
    monkeypatch.setattr(
        ai_features, 'extract_voice_intent',
        lambda text, lang: {'destination_query': 'white sands', 'target_arrival_time': None, 'confidence': 'high'},
    )

    response = client.post('/api/v1/voice-intent', json={'text': 'take me to white sands', 'lang': 'en'})

    assert response.status_code == 200
    assert response.json() == {'destination_query': 'white sands', 'target_arrival_time': None, 'confidence': 'high'}


def test_voice_intent_endpoint_rejects_rate_limited_client(monkeypatch):
    monkeypatch.setattr(main.ai_features.voice_intent_limiter, 'allow', lambda client_id: False)

    response = client.post('/api/v1/voice-intent', json={'text': 'anything', 'lang': 'en'})

    assert response.status_code == 200, "a rate-limited call must still return a safe fallback, not an error"
    assert response.json() == {'destination_query': None, 'target_arrival_time': None, 'confidence': 'low'}


def test_voice_intent_endpoint_rejects_when_daily_budget_exhausted(monkeypatch):
    monkeypatch.setattr(main.ai_features.daily_budget, 'consume', lambda: False)

    response = client.post('/api/v1/voice-intent', json={'text': 'anything', 'lang': 'en'})

    assert response.status_code == 200
    assert response.json() == {'destination_query': None, 'target_arrival_time': None, 'confidence': 'low'}


def test_narrate_trip_endpoint_returns_narrative(monkeypatch):
    monkeypatch.setattr(ai_features, 'narrate_trip', lambda fields, lang: 'A short narration.')

    response = client.post('/api/v1/narrate-trip', json={
        'trip': {'service': '53', 'stops': 8, 'walk_to_dest_min': 2, 'from_name': 'A', 'to_name': 'B'},
        'lang': 'en',
    })

    assert response.status_code == 200
    assert response.json() == {'narrative': 'A short narration.'}


def test_narrate_trip_endpoint_returns_null_narrative_on_failure(monkeypatch):
    monkeypatch.setattr(ai_features, 'narrate_trip', lambda fields, lang: None)

    response = client.post('/api/v1/narrate-trip', json={
        'trip': {'service': '53', 'stops': 8, 'walk_to_dest_min': 2, 'from_name': 'A', 'to_name': 'B'},
        'lang': 'en',
    })

    assert response.status_code == 200
    assert response.json() == {'narrative': None}


def test_narrate_trip_endpoint_rate_limited(monkeypatch):
    monkeypatch.setattr(main.ai_features.narrate_trip_limiter, 'allow', lambda client_id: False)

    response = client.post('/api/v1/narrate-trip', json={
        'trip': {'service': '53', 'stops': 8, 'walk_to_dest_min': 2, 'from_name': 'A', 'to_name': 'B'},
        'lang': 'en',
    })

    assert response.status_code == 200
    assert response.json() == {'narrative': None}


def test_plan_by_deadline_endpoint_returns_the_engine_result():
    response = client.post('/api/v1/plan-by-deadline', json={
        's_lat': 1.373696, 's_lon': 103.94845,
        'e_lat': 1.3575, 'e_lon': 103.9885,
        'target_arrival_time': '23:59',
    })

    assert response.status_code == 200
    body = response.json()
    assert 'depart_by' in body or body.get('type') != 'bus'  # direct trips get depart_by; others pass through


def test_plan_by_deadline_endpoint_rejects_malformed_time():
    response = client.post('/api/v1/plan-by-deadline', json={
        's_lat': 1.373696, 's_lon': 103.94845,
        'e_lat': 1.3575, 'e_lon': 103.9885,
        'target_arrival_time': 'not-a-time',
    })

    assert response.status_code == 422
