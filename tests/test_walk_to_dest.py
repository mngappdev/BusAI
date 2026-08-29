import pytest

import bus_engine
from bus_engine import BusSmartEngine


# Pasir Ris Bus Interchange -> Changi Airport T2 (the kiosk demo journey)
DEMO_START = (1.373696, 103.94845)
DEMO_END = (1.3575, 103.9885)


@pytest.fixture(scope="module")
def engine():
    return BusSmartEngine()


@pytest.fixture
def offline_engine(engine, monkeypatch):
    """The same engine with OneMap unreachable, so the fallback path is exercised."""
    monkeypatch.delenv('ONEMAP_EMAIL', raising=False)
    monkeypatch.delenv('ONEMAP_PASSWORD', raising=False)
    monkeypatch.delenv('ONEMAP_EMAIL_PASSWORD', raising=False)
    monkeypatch.setattr(engine, '_walk_cache', {})
    return engine


@pytest.mark.parametrize('password_var', ['ONEMAP_PASSWORD', 'ONEMAP_EMAIL_PASSWORD'])
def test_either_password_variable_name_authenticates(engine, monkeypatch, password_var):
    """Azure and the local setup script spell the password variable differently."""
    monkeypatch.delenv('ONEMAP_PASSWORD', raising=False)
    monkeypatch.delenv('ONEMAP_EMAIL_PASSWORD', raising=False)
    monkeypatch.setenv('ONEMAP_EMAIL', 'kiosk@example.org')
    monkeypatch.setenv(password_var, 'secret')
    monkeypatch.setattr(engine, '_onemap_auth', None)

    sent = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {'access_token': 'tok', 'expiry_timestamp': '99999999999'}

    def fake_post(url, **kwargs):
        sent.update(kwargs.get('json') or {})
        return FakeResponse()

    monkeypatch.setattr(bus_engine.requests, 'post', fake_post)

    assert engine._get_onemap_token() == 'tok'
    assert sent == {'email': 'kiosk@example.org', 'password': 'secret'}


# ─── The reported bug ─────────────────────────────────────────────────────────

def test_walk_to_dest_is_not_derived_from_on_bus_distance(engine):
    """Regression: the walk leg once showed 101 min because it scaled dist_km by 12."""
    best = engine.plan_trip(*DEMO_START, *DEMO_END)['best']

    assert best['dist_km'] > 5, "demo journey should still be a long bus ride"
    assert best['walk_to_dest_min'] != round(best['dist_km'] * 12)
    assert best['walk_to_dest_min'] <= 10


def test_walk_is_measured_from_the_alighting_stop(engine):
    """Whatever the source, the walk must be in the neighbourhood of the alight stop."""
    best = engine.plan_trip(*DEMO_START, *DEMO_END)['best']
    alight = engine.stop_map[best['to_code']]
    straight_m = engine.haversine(
        alight['Latitude'], alight['Longitude'], DEMO_END[0], DEMO_END[1]
    )

    # A street route is never shorter than the straight line, and never wildly longer.
    assert straight_m <= best['walk_to_dest_m'] <= straight_m * 3 + 100
    assert best['walk_to_dest_min'] == max(
        1, round(best['walk_to_dest_m'] / bus_engine.WALK_SPEED_M_PER_MIN)
    )


def test_every_direct_option_carries_walk_to_dest(engine):
    for opt in engine.plan_trip(*DEMO_START, *DEMO_END)['options']:
        assert opt['walk_to_dest_m'] >= 0
        assert opt['walk_to_dest_min'] >= 1
        assert opt['walk_source'] in {'onemap', 'estimate'}


# ─── OneMap routing ───────────────────────────────────────────────────────────

def test_walking_route_uses_onemap_network_distance(engine, monkeypatch):
    monkeypatch.setattr(engine, '_walk_cache', {})
    monkeypatch.setattr(engine, '_get_onemap_token', lambda: 'test-token')

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {'route_summary': {'total_distance': 240, 'total_time': 190}}

    def fake_get(url, **kwargs):
        captured['url'] = url
        captured['params'] = kwargs.get('params')
        captured['headers'] = kwargs.get('headers')
        return FakeResponse()

    monkeypatch.setattr(bus_engine.requests, 'get', fake_get)
    walk = engine.walking_route(1.3575, 103.9885, 1.3585, 103.9880)

    assert walk == {'distance_m': 240, 'minutes': 3, 'source': 'onemap'}
    assert captured['params']['routeType'] == 'walk'
    assert captured['params']['start'] == '1.3575,103.9885'
    assert captured['headers']['Authorization'] == 'test-token'


def test_onemap_results_are_cached(engine, monkeypatch):
    monkeypatch.setattr(engine, '_walk_cache', {})
    monkeypatch.setattr(engine, '_get_onemap_token', lambda: 'test-token')
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {'route_summary': {'total_distance': 500}}

    def fake_get(url, **kwargs):
        calls.append(url)
        return FakeResponse()

    monkeypatch.setattr(bus_engine.requests, 'get', fake_get)
    first = engine.walking_route(1.3575, 103.9885, 1.3585, 103.9880)
    second = engine.walking_route(1.3575, 103.9885, 1.3585, 103.9880)

    assert first == second
    assert len(calls) == 1, "second identical lookup should hit the cache"


# ─── Fallback when OneMap is unavailable ──────────────────────────────────────

def test_falls_back_to_padded_straight_line_without_credentials(offline_engine):
    walk = offline_engine.walking_route(1.3575, 103.9885, 1.3585, 103.9880)
    straight_m = offline_engine.haversine(1.3575, 103.9885, 1.3585, 103.9880)

    assert walk['source'] == 'estimate'
    assert walk['distance_m'] == round(straight_m * bus_engine.WALK_DETOUR_FACTOR)
    assert walk['minutes'] >= 1


def test_falls_back_when_onemap_errors(engine, monkeypatch):
    monkeypatch.setattr(engine, '_walk_cache', {})
    monkeypatch.setattr(engine, '_get_onemap_token', lambda: 'test-token')

    def boom(url, **kwargs):
        raise bus_engine.requests.RequestException('OneMap down')

    monkeypatch.setattr(bus_engine.requests, 'get', boom)
    walk = engine.walking_route(1.3575, 103.9885, 1.3585, 103.9880)

    assert walk['source'] == 'estimate'
    assert walk['minutes'] >= 1


def test_failed_lookup_is_not_cached(engine, monkeypatch):
    """A transient OneMap outage must not poison the cache for the whole session."""
    monkeypatch.setattr(engine, '_walk_cache', {})
    monkeypatch.setattr(engine, '_get_onemap_token', lambda: 'test-token')

    def boom(url, **kwargs):
        raise bus_engine.requests.RequestException('OneMap down')

    monkeypatch.setattr(bus_engine.requests, 'get', boom)
    engine.walking_route(1.3575, 103.9885, 1.3585, 103.9880)

    assert engine._walk_cache == {}


def test_missing_credentials_skip_the_network_entirely(offline_engine, monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError('should not call OneMap without credentials')

    monkeypatch.setattr(bus_engine.requests, 'get', fail)
    monkeypatch.setattr(bus_engine.requests, 'post', fail)

    assert offline_engine.walking_route(1.3575, 103.9885, 1.3585, 103.9880)['source'] == 'estimate'


# ─── Latency guard ────────────────────────────────────────────────────────────

def test_only_displayed_options_get_a_live_lookup(engine, monkeypatch):
    monkeypatch.setattr(engine, '_walk_cache', {})
    lookups = []

    def fake_walk(s_lat, s_lon, e_lat, e_lon, allow_network=True):
        lookups.append(allow_network)
        return {'distance_m': 100, 'minutes': 2, 'source': 'estimate'}

    monkeypatch.setattr(engine, 'walking_route', fake_walk)
    legs = [{'to_code': code} for code in list(engine.stop_map)[:6]]
    engine._attach_walk_to_dest(legs, *DEMO_END)

    assert lookups[:3] == [True, True, True]
    assert all(allowed is False for allowed in lookups[3:])
