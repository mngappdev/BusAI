# Deadline-Aware Trip Planning + AI Trip Narration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two Claude-backed kiosk features — extracting a destination + optional deadline time from free speech, and a short spoken trip narration — as additive, fallback-first layers over the existing, unmodified voice and trip-planning flow.

**Architecture:** Three new stateless backend endpoints (`/api/v1/voice-intent`, `/api/v1/plan-by-deadline`, `/api/v1/narrate-trip`) plus a small frontend module wrapping them with a hard client-side timeout. Every failure mode of every new piece must fall back to exactly today's behavior — this is checked by name in nearly every task below.

**Tech Stack:** FastAPI + Pydantic (backend), `anthropic` Python SDK (Claude Haiku 4.5, `claude-haiku-4-5`), vanilla JS with `node --test` (frontend), pytest with `TestClient` + `monkeypatch` (backend tests).

**Spec:** `docs/superpowers/specs/2026-09-26-deadline-trip-and-narration-design.md`

## Global Constraints

- Model for both AI calls: `claude-haiku-4-5` (fast, cheap — matches the spec's cost/latency budget). Do not use a different model without the spec being updated first.
- Every AI call is wrapped in a broad `except Exception: return <safe fallback>` — this codebase's established idiom (see `bus_engine.py`'s `get_realtime_arrivals`). No exception from an AI call may propagate to a caller.
- No test in this plan makes a real call to the Anthropic API. All Anthropic client usage is mocked/monkeypatched.
- `ANTHROPIC_API_KEY` is read via `os.getenv` after `load_dotenv()` — never hardcoded, never sent to the client (`index.html`/`static/js/*.js`).
- Deadline math (`plan_trip_by_deadline`) covers `mode: 'direct'` trips only. `mode: 'transfer'`, `type: 'walk'`, and `type: 'none'` responses pass through with no `depart_by`/`urgent` fields added.
- `DEADLINE_BUFFER_MIN = 5` (module constant in `bus_engine.py`, next to `WALK_SPEED_M_PER_MIN`).
- Existing functions/methods this plan must NOT change the signature or behavior of: `plan_trip`, `resolve_place`, `resolveLocationFromText` (JS), `renderTripSummary` (JS) — all are wrapped or called conditionally, never rewritten.

---

### Task 1: AI feature module scaffold — rate limiter + daily budget

**Files:**
- Create: `ai_features.py`
- Test: `tests/test_ai_features.py`

**Interfaces:**
- Consumes: nothing (pure, in-memory, no external calls)
- Produces: `RateLimiter` class with `.allow(client_id: str) -> bool`; `DailyBudget` class with `.consume() -> bool` and `.remaining -> int` property. Both take an injectable `now_fn` for deterministic tests (default `time.monotonic` / `datetime.now`).

This task has no Anthropic dependency at all — it's the safety layer both AI endpoints will sit behind, built and tested first so later tasks can rely on it.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ai_features.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ai_features.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ai_features'`

- [ ] **Step 3: Write the implementation**

Create `ai_features.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_ai_features.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add ai_features.py tests/test_ai_features.py
git commit -m "feat: rate limiter and daily budget for upcoming AI endpoints

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: Voice-intent extraction (Claude call)

**Files:**
- Modify: `ai_features.py`
- Modify: `requirements.txt`
- Test: `tests/test_ai_features.py`

**Interfaces:**
- Consumes: nothing new from earlier tasks
- Produces: `extract_voice_intent(text: str, lang: str) -> dict` — always returns a dict shaped `{"destination_query": str | None, "target_arrival_time": str | None, "confidence": "high" | "low"}`. Never raises. On any failure, returns `{"destination_query": None, "target_arrival_time": None, "confidence": "low"}`.

- [ ] **Step 1: Add `anthropic` to requirements.txt**

```bash
echo anthropic >> requirements.txt
pip install anthropic
```

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_ai_features.py`:

```python
import json
from unittest.mock import MagicMock

import ai_features
from ai_features import extract_voice_intent


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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_ai_features.py -k voice_intent -v`
Expected: FAIL with `ImportError: cannot import name 'extract_voice_intent'`

- [ ] **Step 4: Write the implementation**

Append to `ai_features.py` (add these imports to the top of the file alongside the existing ones):

```python
import json
import logging
import re

import anthropic

logger = logging.getLogger(__name__)

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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_ai_features.py -v`
Expected: PASS (all tests, including Task 1's)

- [ ] **Step 6: Commit**

```bash
git add ai_features.py requirements.txt tests/test_ai_features.py
git commit -m "feat: voice-intent extraction via Claude Haiku 4.5, fallback-first

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: Trip narration (Claude call)

**Files:**
- Modify: `ai_features.py`
- Test: `tests/test_ai_features.py`

**Interfaces:**
- Consumes: `_get_anthropic_client()`, `_first_text()` from Task 2
- Produces: `narrate_trip(trip_fields: dict, lang: str) -> str | None` — a short narrative string, or `None` on any failure (caller must have its own fallback text ready).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_ai_features.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ai_features.py -k narrate_trip -v`
Expected: FAIL with `ImportError: cannot import name 'narrate_trip'`

- [ ] **Step 3: Write the implementation**

Append to `ai_features.py`:

```python
NARRATE_TRIP_SYSTEM_PROMPT = """You narrate a Singapore bus trip for a kiosk to speak \
aloud to a commuter. You will receive the trip's already-computed fields as JSON — \
treat them as ground truth, do not invent or alter any detail (service number, stop \
count, berth, names). Reply with 2-3 short, calm sentences in the requested language: \
mention the walk to the berth, which bus service to board, roughly how many stops, and \
— only if a depart_by field is present — when to leave. Reply with plain sentences only, \
no JSON, no markdown, no preamble."""


def narrate_trip(trip_fields, lang):
    client = _get_anthropic_client()
    if client is None:
        return None

    try:
        response = client.messages.create(
            model='claude-haiku-4-5',
            max_tokens=300,
            system=NARRATE_TRIP_SYSTEM_PROMPT,
            messages=[{
                'role': 'user',
                'content': f'Language: {lang}\nTrip fields: {json.dumps(trip_fields)}',
            }],
        )
        text = _first_text(response)
        if not text or not text.strip():
            return None
        return text.strip()
    except Exception:
        logger.exception('trip narration failed; falling back')
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_ai_features.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add ai_features.py tests/test_ai_features.py
git commit -m "feat: AI trip narration via Claude Haiku 4.5, fallback-first

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 4: Deadline trip math in `bus_engine.py`

**Files:**
- Modify: `bus_engine.py`
- Test: `tests/test_deadline_trip.py`

**Interfaces:**
- Consumes: `self.plan_trip(s_lat, s_lon, e_lat, e_lon)` (existing, unmodified — returns a dict with `type`, and for `type: 'bus', mode: 'direct'` also `best` containing `stops`, `walk_to_dest_min`, `service`, etc.)
- Produces: `BusSmartEngine.plan_trip_by_deadline(s_lat, s_lon, e_lat, e_lon, target_arrival_time: str, now: datetime | None = None) -> dict`. Returns the same shape as `plan_trip`, with `depart_by: str` ("HH:MM") and `urgent: bool` added ONLY when `mode == 'direct'` and a `best` option exists. `now` is injectable for deterministic tests; defaults to `datetime.now()`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_deadline_trip.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_deadline_trip.py -v`
Expected: FAIL with `ImportError: cannot import name 'DEADLINE_BUFFER_MIN'`

- [ ] **Step 3: Write the implementation**

In `bus_engine.py`, add the constant next to `WALK_SPEED_M_PER_MIN` and `WALK_DETOUR_FACTOR`:

```python
WALK_SPEED_M_PER_MIN = 80   # project-wide walking pace, also used by nearby-stop cards
WALK_DETOUR_FACTOR = 1.3    # straight line -> street network, when OneMap is unavailable
DEADLINE_BUFFER_MIN = 5     # safety margin subtracted from a deadline-derived depart_by time
```

Add `from datetime import datetime, timedelta` to the existing `from datetime import ...` import line at the top of `bus_engine.py` (it currently imports `datetime, timezone` — extend to `datetime, timezone, timedelta`).

Add the method immediately after `plan_trip`:

```python
    def plan_trip_by_deadline(self, s_lat, s_lon, e_lat, e_lon, target_arrival_time, now=None):
        """Same as plan_trip, but works backward from a target arrival time
        instead of forward from "now". Scoped to direct-mode trips only —
        transfer trips use a different duration formula (see
        buildTransferTimeline in index.html) and are deliberately not
        covered here; see the design spec's Open Questions.

        target_arrival_time is always interpreted as later today. A kiosk is
        a walk-up, same-visit interaction — nobody asking it "when do I need
        to leave to be there by 3pm" means 3pm tomorrow. A time that has
        already passed today is correctly reported as urgent=True, not
        silently rolled forward a day.
        """
        plan = self.plan_trip(s_lat, s_lon, e_lat, e_lon)
        if plan.get('mode') != 'direct' or not plan.get('best'):
            return plan

        best = plan['best']
        total_minutes = max(4, best['stops'] * 2) + best['walk_to_dest_min']

        now = now or datetime.now()
        target_hour, target_minute = (int(p) for p in target_arrival_time.split(':'))
        target_dt = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)

        depart_dt = target_dt - timedelta(minutes=total_minutes + DEADLINE_BUFFER_MIN)
        urgent = depart_dt <= now

        return {**plan, 'depart_by': depart_dt.strftime('%H:%M'), 'urgent': urgent}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_deadline_trip.py -v`
Expected: PASS (8 tests). `DEMO_START`/`DEMO_END` (Pasir Ris Bus Interchange -> Tampines Mall) is confirmed to resolve to `type: 'bus', mode: 'direct'` against the live route data — verified with `engine.plan_trip(*DEMO_START, *DEMO_END)` before writing this plan.

- [ ] **Step 5: Commit**

```bash
git add bus_engine.py tests/test_deadline_trip.py
git commit -m "feat: deadline-aware trip planning (direct-mode trips)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 5: Three new FastAPI endpoints

**Files:**
- Modify: `main.py`
- Test: `tests/test_ai_endpoints.py`

**Interfaces:**
- Consumes: `ai_features.extract_voice_intent`, `ai_features.narrate_trip`, `ai_features.voice_intent_limiter`, `ai_features.narrate_trip_limiter`, `ai_features.daily_budget` (Tasks 1-3); `engine.plan_trip_by_deadline` (Task 4)
- Produces: `POST /api/v1/voice-intent`, `POST /api/v1/plan-by-deadline`, `POST /api/v1/narrate-trip`

This is the task that proves the spec's central claim: **every failure of these endpoints must look identical to the feature not existing.** Test that explicitly, not just the happy path.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ai_endpoints.py`:

```python
from unittest.mock import MagicMock

import ai_features
import main
from main import app
from fastapi.testclient import TestClient

client = TestClient(app)

# main.py calls ai_features.extract_voice_intent(...) / ai_features.narrate_trip(...)
# through the module reference (never `from ai_features import extract_voice_intent`)
# specifically so that patching ai_features.<name> here actually takes effect. A
# bare-name import would bind its own copy at import time and silently ignore
# these patches — the endpoint would call the real function instead of the fake
# one, and a happy-path test could pass for the wrong reason.


def test_voice_intent_endpoint_returns_extraction(monkeypatch):
    monkeypatch.setattr(
        ai_features, 'extract_voice_intent',
        lambda text, lang: {'destination_query': 'white sands', 'target_arrival_time': None, 'confidence': 'high'},
    )

    response = client.post('/api/v1/voice-intent', json={'text': 'take me to white sands', 'lang': 'en'})

    assert response.status_code == 200
    assert response.json() == {'destination_query': 'white sands', 'target_arrival_time': None, 'confidence': 'high'}


def test_voice_intent_endpoint_rejects_rate_limited_client(monkeypatch):
    monkeypatch.setattr(main.ai_features.voice_intent_limiter, 'allow', lambda client_id: False)

    response = client.post('/api/v1/voice-intent', json={'text': 'anything', 'lang': 'en'})

    assert response.status_code == 200, "a rate-limited call must still return a safe fallback, not an error"
    assert response.json() == {'destination_query': None, 'target_arrival_time': None, 'confidence': 'low'}


def test_voice_intent_endpoint_rejects_when_daily_budget_exhausted(monkeypatch):
    monkeypatch.setattr(main.ai_features.daily_budget, 'consume', lambda: False)

    response = client.post('/api/v1/voice-intent', json={'text': 'anything', 'lang': 'en'})

    assert response.status_code == 200
    assert response.json() == {'destination_query': None, 'target_arrival_time': None, 'confidence': 'low'}


def test_narrate_trip_endpoint_returns_narrative(monkeypatch):
    monkeypatch.setattr(ai_features, 'narrate_trip', lambda fields, lang: 'A short narration.')

    response = client.post('/api/v1/narrate-trip', json={
        'trip': {'service': '53', 'stops': 8, 'walk_to_dest_min': 2, 'from_name': 'A', 'to_name': 'B'},
        'lang': 'en',
    })

    assert response.status_code == 200
    assert response.json() == {'narrative': 'A short narration.'}


def test_narrate_trip_endpoint_returns_null_narrative_on_failure(monkeypatch):
    monkeypatch.setattr(ai_features, 'narrate_trip', lambda fields, lang: None)

    response = client.post('/api/v1/narrate-trip', json={
        'trip': {'service': '53', 'stops': 8, 'walk_to_dest_min': 2, 'from_name': 'A', 'to_name': 'B'},
        'lang': 'en',
    })

    assert response.status_code == 200
    assert response.json() == {'narrative': None}


def test_narrate_trip_endpoint_rate_limited(monkeypatch):
    monkeypatch.setattr(main.ai_features.narrate_trip_limiter, 'allow', lambda client_id: False)

    response = client.post('/api/v1/narrate-trip', json={
        'trip': {'service': '53', 'stops': 8, 'walk_to_dest_min': 2, 'from_name': 'A', 'to_name': 'B'},
        'lang': 'en',
    })

    assert response.status_code == 200
    assert response.json() == {'narrative': None}


def test_plan_by_deadline_endpoint_returns_the_engine_result():
    response = client.post('/api/v1/plan-by-deadline', json={
        's_lat': 1.373696, 's_lon': 103.94845,
        'e_lat': 1.3575, 'e_lon': 103.9885,
        'target_arrival_time': '23:59',
    })

    assert response.status_code == 200
    body = response.json()
    assert 'depart_by' in body or body.get('type') != 'bus'  # direct trips get depart_by; others pass through


def test_plan_by_deadline_endpoint_rejects_malformed_time():
    response = client.post('/api/v1/plan-by-deadline', json={
        's_lat': 1.373696, 's_lon': 103.94845,
        'e_lat': 1.3575, 'e_lon': 103.9885,
        'target_arrival_time': 'not-a-time',
    })

    assert response.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ai_endpoints.py -v`
Expected: FAIL — the three routes don't exist yet, so every request 404s

- [ ] **Step 3: Write the implementation**

In `main.py`, add to the imports at the top:

```python
import re

import ai_features
```

Call `ai_features.extract_voice_intent(...)` / `ai_features.narrate_trip(...)` through the module reference everywhere below — never `from ai_features import extract_voice_intent, narrate_trip`. That form binds its own copy of the name into `main`'s namespace at import time, so a test patching `ai_features.extract_voice_intent` later would silently miss `main`'s already-bound copy (see the note at the top of `tests/test_ai_endpoints.py`, Task 5 Step 2).

Add two new Pydantic models next to `TripRequest`:

```python
class VoiceIntentRequest(BaseModel):
    text: str
    lang: str = 'en'


class NarrateTripRequest(BaseModel):
    trip: dict
    lang: str = 'en'


class DeadlineTripRequest(BaseModel):
    s_lat: float
    s_lon: float
    e_lat: float
    e_lon: float
    target_arrival_time: str

    @field_validator('target_arrival_time')
    @classmethod
    def validate_time_format(cls, v):
        if not re.match(r'^([01]\d|2[0-3]):([0-5]\d)$', v):
            raise ValueError('target_arrival_time must be HH:MM (24-hour)')
        return v
```

This project runs Pydantic v2 (confirmed: `python -c "import pydantic; print(pydantic.VERSION)"` → `2.12.5`), so `field_validator` is correct — `main.py`'s existing `from pydantic import BaseModel` line needs `field_validator` added to it: `from pydantic import BaseModel, field_validator`.

Add the three endpoints after the existing `POST /api/v1/plan`:

```python
@app.post("/api/v1/voice-intent")
async def voice_intent(request: VoiceIntentRequest, req: Request):
    client_id = req.client.host if req.client else 'unknown'
    if not ai_features.voice_intent_limiter.allow(client_id) or not ai_features.daily_budget.consume():
        return {"destination_query": None, "target_arrival_time": None, "confidence": "low"}
    return ai_features.extract_voice_intent(request.text, request.lang)


@app.post("/api/v1/plan-by-deadline")
async def plan_by_deadline(request: DeadlineTripRequest):
    return engine.plan_trip_by_deadline(
        request.s_lat, request.s_lon, request.e_lat, request.e_lon, request.target_arrival_time,
    )


@app.post("/api/v1/narrate-trip")
async def narrate_trip_endpoint(request: NarrateTripRequest, req: Request):
    client_id = req.client.host if req.client else 'unknown'
    if not ai_features.narrate_trip_limiter.allow(client_id) or not ai_features.daily_budget.consume():
        return {"narrative": None}
    return {"narrative": ai_features.narrate_trip(request.trip, request.lang)}
```

Add `Request` to the existing `from fastapi import FastAPI, HTTPException, Query` import line (extend to `from fastapi import FastAPI, HTTPException, Query, Request`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_ai_endpoints.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Run the full backend suite to check for regressions**

Run: `python -m pytest -q`
Expected: PASS, all tests including every pre-existing one (should be 150+ passed at this point given the session's prior counts)

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_ai_endpoints.py
git commit -m "feat: wire voice-intent, plan-by-deadline, narrate-trip endpoints

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 6: `assistant-status.js` — depart-by / urgent status

**Files:**
- Modify: `static/js/assistant-status.js`
- Modify: `static/js/assistant-status.test.js`

**Interfaces:**
- Consumes: nothing new
- Produces: `planStatus(data)` now also handles `data.depart_by` / `data.urgent` on direct-mode results, returning `{key: 'statusUrgent', args: []}` or `{key: 'statusDepartBy', args: [data.depart_by]}` instead of `bestOption` when present.

- [ ] **Step 1: Write the failing tests**

Add to `static/js/assistant-status.test.js`, in the first test block (near the other `planStatus` tests):

```js
test('a direct plan with a comfortable deadline reports the depart-by time', () => {
  const status = planStatus({
    type: 'bus', mode: 'direct',
    best: { service: '53', stops: 8 },
    depart_by: '13:40', urgent: false,
  });

  assert.equal(status.key, 'statusDepartBy');
  assert.deepEqual(status.args, ['13:40']);
});

test('a direct plan with an already-passed deadline reports urgency, not the time', () => {
  const status = planStatus({
    type: 'bus', mode: 'direct',
    best: { service: '53', stops: 8 },
    depart_by: '09:00', urgent: true,
  });

  assert.equal(status.key, 'statusUrgent');
});

test('a direct plan with no deadline still reports the best option as before', () => {
  const status = planStatus({ type: 'bus', mode: 'direct', best: { service: '53', stops: 8 } });

  assert.equal(status.key, 'bestOption');
});
```

Add `'statusDepartBy'` and `'statusUrgent'` to the existing `REQUIRED_KEYS` array near the bottom of the same file:

```js
const REQUIRED_KEYS = [
  'planning', 'ready', 'noRoute', 'bestOption', 'routeFailed', 'planFailed',
  'foundNearby', 'statusWalkSuggested', 'destinationResolved', 'nearbyFailed',
  'searchingFor', 'destinationNotFound', 'destinationUnresolvable',
  'statusDepartBy', 'statusUrgent',
];
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `node --test static/js/assistant-status.test.js`
Expected: FAIL — the new `planStatus` assertions fail (still returns `bestOption`), and the `REQUIRED_KEYS` loop fails because the two new keys don't exist in `i18n.js` yet

- [ ] **Step 3: Write the implementation**

In `static/js/assistant-status.js`, replace the direct-mode branch of `planStatus`:

```js
    const best = data.best || (data.options || [])[0];
    if (best && best.service) {
      if (data.depart_by) {
        return data.urgent
          ? { key: 'statusUrgent', args: [] }
          : { key: 'statusDepartBy', args: [data.depart_by] };
      }
      return { key: 'bestOption', args: [best.service] };
    }
    return { key: 'noRoute', args: [] };
```

(This replaces the existing block that only had the final two lines — same file, same function, just the added `if (data.depart_by)` branch before the existing `return { key: 'bestOption', ... }`.)

- [ ] **Step 4: Run tests to verify they pass (i18n keys come in Task 7 — expect one remaining failure)**

Run: `node --test static/js/assistant-status.test.js`
Expected: The three new `planStatus` tests PASS. `every status key is translated in both languages` (the `REQUIRED_KEYS` loop) still FAILS until Task 7 adds the keys — that's expected at this point; don't treat it as a regression here.

- [ ] **Step 5: Commit**

```bash
git add static/js/assistant-status.js static/js/assistant-status.test.js
git commit -m "feat: assistant status reports depart-by / urgent for deadline trips

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 7: i18n keys for depart-by / urgent

**Files:**
- Modify: `static/js/i18n.js`

**Interfaces:**
- Consumes: nothing
- Produces: `statusDepartBy` and `statusUrgent` keys in both `zh` and `en` dictionaries

- [ ] **Step 1: Confirm the failing test from Task 6**

Run: `node --test static/js/assistant-status.test.js`
Expected: FAIL on `every status key is translated in both languages` (this is the test we're about to fix — no new test needed here, Task 6 already added the coverage)

- [ ] **Step 2: Add the keys**

In `static/js/i18n.js`, `zh` dictionary, add near `statusWalkSuggested`:

```js
      statusDepartBy: (time) => `建议 ${time} 前出发`,
      statusUrgent: '现在出发才来得及',
```

In the `en` dictionary, add near `statusWalkSuggested`:

```js
      statusDepartBy: (time) => `Leave by ${time}`,
      statusUrgent: 'Leave now to make it',
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `node --test static/js/assistant-status.test.js`
Expected: PASS (all tests, including `every status key is translated in both languages` and `the two languages actually differ for status text` — note `statusUrgent` isn't in that second list, that's fine, it wasn't asked for)

Run: `node --test static/js/i18n.test.js`
Expected: PASS (unchanged, new keys don't break anything here)

- [ ] **Step 4: Commit**

```bash
git add static/js/i18n.js
git commit -m "feat: i18n strings for deadline-trip status

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 8: Frontend AI client module (`ai-features.js`)

**Files:**
- Create: `static/js/ai-features.js`
- Create: `static/js/ai-features.test.js`

**Interfaces:**
- Consumes: global `fetch`, `AbortController` (both available in the browser and in Node 18+, confirmed by this repo's CI running Node 24)
- Produces: `fetchVoiceIntent({ text, lang, apiBase, timeoutMs, fetchImpl }) -> Promise<{destination_query, target_arrival_time, confidence} | null>`; `fetchTripNarration({ trip, lang, apiBase, timeoutMs, fetchImpl }) -> Promise<string | null>`. Both resolve to `null` (never reject) on any error, non-200, or timeout.

- [ ] **Step 1: Write the failing tests**

Create `static/js/ai-features.test.js`:

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const { fetchVoiceIntent, fetchTripNarration } = require('./ai-features.js');

function fakeFetchResolving(body, ok = true) {
  return async () => ({ ok, json: async () => body });
}

function fakeFetchNeverResolving() {
  return () => new Promise(() => {}); // never settles — exercises the timeout path
}

function fakeFetchRejecting() {
  return async () => { throw new Error('network down'); };
}

// ─── fetchVoiceIntent ───────────────────────────────────────────────────────

test('fetchVoiceIntent returns the parsed intent on success', async () => {
  const result = await fetchVoiceIntent({
    text: 'take me to white sands', lang: 'en',
    fetchImpl: fakeFetchResolving({ destination_query: 'white sands', target_arrival_time: null, confidence: 'high' }),
  });

  assert.deepEqual(result, { destination_query: 'white sands', target_arrival_time: null, confidence: 'high' });
});

test('fetchVoiceIntent sends the text and lang in the request body', async () => {
  let sentBody = null;
  const fetchImpl = async (url, options) => {
    sentBody = JSON.parse(options.body);
    return { ok: true, json: async () => ({ destination_query: null, target_arrival_time: null, confidence: 'low' }) };
  };

  await fetchVoiceIntent({ text: 'hello there', lang: 'zh', fetchImpl });

  assert.equal(sentBody.text, 'hello there');
  assert.equal(sentBody.lang, 'zh');
});

test('fetchVoiceIntent returns null on a non-ok response', async () => {
  const result = await fetchVoiceIntent({ text: 'x', lang: 'en', fetchImpl: fakeFetchResolving({}, false) });
  assert.equal(result, null);
});

test('fetchVoiceIntent returns null when fetch rejects', async () => {
  const result = await fetchVoiceIntent({ text: 'x', lang: 'en', fetchImpl: fakeFetchRejecting() });
  assert.equal(result, null);
});

test('fetchVoiceIntent returns null after the timeout elapses', async () => {
  const start = Date.now();
  const result = await fetchVoiceIntent({
    text: 'x', lang: 'en', timeoutMs: 30, fetchImpl: fakeFetchNeverResolving(),
  });
  const elapsed = Date.now() - start;

  assert.equal(result, null);
  assert.ok(elapsed < 500, `should resolve promptly after the 30ms timeout, took ${elapsed}ms`);
});

// ─── fetchTripNarration ─────────────────────────────────────────────────────

test('fetchTripNarration returns the narrative string on success', async () => {
  const result = await fetchTripNarration({
    trip: { service: '53', stops: 8 }, lang: 'en',
    fetchImpl: fakeFetchResolving({ narrative: 'Walk to Berth B1.' }),
  });

  assert.equal(result, 'Walk to Berth B1.');
});

test('fetchTripNarration returns null when the narrative field is null', async () => {
  const result = await fetchTripNarration({
    trip: { service: '53' }, lang: 'en', fetchImpl: fakeFetchResolving({ narrative: null }),
  });

  assert.equal(result, null);
});

test('fetchTripNarration returns null on a non-ok response', async () => {
  const result = await fetchTripNarration({ trip: {}, lang: 'en', fetchImpl: fakeFetchResolving({}, false) });
  assert.equal(result, null);
});

test('fetchTripNarration returns null when fetch rejects', async () => {
  const result = await fetchTripNarration({ trip: {}, lang: 'en', fetchImpl: fakeFetchRejecting() });
  assert.equal(result, null);
});

test('fetchTripNarration returns null after the timeout elapses', async () => {
  const start = Date.now();
  const result = await fetchTripNarration({
    trip: {}, lang: 'en', timeoutMs: 30, fetchImpl: fakeFetchNeverResolving(),
  });
  const elapsed = Date.now() - start;

  assert.equal(result, null);
  assert.ok(elapsed < 500, `should resolve promptly after the 30ms timeout, took ${elapsed}ms`);
});

test('fetchTripNarration sends the trip and lang in the request body', async () => {
  let sentBody = null;
  const fetchImpl = async (url, options) => {
    sentBody = JSON.parse(options.body);
    return { ok: true, json: async () => ({ narrative: null }) };
  };

  await fetchTripNarration({ trip: { service: '53' }, lang: 'zh', fetchImpl });

  assert.deepEqual(sentBody.trip, { service: '53' });
  assert.equal(sentBody.lang, 'zh');
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `node --test static/js/ai-features.test.js`
Expected: FAIL with `Cannot find module './ai-features.js'`

- [ ] **Step 3: Write the implementation**

Create `static/js/ai-features.js`:

```js
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.KioskAIFeatures = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  // Both functions here follow the same rule as their backend counterparts in
  // ai_features.py: any failure — timeout, network error, non-200, malformed
  // body — resolves to null, never rejects. The caller's own fallback (today's
  // exact behavior, pre-dating these features) always runs when this happens.

  async function withTimeout(fetchImpl, url, options, timeoutMs) {
    const controller = new AbortController();
    let timer;
    // Races the fetch against a plain timer that resolves to null. This race
    // is what actually bounds wall-clock time — aborting the signal is a
    // courtesy that lets a real fetch() free its connection early, but nothing
    // requires fetchImpl to honor it. A fetchImpl that ignores the signal
    // (any fake that doesn't wire it up, or a misbehaving real one) would hang
    // this forever without the race — confirmed by hand: an earlier version of
    // this function that only used `signal` (no race) hung indefinitely
    // against a fake fetch that never resolves.
    const timeoutPromise = new Promise((resolve) => {
      timer = setTimeout(() => {
        controller.abort();
        resolve(null);
      }, timeoutMs);
    });

    const fetchAndParse = (async () => {
      try {
        const res = await fetchImpl(url, { ...options, signal: controller.signal });
        if (!res.ok) return null;
        return await res.json();
      } catch (err) {
        return null;
      }
    })();

    const result = await Promise.race([fetchAndParse, timeoutPromise]);
    clearTimeout(timer);
    return result;
  }

  async function fetchVoiceIntent({ text, lang, apiBase = '', timeoutMs = 1200, fetchImpl = fetch }) {
    const data = await withTimeout(fetchImpl, `${apiBase}/api/v1/voice-intent`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, lang }),
    }, timeoutMs);

    if (!data || typeof data !== 'object') return null;
    return {
      destination_query: typeof data.destination_query === 'string' ? data.destination_query : null,
      target_arrival_time: typeof data.target_arrival_time === 'string' ? data.target_arrival_time : null,
      confidence: data.confidence === 'high' ? 'high' : 'low',
    };
  }

  async function fetchTripNarration({ trip, lang, apiBase = '', timeoutMs = 1500, fetchImpl = fetch }) {
    const data = await withTimeout(fetchImpl, `${apiBase}/api/v1/narrate-trip`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ trip, lang }),
    }, timeoutMs);

    if (!data || typeof data.narrative !== 'string' || !data.narrative.trim()) return null;
    return data.narrative;
  }

  return { fetchVoiceIntent, fetchTripNarration };
});
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `node --test static/js/ai-features.test.js`
Expected: PASS (11 tests)

- [ ] **Step 5: Commit**

```bash
git add static/js/ai-features.js static/js/ai-features.test.js
git commit -m "feat: frontend client for voice-intent and narrate-trip, timeout-safe

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 9: Wire it all into `index.html`

**Files:**
- Modify: `index.html`
- Modify: `tests/test_static_assets.py`

**Interfaces:**
- Consumes: `KioskAIFeatures.fetchVoiceIntent`, `KioskAIFeatures.fetchTripNarration` (Task 8); `resolveLocationFromText`, `planJourney`, `renderTripSummary`, `speak`, `buildDirectTimeline` (existing, unmodified signatures except `planJourney` gains one optional parameter)
- Produces: the end-to-end feature, wired into the existing voice and trip-planning flow

This task has no `node --test` coverage of its own (the codebase's established pattern: logic that must live inline in `index.html`'s single script block is covered by presence/ordering assertions in `test_static_assets.py`, exactly like the existing `test_planning_status_is_cleared_after_a_plan_renders` and `test_index_wires_the_digital_human_to_speech_events` tests already do).

- [ ] **Step 1: Register the new script**

In `index.html`, find:
```html
  <script src="/static/js/digital-human.js"></script>
```
Add immediately after it:
```html
  <script src="/static/js/ai-features.js"></script>
```

- [ ] **Step 2: Write the failing tests**

Add to `tests/test_static_assets.py`:

```python
def test_serves_ai_features_module():
    response = client.get("/static/js/ai-features.js")
    assert response.status_code == 200
    assert "fetchVoiceIntent" in response.text
    assert "fetchTripNarration" in response.text


def test_index_wires_ai_features_module():
    body = client.get("/").text
    assert '<script src="/static/js/ai-features.js"></script>' in body
    assert "KioskAIFeatures.fetchVoiceIntent" in body
    assert "KioskAIFeatures.fetchTripNarration" in body


def test_voice_intent_extraction_runs_before_falling_back_to_the_raw_transcript():
    """Regression guard: the raw-transcript resolveLocationFromText(text) call
    must still exist as the fallback — voice-intent extraction sits in front
    of it, never replaces it."""
    body = client.get("/").text
    assert "await resolveLocationFromText(text)" in body
    assert "KioskAIFeatures.fetchVoiceIntent(" in body


def test_plan_journey_accepts_an_optional_deadline_and_defaults_to_the_plain_endpoint():
    body = client.get("/").text
    assert "async function planJourney(targetArrivalTime = null)" in body
    assert "/api/v1/plan-by-deadline" in body
    # the original, unconditional endpoint call must still be reachable when no deadline is given
    assert "'/api/v1/plan'" in body or '"/api/v1/plan"' in body or "`${apiBase}/api/v1/plan`" in body


def test_narration_falls_back_to_the_existing_welcome_speak_line():
    body = client.get("/").text
    assert "KioskAIFeatures.fetchTripNarration(" in body
    assert "t('welcomeSpeak', best.service, etaText)" in body
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_static_assets.py -k "ai_features or voice_intent or plan_journey or narration" -v`
Expected: FAIL — none of the new wiring exists yet in `index.html`

- [ ] **Step 4: Modify `onresult` to try voice-intent extraction first**

In `index.html`, find the existing:
```js
      recognitionInstance.onresult = async (event) => {
        const text = event.results[0][0].transcript;
        setAssistantStatus('heard', text);
        showToast(text);
        const destination = await resolveLocationFromText(text);
        if (destination) {
          const updated = await setDestinationLocation(destination, text);
          if (updated) {
            await planJourney();
          }
          return;
        }

        await searchStops(text);
      };
```

Replace it with:

```js
      recognitionInstance.onresult = async (event) => {
        const text = event.results[0][0].transcript;
        setAssistantStatus('heard', text);
        showToast(text);

        // Try to extract a destination + optional deadline with Claude first.
        // Any failure (network, timeout, low confidence) resolves to null,
        // and the very next line is the exact call this replaces — the
        // fallback is not a rewrite, it's literally not using this result.
        const intent = await KioskAIFeatures.fetchVoiceIntent({ text, lang: stateLang.ui });
        const useExtracted = intent && intent.destination_query && intent.confidence === 'high';

        const destination = useExtracted
          ? await resolveLocationFromText(intent.destination_query)
          : await resolveLocationFromText(text);

        if (destination) {
          const updated = await setDestinationLocation(destination, text);
          if (updated) {
            await planJourney(useExtracted ? intent.target_arrival_time : null);
          }
          return;
        }

        await searchStops(text);
      };
```

- [ ] **Step 5: Modify `planJourney` to branch on a deadline**

Find the existing:
```js
    async function planJourney() {
      try {
        setAssistantStatus('planning');
        const res = await fetch(`${apiBase}/api/v1/plan`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            s_lat: state.current.lat,
            s_lon: state.current.lon,
            e_lat: state.destination.lat,
            e_lon: state.destination.lon,
          })
        });
        const data = await res.json();
        renderTripSummary(data, { announce: currentView === 'wayfinding' });
        // planJourney announced "planning"; it is responsible for taking it
        // down. renderTripSummary returns through four branches and none of
        // them touch the status.
        const done = KioskAssistantStatus.planStatus(data);
        setAssistantStatus(done.key, ...done.args);
      } catch (err) {
        console.error(err);
        setAssistantStatus('routeFailed');
        if (currentView === 'wayfinding') showToast(t('planFailed'));
      }
    }
```

Replace it with:

```js
    async function planJourney(targetArrivalTime = null) {
      try {
        setAssistantStatus('planning');
        const body = {
          s_lat: state.current.lat,
          s_lon: state.current.lon,
          e_lat: state.destination.lat,
          e_lon: state.destination.lon,
        };
        const endpoint = targetArrivalTime
          ? `${apiBase}/api/v1/plan-by-deadline`
          : `${apiBase}/api/v1/plan`;
        if (targetArrivalTime) body.target_arrival_time = targetArrivalTime;

        const res = await fetch(endpoint, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(body)
        });
        const data = await res.json();
        renderTripSummary(data, { announce: currentView === 'wayfinding' });
        // planJourney announced "planning"; it is responsible for taking it
        // down. renderTripSummary returns through four branches and none of
        // them touch the status.
        const done = KioskAssistantStatus.planStatus(data);
        setAssistantStatus(done.key, ...done.args);
      } catch (err) {
        console.error(err);
        setAssistantStatus('routeFailed');
        if (currentView === 'wayfinding') showToast(t('planFailed'));
      }
    }
```

Every other existing call site (`focusStop`'s `await planJourney();`, any postcode-search call) passes no argument, so `targetArrivalTime` defaults to `null` and `endpoint` resolves to the original `/api/v1/plan` — byte-for-byte the same request as before.

- [ ] **Step 6: Add the depart-by / urgent line to `buildDirectTimeline`**

Find the existing:
```js
    function buildDirectTimeline(best, isZh) {
      const now = new Date();
      const waitMins  = best?.live?.minutes ?? 5;
      const totalMins = KioskTripDuration.computeDirectTripMinutes(best);
      const travelMins = Math.max(4, (best?.stops ?? 5) * 2);
      const walkMins  = totalMins - travelMins;
      const departT   = new Date(now.getTime() + waitMins  * 60000);
      const alightT   = new Date(departT.getTime()  + travelMins * 60000);
      const arriveT   = new Date(alightT.getTime()  + walkMins   * 60000);
      const stopsLabel = isZh
        ? `${best.stops} 站 · ${travelMins} 分钟`
        : `${best.stops} stops · ${travelMins} min`;
      const walkLabel = isZh
        ? `步行约 ${walkMins} 分钟`
        : `Walk ~${walkMins} min`;
      return `
        <div class="tl-header">
          <div>
            <div class="tl-timerange">${fmtTime(departT)} – ${fmtTime(arriveT)}</div>
            <span class="tl-duration">${totalMins} min</span>
          </div>
```

Replace the function signature and header block with:

```js
    function buildDirectTimeline(best, isZh, departInfo = null) {
      const now = new Date();
      const waitMins  = best?.live?.minutes ?? 5;
      const totalMins = KioskTripDuration.computeDirectTripMinutes(best);
      const travelMins = Math.max(4, (best?.stops ?? 5) * 2);
      const walkMins  = totalMins - travelMins;
      const departT   = new Date(now.getTime() + waitMins  * 60000);
      const alightT   = new Date(departT.getTime()  + travelMins * 60000);
      const arriveT   = new Date(alightT.getTime()  + walkMins   * 60000);
      const stopsLabel = isZh
        ? `${best.stops} 站 · ${travelMins} 分钟`
        : `${best.stops} stops · ${travelMins} min`;
      const walkLabel = isZh
        ? `步行约 ${walkMins} 分钟`
        : `Walk ~${walkMins} min`;
      const departByLine = departInfo
        ? `<div class="small-label" style="margin-top:6px">${
            departInfo.urgent ? t('statusUrgent') : t('statusDepartBy', departInfo.departBy)
          }</div>`
        : '';
      return `
        <div class="tl-header">
          <div>
            <div class="tl-timerange">${fmtTime(departT)} – ${fmtTime(arriveT)}</div>
            <span class="tl-duration">${totalMins} min</span>
            ${departByLine}
          </div>
```

- [ ] **Step 7: Call narration and pass `departInfo` from `renderTripSummary`**

Find the existing direct-mode tail of `renderTripSummary`:
```js
        // Direct mode
        const best = data.best || data.options?.[0];
        summary.innerHTML = buildDirectTimeline(best, isZh);
```

Replace with:

```js
        // Direct mode
        const best = data.best || data.options?.[0];
        const departInfo = data.depart_by ? { departBy: data.depart_by, urgent: !!data.urgent } : null;
        summary.innerHTML = buildDirectTimeline(best, isZh, departInfo);
```

Then find:
```js
        renderRouteCards(data.options || []);
        if (best) {
          if (shouldAnnounce()) {
            const etaText = KioskTripDuration.computeDirectTripMinutes(best);
            speak(t('welcomeSpeak', best.service, etaText));
            showToast(t('bestOption', best.service));
          }
        } else if (shouldAnnounce()) {
          showToast(t('noRoute'));
        }
    }
```

Replace the `if (best) { if (shouldAnnounce()) { ... } }` block with:

```js
        renderRouteCards(data.options || []);
        if (best) {
          if (shouldAnnounce()) {
            const etaText = KioskTripDuration.computeDirectTripMinutes(best);
            const fallbackLine = t('welcomeSpeak', best.service, etaText);
            const narrationFields = {
              service: best.service, stops: best.stops, berth: best.berth,
              walk_to_dest_min: best.walk_to_dest_min, from_name: best.from_name, to_name: best.to_name,
              ...(departInfo ? { depart_by: departInfo.departBy, urgent: departInfo.urgent } : {}),
            };
            KioskAIFeatures.fetchTripNarration({ trip: narrationFields, lang: stateLang.ui })
              .then((narrative) => speak(narrative || fallbackLine));
            showToast(t('bestOption', best.service));
          }
        } else if (shouldAnnounce()) {
          showToast(t('noRoute'));
        }
    }
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `python -m pytest tests/test_static_assets.py -v`
Expected: PASS (all tests, old and new)

- [ ] **Step 9: Run the complete test suite**

Run: `python -m pytest -q`
Run: `for f in static/js/*.test.js; do node --test "$f"; done`
Expected: every test, backend and frontend, passes with zero failures

- [ ] **Step 10: Manual smoke test**

Start the server (`python -m uvicorn main:app --port 8098`) and confirm with curl that a request without `ANTHROPIC_API_KEY` set behaves exactly as today:

```bash
curl -s -X POST http://127.0.0.1:8098/api/v1/voice-intent -H "Content-Type: application/json" -d '{"text":"take me to changi airport","lang":"en"}'
```
Expected: `{"destination_query":null,"target_arrival_time":null,"confidence":"low"}` — proves the no-key fallback works before any real key is ever configured.

```bash
curl -s -X POST http://127.0.0.1:8098/api/v1/plan -H "Content-Type: application/json" -d '{"s_lat":1.373696,"s_lon":103.94845,"e_lat":1.3575,"e_lon":103.9885}'
```
Expected: identical to the pre-existing behavior of this untouched endpoint — confirms nothing in this task regressed the trip planner itself.

- [ ] **Step 11: Commit**

```bash
git add index.html tests/test_static_assets.py
git commit -m "feat: wire voice-intent, deadline planning, and narration into the kiosk UI

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 10: Configuration & documentation

**Files:**
- Modify: `README.md`

**Interfaces:** none — documentation only.

- [ ] **Step 1: Document the new environment variables**

In `README.md`, in the `## 环境变量` section, extend the example block:

```bash
set LTA_API_KEY=你的LTA_API_KEY
set DATAGOVSG=你的DATA_GOV_SG_API_KEY
set LTA_REFRESH_INTERVAL=900
set ONEMAP_EMAIL=你的OneMap账号邮箱
set ONEMAP_PASSWORD=你的OneMap账号密码
set ANTHROPIC_API_KEY=你的Anthropic_API_Key
```

And add to the bullet list immediately after the `ONEMAP_EMAIL` / `ONEMAP_PASSWORD` entry:

```markdown
- `ANTHROPIC_API_KEY`：用于两个 AI 功能（语音意图抽取、行程语音简述）。未配置时两个功能自动禁用，
  kiosk 行为与今天完全一致——这两个功能只做"锦上添花"，绝不阻断已有流程。
- `AI_RATE_LIMIT_MAX_CALLS` / `AI_RATE_LIMIT_WINDOW_SECONDS`：单个来源每个时间窗口允许调用 AI 接口的
  次数，默认 20 次 / 60 秒。
- `AI_DAILY_CALL_BUDGET`：AI 接口每天（UTC）总调用次数上限，默认 2000，超出后当天自动禁用（回退为
  今天的行为），避免公开无人值守 kiosk 被刷调用产生意外账单。
```

- [ ] **Step 2: Run the complete test suite one final time**

```bash
python -m pytest -q
for f in static/js/*.test.js; do node --test "$f"; done
```

Expected: 100% pass, zero regressions from the pre-existing suite.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document ANTHROPIC_API_KEY and AI rate-limit/budget env vars

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Deployment note (not a task — read before merging)

This repo's convention (established throughout this project's history) is: branch → PR → merge → the Azure Web App workflow auto-deploys on push to `main`. Each task above commits to whatever branch the executor is on; open one PR for the whole plan (or one per task, if the reviewer prefers smaller diffs) before merging to `main`. **Do not set a real `ANTHROPIC_API_KEY` in the Azure App Settings until Task 10 is merged and deployed** — the two AI endpoints must have shipped their fallback logic first, given this is a public, unauthenticated production URL.
