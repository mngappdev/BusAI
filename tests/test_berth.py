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
