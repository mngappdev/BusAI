const test = require('node:test');
const assert = require('node:assert/strict');
const { computeDirectTripMinutes } = require('./trip-duration.js');

// Mirrors buildDirectTimeline's own formula exactly, so the panel's badge
// and the spoken ETA can never read two different numbers for one trip.

test('computeDirectTripMinutes sums the travel and walk legs', () => {
  const mins = computeDirectTripMinutes({ stops: 5, walk_to_dest_min: 3 });
  assert.equal(mins, 10 + 3); // travel = max(4, 5*2) = 10
});

test('computeDirectTripMinutes floors travel time at 4 minutes for very short hops', () => {
  const mins = computeDirectTripMinutes({ stops: 1, walk_to_dest_min: 1 });
  assert.equal(mins, 4 + 1);
});

test('computeDirectTripMinutes defaults stops and walk when missing, like the panel does', () => {
  const mins = computeDirectTripMinutes({});
  assert.equal(mins, Math.max(4, 5 * 2) + 5);
});

test('computeDirectTripMinutes handles a null best (no route found)', () => {
  const mins = computeDirectTripMinutes(null);
  assert.equal(mins, Math.max(4, 5 * 2) + 5);
});

test('computeDirectTripMinutes never depends on live-arrival data being present', () => {
  const withLive = computeDirectTripMinutes({ stops: 3, walk_to_dest_min: 2, live: { minutes: 7 } });
  const withoutLive = computeDirectTripMinutes({ stops: 3, walk_to_dest_min: 2, live: null });
  assert.equal(withLive, withoutLive);
});

test('computeDirectTripMinutes floors the walk leg at 1 minute', () => {
  const mins = computeDirectTripMinutes({ stops: 2, walk_to_dest_min: 0 });
  assert.equal(mins, 4 + 1);
});

// ─── Regression ───────────────────────────────────────────────────────────
// dist_km is the distance travelled ON the bus. Scaling it by 12 min/km once
// reported a 2-minute walk to Changi Airport T2 as 101 minutes.

test('computeDirectTripMinutes ignores dist_km entirely', () => {
  const longRide = computeDirectTripMinutes({ stops: 12, dist_km: 8.4, walk_to_dest_min: 2 });
  const shortRide = computeDirectTripMinutes({ stops: 12, dist_km: 0.1, walk_to_dest_min: 2 });

  assert.equal(longRide, shortRide, 'on-bus distance must not move the walk leg');
  assert.equal(longRide, 24 + 2);
});

test('computeDirectTripMinutes does not reproduce the 101-minute walk', () => {
  const mins = computeDirectTripMinutes({ stops: 12, dist_km: 8.4, walk_to_dest_min: 2 });
  assert.notEqual(mins - 24, Math.round(8.4 * 12));
  assert.ok(mins < 40, `expected a sane total, got ${mins}`);
});
