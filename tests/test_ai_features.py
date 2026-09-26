import json
from unittest.mock import MagicMock

import pytest

import ai_features
from ai_features import RateLimiter, DailyBudget, extract_voice_intent


def test_rate_limiter_allows_up_to_the_limit():
    clock = [0.0]
    limiter = RateLimiter(max_calls=3, window_seconds=60, now_fn=lambda: clock[0])

    assert limiter.allow('1.2.3.4') is True
    assert limiter.allow('1.2.3.4') is True
    assert limiter.allow('1.2.3.4') is True
    assert limiter.allow('1.2.3.4') is False, "4th call within the window must be rejected"


def test_rate_limiter_resets_after_the_window_passes():
    clock = [0.0]
    limiter = RateLimiter(max_calls=1, window_seconds=60, now_fn=lambda: clock[0])

    assert limiter.allow('1.2.3.4') is True
    assert limiter.allow('1.2.3.4') is False
    clock[0] = 61.0
    assert limiter.allow('1.2.3.4') is True, "window has fully elapsed, should reset"


def test_rate_limiter_tracks_clients_independently():
    limiter = RateLimiter(max_calls=1, window_seconds=60, now_fn=lambda: 0.0)

    assert limiter.allow('1.2.3.4') is True
    assert limiter.allow('5.6.7.8') is True, "a different client must not share the first one's quota"


def test_daily_budget_allows_up_to_the_cap():
    budget = DailyBudget(max_calls_per_day=2, now_fn=lambda: 1000.0)

    assert budget.consume() is True
    assert budget.consume() is True
    assert budget.consume() is False, "3rd call today must be rejected"


def test_daily_budget_resets_on_a_new_day():
    clock = [1000.0]
    budget = DailyBudget(max_calls_per_day=1, now_fn=lambda: clock[0])

    assert budget.consume() is True
    assert budget.consume() is False
    clock[0] = 1000.0 + 86400  # one day later
    assert budget.consume() is True, "a new UTC day must reset the counter"


def test_daily_budget_remaining_reflects_consumption():
    budget = DailyBudget(max_calls_per_day=5, now_fn=lambda: 1000.0)

    assert budget.remaining == 5
    budget.consume()
    assert budget.remaining == 4


class _FakeTextBlock:
    def __init__(self, text):
        self.type = 'text'
        self.text = text


def _fake_response(payload_dict):
    response = MagicMock()
    response.content = [_FakeTextBlock(json.dumps(payload_dict))]
    return response


def test_extract_voice_intent_parses_a_well_formed_response(monkeypatch):
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_response({
        'destination_query': 'changi general hospital',
        'target_arrival_time': '15:00',
        'confidence': 'high',
    })
    monkeypatch.setattr(ai_features, '_get_anthropic_client', lambda: fake_client)

    result = extract_voice_intent('i need to be at changi general hospital by 3pm', 'en')

    assert result == {
        'destination_query': 'changi general hospital',
        'target_arrival_time': '15:00',
        'confidence': 'high',
    }
    fake_client.messages.create.assert_called_once()
    call_kwargs = fake_client.messages.create.call_args.kwargs
    assert call_kwargs['model'] == 'claude-haiku-4-5'


def test_extract_voice_intent_defaults_missing_fields_to_none(monkeypatch):
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_response({
        'destination_query': 'white sands',
    })
    monkeypatch.setattr(ai_features, '_get_anthropic_client', lambda: fake_client)

    result = extract_voice_intent('take me to white sands', 'en')

    assert result['destination_query'] == 'white sands'
    assert result['target_arrival_time'] is None
    assert result['confidence'] == 'low'


def test_extract_voice_intent_falls_back_when_client_is_unavailable(monkeypatch):
    monkeypatch.setattr(ai_features, '_get_anthropic_client', lambda: None)

    result = extract_voice_intent('anything', 'en')

    assert result == {'destination_query': None, 'target_arrival_time': None, 'confidence': 'low'}


def test_extract_voice_intent_falls_back_on_api_error(monkeypatch):
    fake_client = MagicMock()
    fake_client.messages.create.side_effect = RuntimeError('network exploded')
    monkeypatch.setattr(ai_features, '_get_anthropic_client', lambda: fake_client)

    result = extract_voice_intent('anything', 'en')

    assert result == {'destination_query': None, 'target_arrival_time': None, 'confidence': 'low'}


def test_extract_voice_intent_falls_back_on_malformed_json(monkeypatch):
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_response.__wrapped__ if False else None
    response = MagicMock()
    response.content = [_FakeTextBlock('not json at all')]
    fake_client.messages.create.return_value = response
    monkeypatch.setattr(ai_features, '_get_anthropic_client', lambda: fake_client)

    result = extract_voice_intent('anything', 'en')

    assert result == {'destination_query': None, 'target_arrival_time': None, 'confidence': 'low'}


def test_extract_voice_intent_falls_back_when_time_is_not_hh_mm(monkeypatch):
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_response({
        'destination_query': 'changi airport',
        'target_arrival_time': 'sometime this afternoon',
        'confidence': 'high',
    })
    monkeypatch.setattr(ai_features, '_get_anthropic_client', lambda: fake_client)

    result = extract_voice_intent('go to changi airport this afternoon', 'en')

    assert result['destination_query'] == 'changi airport'
    assert result['target_arrival_time'] is None, "an unparseable time must not reach the caller"


from ai_features import narrate_trip


def test_narrate_trip_returns_the_model_text(monkeypatch):
    fake_client = MagicMock()
    response = MagicMock()
    response.content = [_FakeTextBlock('Walk to Berth B1, board the blue 53, about 8 stops.')]
    fake_client.messages.create.return_value = response
    monkeypatch.setattr(ai_features, '_get_anthropic_client', lambda: fake_client)

    trip_fields = {
        'service': '53', 'stops': 8, 'berth': 'B1',
        'walk_to_dest_min': 2, 'from_name': 'Pasir Ris Int', 'to_name': 'Tampines Mall',
    }
    result = narrate_trip(trip_fields, 'en')

    assert result == 'Walk to Berth B1, board the blue 53, about 8 stops.'
    call_kwargs = fake_client.messages.create.call_args.kwargs
    assert call_kwargs['model'] == 'claude-haiku-4-5'
    assert '"service": "53"' in call_kwargs['messages'][0]['content'] or "'53'" in str(call_kwargs['messages'])


def test_narrate_trip_returns_none_when_client_unavailable(monkeypatch):
    monkeypatch.setattr(ai_features, '_get_anthropic_client', lambda: None)

    assert narrate_trip({'service': '53', 'stops': 8}, 'en') is None


def test_narrate_trip_returns_none_on_api_error(monkeypatch):
    fake_client = MagicMock()
    fake_client.messages.create.side_effect = RuntimeError('boom')
    monkeypatch.setattr(ai_features, '_get_anthropic_client', lambda: fake_client)

    assert narrate_trip({'service': '53', 'stops': 8}, 'en') is None


def test_narrate_trip_returns_none_when_response_is_empty(monkeypatch):
    fake_client = MagicMock()
    response = MagicMock()
    response.content = []
    fake_client.messages.create.return_value = response
    monkeypatch.setattr(ai_features, '_get_anthropic_client', lambda: fake_client)

    assert narrate_trip({'service': '53', 'stops': 8}, 'en') is None


def test_narrate_trip_includes_deadline_fields_when_present(monkeypatch):
    fake_client = MagicMock()
    response = MagicMock()
    response.content = [_FakeTextBlock('Leave by 1:40pm to make your 3pm appointment.')]
    fake_client.messages.create.return_value = response
    monkeypatch.setattr(ai_features, '_get_anthropic_client', lambda: fake_client)

    trip_fields = {
        'service': '53', 'stops': 8, 'berth': 'B1', 'walk_to_dest_min': 2,
        'from_name': 'Pasir Ris Int', 'to_name': 'Changi General Hospital',
        'depart_by': '13:40', 'urgent': False,
    }
    result = narrate_trip(trip_fields, 'en')

    assert result == 'Leave by 1:40pm to make your 3pm appointment.'
    sent_content = str(fake_client.messages.create.call_args.kwargs['messages'])
    assert '13:40' in sent_content
