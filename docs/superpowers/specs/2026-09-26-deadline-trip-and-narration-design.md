# Deadline-Aware Trip Planning + AI Trip Narration — Design

Status: draft, pending user review
Date: 2026-09-26

## Problem

Two real, distinct commuter gaps, chosen out of a broader "AI features by commuter
persona" brainstorm as the pair that (a) need no new hardware, (b) share the same
underlying mechanic, and (c) are pure software additions on top of data the kiosk
already computes:

1. **Trip planning is departure-first, never deadline-first.** A commuter with an
   appointment ("I need to be at Changi General by 3pm") has no way to ask "when do
   I need to leave" — they can only ask "what's the next bus right now." This
   matters most for older commuters, who described exactly this need in the
   persona brainstorm (fear of missing a connection, need for buffer time).
2. **The kiosk never previews the trip in plain language before or in addition to
   the raw itinerary.** A short spoken walkthrough — "walk to Berth B3, board the
   red 53, about 8 stops" — is a known anxiety-reduction technique (a "social
   story," used in autism support) and helps first-time riders, elderly commuters,
   and anyone who processes speech better than reading a card.

Both are single, stateless, one-shot Claude calls — no agent loop, no tool-use, no
conversation memory. This explicitly is *not* the larger "reasoning concierge"
idea discussed earlier (multi-turn negotiation over weather/crowding/accessibility)
— that remains a separate, bigger future project. These two endpoints are
designed so they *could* become tool targets for that project later, but nothing
here depends on it.

## Goals

- Extract a destination and an optional target arrival time from a freely-spoken
  voice query.
- When a target arrival time is present, compute a suggested departure time by
  working backward from the existing, unmodified trip-time estimate.
- After any successful trip plan, speak (and caption) a short natural-language
  narration of the itinerary, in the kiosk's current UI language.
- Every failure mode of both new features must degrade to **exactly today's
  behavior** — no error surfaced to the commuter, no broken flow.
- No PII/transcript retention beyond what's needed to log success/failure.
- No unbounded API spend on a public, unauthenticated kiosk URL.

## Non-goals

- Multi-turn conversation, negotiation, or tool-use reasoning (the "reasoning
  concierge" idea) — future work, not this spec.
- Sign-language generation, dialect speech, camera/vision features — separate
  ideas from the same brainstorm, not in scope here.
- Persona detection or an explicit "detailed mode" toggle — the earlier
  clarifying question settled this: narration is unconditional, for every trip.
- Changing `resolve_place`, `plan_trip`, or any existing engine method's
  behavior or signature. Both features are additive wrappers.

## Architecture

Three new, independent, stateless backend endpoints — two LLM-backed, one pure
arithmetic. None replaces an existing code path — each sits in front of or after
one, with a hard fallback if it fails.

```
POST /api/v1/voice-intent      (LLM)  raw transcript -> destination + optional deadline
POST /api/v1/plan-by-deadline  (math) trip request + target time -> plan + depart_by
POST /api/v1/narrate-trip      (LLM)  computed trip -> short spoken narrative
```

Rejected alternatives (recorded for future reference, not re-litigated):

- **One combined "voice turn" endpoint** doing extraction + narration
  server-side in a single round trip. Rejected: couples two independently
  useful things, harder to test and fail gracefully at a granular level.
- **One Claude call with trip-planning tools** that reasons and narrates in one
  shot. Rejected: this is the bigger reasoning-concierge project smuggled in
  under a smaller feature's name. Keep them separate.

## Data flow

### Voice intent extraction

1. `recognitionInstance.onresult` fires with `text` (existing, unchanged —
   `index.html`).
2. New: `POST /api/v1/voice-intent` with `{ text, lang }`.
   - Backend calls Claude (Haiku 4.5) with `output_config.format` structured
     output. Schema: `{ destination_query: string | null, target_arrival_time:
     string | null, confidence: "high" | "low" }`. `target_arrival_time` is a
     24-hour `HH:MM` string or `null`.
   - System prompt instructs the model to extract only what was actually said —
     never infer or invent a time that wasn't mentioned in the transcript.
   - Server-side timeout on the Claude call; client-side `AbortController`
     timeout (~1.2s) as a second, independent guard.
3. Client behavior on the response:
   - `destination_query` present, `confidence` not `"low"` → call the existing,
     unmodified `resolveLocationFromText(destination_query)`.
   - Endpoint errors, times out, returns nothing usable, or `confidence` is
     `"low"` → call the existing, unmodified `resolveLocationFromText(text)` on
     the raw transcript. This is **exactly today's code path** — the fallback is
     not a new implementation, it is literally not calling the new endpoint's
     result.
4. `target_arrival_time` present and destination resolved → deadline trip (next
   section). Otherwise → today's immediate-departure `planJourney()`, untouched.

### Deadline trip math (no LLM — deterministic arithmetic)

**Scoped to `mode: 'direct'` trips only for this spec.** Transfer-mode trips use
a materially different duration formula (`travel1 + travel2 + walkMins` vs.
direct's `max(4, stops*2) + walk_to_dest_min` — see
`static/js/trip-duration.js` and `buildTransferTimeline` in `index.html`).
Doubling the duration logic for a first version isn't worth it; see Open
Questions. When `plan_trip` returns `mode: 'transfer'`, `type: 'walk'`, or
`type: 'none'`, `plan_trip_by_deadline` returns the plan unchanged with no
`depart_by` — the client then falls back to today's immediate-departure
display for that trip, exactly as if no deadline had been given.

New `bus_engine.py` method, wrapping the existing `plan_trip` without modifying
it, mirroring the exact formula `KioskTripDuration.computeDirectTripMinutes`
already uses client-side (`max(4, stops*2) + walk_to_dest_min`) so the two
never drift apart:

```python
def plan_trip_by_deadline(self, s_lat, s_lon, e_lat, e_lon, target_arrival_time):
    plan = self.plan_trip(s_lat, s_lon, e_lat, e_lon)  # existing, unmodified
    best = plan.get('best')
    if plan.get('mode') != 'direct' or not best:
        return plan  # transfer / walk / none — no deadline math, see above
    total_minutes = max(4, best['stops'] * 2) + best['walk_to_dest_min']
    depart_by = target_arrival_time - total_minutes - DEADLINE_BUFFER_MIN
    urgent = depart_by <= now()
    return {**plan, "depart_by": depart_by, "urgent": urgent}
```

`DEADLINE_BUFFER_MIN` defaults to 5 minutes, defined as a module constant next
to `WALK_SPEED_M_PER_MIN` and the other tunables in `bus_engine.py`.

New endpoint `POST /api/v1/plan-by-deadline` takes the same body as the
existing `TripRequest` model (`s_lat, s_lon, e_lat, e_lon`) plus
`target_arrival_time: str` (24-hour `HH:MM`). On the client, `planJourney()`
calls this endpoint instead of the existing `/api/v1/plan` whenever voice-intent
extraction returned a `target_arrival_time` — this is the one branching change
to `planJourney()` itself; everything else about it is unchanged.

### Narration

1. After `renderTripSummary()` succeeds with a `best` option (existing code
   path).
2. New: `POST /api/v1/narrate-trip` with the trip's already-computed fields —
   `service`, `stops`, `berth`, `walk_to_dest_min`, `from_name`, `to_name`, and
   `depart_by`/`urgent` when present — plus `lang`. The model receives
   structured fields, never a free-text prompt describing the route, so it
   cannot hallucinate a different itinerary.
3. Claude (Haiku 4.5) returns `{ narrative: string }` — 2-3 short, calm
   sentences in the requested language covering: walk to berth, which
   service/color, roughly how many stops, and (if present) when to leave.
4. Client passes `narrative` into the existing `speak()`. Hard ~1.5s client-side
   timeout; past that, fall back to today's
   `speak(t('welcomeSpeak', best.service, etaText))`, unchanged.
5. Exactly one narration call per trip — the deadline clause is one more field
   in the same request, never a second LLM call.

## Error handling contract

This is the load-bearing property of the whole design and must be covered by a
named test, not just informal behavior:

> **Every failure of `/api/v1/voice-intent` or `/api/v1/narrate-trip` — timeout,
> non-200, malformed JSON, empty result, rate-limit rejection, or the AI daily
> budget kill switch being tripped — must produce output identical to what the
> kiosk does today with these features absent entirely.**

No error toast, no new `KioskSpeechErrors` category, no partial state. The
commuter never knows these features exist unless they work.

## Security & cost controls

- `ANTHROPIC_API_KEY` in `.env`, loaded via the existing `load_dotenv()` call in
  `bus_engine.py`. Never referenced in `index.html` or any client-side file.
- Per-IP rate limit on both new endpoints (in-memory sliding window is
  sufficient — this is a single-kiosk deployment, not a multi-tenant service).
- Server-side Claude call timeout *and* client-side `AbortController` timeout —
  two independent guards against a hung request.
- A daily spend/call-count cap (env-configured) that disables both AI endpoints
  once tripped, falling back to today's behavior rather than an open-ended
  bill.
- Log success/failure counts and latency; do not log full transcripts by
  default (PII minimization).

## i18n additions

New keys in both `zh` and `en` dictionaries in `static/js/i18n.js`:

- `statusDepartBy`: `(time) => `建议 ${time} 前出发`` / `(time) => `Leave by
  ${time}``
- `statusUrgent`: `'现在出发才来得及'` / `'Leave now to make it'`

Shown both on the trip summary card (next to the existing time range) and in
the `assistant-status` caption line — captioned, not audio-only, per the
accessibility principle raised in the persona brainstorm (hard-of-hearing
commuters need the text, not just the speech).

## UI surface

- No new digital-human state. Narration reuses the existing `speaking` state;
  the added extraction → plan → narrate latency sits inside the wait a
  commuter already has today for STT + planning.
- Trip summary panel gets one additional line for deadline trips only
  (`depart_by` / `urgent`), using the new i18n keys.

## Testing plan

- **Backend**: all tests mock the Anthropic client — no real API calls in CI
  (cost, non-determinism). Cover:
  - `/api/v1/voice-intent` parses a well-formed structured response correctly.
  - `plan_trip_by_deadline` is pure arithmetic — tested directly with real
    inputs, no mocking needed, including the transfer/walk/none passthrough
    (no `depart_by` added) and the `urgent` boundary when `depart_by` has
    already passed.
  - `/api/v1/narrate-trip` returns the mocked narrative on success.
  - **The fallback contract above**, explicitly: simulate timeout, non-200,
    malformed JSON, and rate-limit rejection for both endpoints, and assert the
    resulting behavior matches the no-AI code path.
  - Rate limiter and daily-budget kill switch unit tests.
- **Frontend**: mock `fetch` to cover the `AbortController` timeout → fallback
  branch for both features; assert `speak()` receives the fallback template
  string when narration fails or times out.

## Open questions / future work

- `DEADLINE_BUFFER_MIN` = 5 is a starting guess, not user-validated — worth
  revisiting once real usage data exists.
- Deadline math covers `mode: 'direct'` trips only (see Data Flow). Extending
  it to transfer trips is a natural follow-up once the direct-mode version has
  shipped and been used.
- This spec's two endpoints are designed to be reusable as tool targets if the
  larger "reasoning concierge" (multi-turn, weather/crowding/accessibility
  negotiation) project happens later — not required for this spec to ship.
- Dialect speech, sign-language avatar, camera/vision features, and persona
  detection remain separate, unscoped ideas from the same brainstorm.
