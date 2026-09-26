"""AI-backed kiosk features (voice-intent extraction, trip narration).

Every function here follows one rule, no exceptions: a failure — timeout,
network error, malformed response, rate limit, budget exhaustion — must never
propagate. It returns a safe fallback value instead, so the caller can proceed
exactly as if this module didn't exist. See the design spec's "Error handling
contract" section — this is the load-bearing property of the whole feature.
"""

import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()  # picks up ANTHROPIC_API_KEY from a .env file, if present. Also
                # called by bus_engine.py; python-dotenv is safe to call from
                # multiple modules — this makes ai_features.py self-sufficient
                # rather than relying on import order with bus_engine.py.


class RateLimiter:
    """Per-client sliding-window limiter. In-memory — this is a single-kiosk
    deployment, not a multi-tenant service, so no shared store is needed."""

    def __init__(self, max_calls, window_seconds, now_fn=time.monotonic):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._now = now_fn
        self._calls = defaultdict(list)

    def allow(self, client_id):
        now = self._now()
        cutoff = now - self.window_seconds
        recent = [t for t in self._calls[client_id] if t > cutoff]
        if len(recent) >= self.max_calls:
            self._calls[client_id] = recent
            return False
        recent.append(now)
        self._calls[client_id] = recent
        return True


class DailyBudget:
    """A hard cap on total AI calls per UTC day, across all clients. Trips
    once and disables the AI endpoints for the rest of the day rather than
    risking an open-ended bill."""

    def __init__(self, max_calls_per_day, now_fn=lambda: datetime.now(timezone.utc).timestamp()):
        self.max_calls_per_day = max_calls_per_day
        self._now = now_fn
        self._day_start = None
        self._count = 0

    def _current_day(self, now):
        return int(now // 86400)

    def _roll_if_new_day(self):
        now = self._now()
        day = self._current_day(now)
        if self._day_start != day:
            self._day_start = day
            self._count = 0

    def consume(self):
        self._roll_if_new_day()
        if self._count >= self.max_calls_per_day:
            return False
        self._count += 1
        return True

    @property
    def remaining(self):
        self._roll_if_new_day()
        return max(0, self.max_calls_per_day - self._count)


# Shared instances used by main.py. Values are env-configurable so the caps
# can be tuned per deployment without a code change.
voice_intent_limiter = RateLimiter(
    max_calls=int(os.getenv('AI_RATE_LIMIT_MAX_CALLS', '20')),
    window_seconds=int(os.getenv('AI_RATE_LIMIT_WINDOW_SECONDS', '60')),
)
narrate_trip_limiter = RateLimiter(
    max_calls=int(os.getenv('AI_RATE_LIMIT_MAX_CALLS', '20')),
    window_seconds=int(os.getenv('AI_RATE_LIMIT_WINDOW_SECONDS', '60')),
)
daily_budget = DailyBudget(
    max_calls_per_day=int(os.getenv('AI_DAILY_CALL_BUDGET', '2000')),
)
