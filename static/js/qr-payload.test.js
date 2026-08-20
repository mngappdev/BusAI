const test = require('node:test');
const assert = require('node:assert/strict');
const { buildDirectTripPayload } = require('./qr-payload.js');

test('buildDirectTripPayload includes service, stops, and berth', () => {
  const text = buildDirectTripPayload({
    service: '58',
    fromName: 'Pasir Ris Int',
    toName: 'Changi Airport',
    stops: 6,
    berth: 'B1',
  });
  assert.ok(text.includes('58'));
  assert.ok(text.includes('Pasir Ris Int'));
  assert.ok(text.includes('Changi Airport'));
  assert.ok(text.includes('6'));
  assert.ok(text.includes('B1'));
});

test('buildDirectTripPayload omits the berth line when berth is absent', () => {
  const text = buildDirectTripPayload({
    service: '5',
    fromName: 'Some Stop',
    toName: 'Other Stop',
    stops: 3,
  });
  assert.ok(!text.toLowerCase().includes('berth'));
});
