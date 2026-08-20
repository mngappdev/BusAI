import pytest

from bus_engine import BusSmartEngine


@pytest.fixture(scope="module")
def engine():
    return BusSmartEngine()


def test_format_leg_includes_berth_for_a_mapped_service(engine):
    routes_at_stop = [r for r in engine.stop_to_routes['77009'] if r['ServiceNo'] == '58']
    assert routes_at_stop, 'service 58 should stop at 77009 in the fixture data'
    r_start = routes_at_stop[0]
    leg = engine._format_leg('77009', '77009', r_start, r_start)
    assert leg['berth'] == 'B1'


def test_format_leg_berth_is_none_for_an_unmapped_stop(engine):
    routes_at_stop = engine.stop_to_routes.get('01012')
    assert routes_at_stop, 'stop 01012 should have at least one route in the fixture data'
    r_start = routes_at_stop[0]
    leg = engine._format_leg('01012', '01012', r_start, r_start)
    assert leg['berth'] is None
