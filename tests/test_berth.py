import pytest

from bus_engine import BusSmartEngine


@pytest.fixture(scope="module")
def engine():
    return BusSmartEngine()


def test_get_berth_known_stop_and_service(engine):
    assert engine.get_berth('77009', '58') == 'B1'


def test_get_berth_coerces_int_service_no(engine):
    assert engine.get_berth('77009', 58) == 'B1'


def test_get_berth_unknown_service_at_known_stop(engine):
    assert engine.get_berth('77009', '999') is None


def test_get_berth_unknown_stop(engine):
    assert engine.get_berth('00000', '58') is None


def test_get_berth_returns_none_when_service_uses_two_berths(engine):
    """359 boards at B4 (west loop) and B6 (east loop). Our route data has no
    loop-direction field, so naming one berth would be wrong half the time."""
    assert engine.get_berth('77009', '359') is None
    assert engine.get_berth('77009', '358') is None


def test_get_berth_options_lists_every_berth_for_a_service(engine):
    assert engine.get_berth_options('77009', '359') == ['B4', 'B6']
    assert engine.get_berth_options('77009', '358') == ['B5', 'B7']


def test_get_berth_options_single_berth_service(engine):
    assert engine.get_berth_options('77009', '58') == ['B1']


def test_get_berth_options_unknown_service(engine):
    assert engine.get_berth_options('77009', '999') == []


def test_loop_services_are_registered_at_both_berths(engine):
    """Regression: 359 was missing from B6 and 358 from B7 entirely."""
    berths = {e['berth']: e['services'] for e in engine.berth_map['77009']['boarding']}
    assert '359' in berths['B4'] and '359' in berths['B6']
    assert '358' in berths['B5'] and '358' in berths['B7']


def test_every_berth_carries_signage_labels(engine):
    """displayServices are what the real interchange signage shows (e.g. 359W)."""
    for entry in engine.berth_map['77009']['boarding']:
        assert 'displayServices' in entry, f"{entry['berth']} missing displayServices"
