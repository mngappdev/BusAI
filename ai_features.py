"""AI-backed kiosk features (voice-intent extraction, trip narration).

Every function here follows one rule, no exceptions: a failure — timeout,
network error, malformed response, rate limit, budget exhaustion — must never
propagate. It returns a safe fallback value instead, so the caller can proceed
exactly as if this module didn't exist. See the design spec's "Error handling
contract" section — this is the load-bearing property of the whole feature.
"""

import json
import logging
import os
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from dotenv import load_dotenv

import anthropic

load_dotenv()  # picks up ANTHROPIC_API_KEY from a .env file, if present. Also
                # called by bus_engine.py; python-dotenv is safe to call from
                # multiple modules — this makes ai_features.py self-sufficient
                # rather than relying on import order with bus_engine.py.

logger = logging.getLogger(__name__)


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


_HH_MM_RE = re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')
_FALLBACK_INTENT = {'destination_query': None, 'target_arrival_time': None, 'confidence': 'low'}

_anthropic_client = None
_anthropic_client_checked = False


def _get_anthropic_client():
    """Lazily build the Anthropic client. Returns None (never raises) when no
    API key is configured, so callers can treat "no key" the same as "call
    failed" — both fall back."""
    global _anthropic_client, _anthropic_client_checked
    if _anthropic_client_checked:
        return _anthropic_client
    _anthropic_client_checked = True
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        return None
    _anthropic_client = anthropic.Anthropic(api_key=api_key, timeout=8.0)
    return _anthropic_client


def _first_text(response):
    for block in response.content:
        if getattr(block, 'type', None) == 'text':
            return block.text
    return None


VOICE_INTENT_SYSTEM_PROMPT = """You extract structured intent from a Singapore bus \
kiosk voice query. The commuter spoke this sentence aloud; you see only the transcript.

Respond with ONLY a JSON object (no markdown fences, no explanation), exactly this shape:
{"destination_query": string or null, "target_arrival_time": string or null, "confidence": "high" or "low"}

Rules:
- destination_query: the place name the commuter wants to go, in their own words. null if no destination is mentioned at all.
- target_arrival_time: a 24-hour "HH:MM" time ONLY IF the commuter stated a specific deadline or appointment time (e.g. "by 3pm", "before 15:30"). null if no time was mentioned. NEVER invent or infer a time that wasn't said.
- confidence: "high" only if you are confident of the destination_query extraction. "low" otherwise.
"""


def extract_voice_intent(text, lang):
    client = _get_anthropic_client()
    if client is None:
        return dict(_FALLBACK_INTENT)

    try:
        response = client.messages.create(
            model='claude-haiku-4-5',
            max_tokens=200,
            system=VOICE_INTENT_SYSTEM_PROMPT,
            messages=[{'role': 'user', 'content': f'Language: {lang}\nTranscript: {text}'}],
        )
        raw_text = _first_text(response)
        if not raw_text:
            return dict(_FALLBACK_INTENT)

        parsed = json.loads(raw_text)
        destination_query = parsed.get('destination_query')
        if not isinstance(destination_query, str) or not destination_query.strip():
            destination_query = None

        target_arrival_time = parsed.get('target_arrival_time')
        if not isinstance(target_arrival_time, str) or not _HH_MM_RE.match(target_arrival_time):
            target_arrival_time = None

        confidence = 'high' if parsed.get('confidence') == 'high' else 'low'

        return {
            'destination_query': destination_query,
            'target_arrival_time': target_arrival_time,
            'confidence': confidence,
        }
    except Exception:
        logger.exception('voice-intent extraction failed; falling back')
        return dict(_FALLBACK_INTENT)
