const test = require('node:test');
const assert = require('node:assert/strict');
const { computeDirectTripMinutes } = require('./trip-duration.js');

// Mirrors buildDirectTimeline's own formula exactly, so the panel's badge
// and the spoken ETA can never read two different numbers for one trip.

test('computeDirectTripMinutes sums the travel and walk legs', () => {
  const mins = computeDirectTripMinutes({ stops: 5, dist_km: 1.0 });
  assert.equal(mins, 10 + 12); // travel = max(4, 5*2)=10, walk = round(1.0*12)=12
});

test('computeDirectTripMinutes floors travel time at 4 minutes for very short hops', () => {
  const mins = computeDirectTripMinutes({ stops: 1, dist_km: 0 });
  assert.equal(mins, 4 + 0);
});

test('computeDirectTripMinutes defaults stops and distance when missing, like the panel does', () => {
  const mins = computeDirectTripMinutes({});
  assert.equal(mins, Math.max(4, 5 * 2) + Math.round(0.5 * 12));
});

test('computeDirectTripMinutes handles a null best (no route found)', () => {
  const mins = computeDirectTripMinutes(null);
  assert.equal(mins, Math.max(4, 5 * 2) + Math.round(0.5 * 12));
});

test('computeDirectTripMinutes never depends on live-arrival data being present', () => {
  const withLive = computeDirectTripMinutes({ stops: 3, dist_km: 0.4, live: { minutes: 7 } });
  const withoutLive = computeDirectTripMinutes({ stops: 3, dist_km: 0.4, live: null });
  assert.equal(withLive, withoutLive);
});
