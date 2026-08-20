const test = require('node:test');
const assert = require('node:assert/strict');
const { buildDirectTripPayload, utf8ToBytes } = require('./qr-payload.js');

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

test('buildDirectTripPayload uses provided labels for a localized QR payload', () => {
  const text = buildDirectTripPayload(
    { service: '58', fromName: '巴西立', toName: '樟宜机场', stops: 6, berth: 'B1' },
    { bus: '巴士', to: '→', stops: '站', berth: '泊位' }
  );
  assert.ok(text.includes('巴士 58'));
  assert.ok(text.includes('巴西立 → 樟宜机场'));
  assert.ok(text.includes('6 站'));
  assert.ok(text.includes('泊位 B1'));
});

test('utf8ToBytes encodes a known Chinese character to its exact UTF-8 byte sequence', () => {
  assert.deepEqual(utf8ToBytes('巴'), [0xE5, 0xB7, 0xB4]);
});

test('utf8ToBytes encodes plain ASCII unchanged', () => {
  assert.deepEqual(utf8ToBytes('Bus 58'), [66, 117, 115, 32, 53, 56]);
});
