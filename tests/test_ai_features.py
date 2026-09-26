import pytest

from ai_features import RateLimiter, DailyBudget


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
