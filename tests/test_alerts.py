import logging

import pytest

from bus_engine import BusSmartEngine


@pytest.fixture(scope="module")
def engine():
    return BusSmartEngine()


# These three "Alerts" feeds all failed silently before this fix: any missing
# key or failed request was swallowed by a bare `except Exception: return []`,
# so an empty ticker was indistinguishable from "no active incidents." That's
# exactly what was happening in this environment — LTA_API_KEY was never set.

@pytest.mark.parametrize("method_name", [
    "get_traffic_incidents",
    "get_train_service_alerts",
    "get_facilities_maintenance",
])
def test_missing_api_key_logs_a_warning_instead_of_failing_silently(engine, monkeypatch, caplog, method_name):
    monkeypatch.delenv("LTA_API_KEY", raising=False)
    with caplog.at_level(logging.WARNING):
        result = getattr(engine, method_name)()
    assert result == []
    assert any("LTA_API_KEY" in record.message for record in caplog.records)


@pytest.mark.parametrize("method_name", [
    "get_traffic_incidents",
    "get_train_service_alerts",
    "get_facilities_maintenance",
])
def test_request_failure_logs_the_error_instead_of_failing_silently(engine, monkeypatch, caplog, method_name):
    monkeypatch.setenv("LTA_API_KEY", "test-key")

    def boom(*args, **kwargs):
        raise ConnectionError("simulated network failure")

    monkeypatch.setattr("bus_engine.requests.get", boom)
    with caplog.at_level(logging.WARNING):
        result = getattr(engine, method_name)()
    assert result == []
    assert any("simulated network failure" in record.message for record in caplog.records)
