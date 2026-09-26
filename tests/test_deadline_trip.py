from datetime import datetime, timedelta

import pytest

from bus_engine import BusSmartEngine, DEADLINE_BUFFER_MIN

# Pasir Ris Bus Interchange -> Tampines Mall (a real direct-route pair used
# elsewhere in this test suite)
DEMO_START = (1.373696, 103.94845)
DEMO_END = (1.352083, 103.945201)  # Tampines Mall, per places_aliases.json


@pytest.fixture(scope="module")
def engine():
    return BusSmartEngine()


def test_deadline_buffer_constant_matches_the_spec():
    assert DEADLINE_BUFFER_MIN == 5


def test_direct_trip_gets_a_depart_by_time(engine):
    plan = engine.plan_trip(*DEMO_START, *DEMO_END)
    assert plan.get('mode') == 'direct', "test assumes a direct route exists for this pair"

    now = datetime(2026, 1, 1, 12, 0)
    target_str = f"{(now.hour + 1):02d}:00"  # one hour from "now", comfortably reachable

    result = engine.plan_trip_by_deadline(*DEMO_START, *DEMO_END, target_str, now=now)

    assert 'depart_by' in result
    assert 'urgent' in result
    assert result['urgent'] is False


def test_urgent_when_deadline_has_already_passed(engine):
    now = datetime(2026, 1, 1, 12, 0)
    target_str = "11:00"  # an hour before "now" — impossible to make

    result = engine.plan_trip_by_deadline(*DEMO_START, *DEMO_END, target_str, now=now)

    assert result['urgent'] is True


def test_depart_by_accounts_for_travel_time_and_buffer(engine):
    plan = engine.plan_trip(*DEMO_START, *DEMO_END)
    best = plan['best']
    total_minutes = max(4, best['stops'] * 2) + best['walk_to_dest_min']

    now = datetime(2026, 1, 1, 10, 0)
    target_str = "15:00"

    result = engine.plan_trip_by_deadline(*DEMO_START, *DEMO_END, target_str, now=now)

    target_dt = datetime(2026, 1, 1, 15, 0)
    expected_depart = target_dt - timedelta(minutes=total_minutes + DEADLINE_BUFFER_MIN)
    assert result['depart_by'] == expected_depart.strftime('%H:%M')


def test_transfer_mode_passes_through_without_deadline_fields(engine, monkeypatch):
    monkeypatch.setattr(engine, 'plan_trip', lambda *a, **k: {
        'type': 'bus', 'mode': 'transfer', 'options': [{'leg1': {'service': '5'}, 'leg2': {'service': '9'}}],
    })

    result = engine.plan_trip_by_deadline(*DEMO_START, *DEMO_END, "15:00")

    assert 'depart_by' not in result
    assert 'urgent' not in result
    assert result['mode'] == 'transfer'


def test_walk_mode_passes_through_without_deadline_fields(engine, monkeypatch):
    monkeypatch.setattr(engine, 'plan_trip', lambda *a, **k: {'type': 'walk', 'minutes': 5, 'dist_m': 300})

    result = engine.plan_trip_by_deadline(*DEMO_START, *DEMO_END, "15:00")

    assert 'depart_by' not in result
    assert result['type'] == 'walk'


def test_none_mode_passes_through_without_deadline_fields(engine, monkeypatch):
    monkeypatch.setattr(engine, 'plan_trip', lambda *a, **k: {'type': 'none', 'message': 'no route'})

    result = engine.plan_trip_by_deadline(*DEMO_START, *DEMO_END, "15:00")

    assert 'depart_by' not in result
    assert result['type'] == 'none'


def test_direct_mode_with_no_best_passes_through(engine, monkeypatch):
    monkeypatch.setattr(engine, 'plan_trip', lambda *a, **k: {
        'type': 'bus', 'mode': 'direct', 'best': None, 'options': [],
    })

    result = engine.plan_trip_by_deadline(*DEMO_START, *DEMO_END, "15:00")

    assert 'depart_by' not in result
