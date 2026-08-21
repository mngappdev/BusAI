const test = require('node:test');
const assert = require('node:assert/strict');
const { pickBestPreview } = require('./home-preview.js');

test('pickBestPreview returns the first stop with a real arrival time', () => {
  const stops = [
    { nearest_arrival: null },
    { nearest_arrival: { service: '58', minutes: 5, load: '有座', is_wab: false } },
    { nearest_arrival: { service: '3', minutes: 2, load: '拥挤', is_wab: false } },
  ];
  assert.deepEqual(pickBestPreview(stops), { service: '58', minutes: 5 });
});

test('pickBestPreview returns null when no stop has live arrival data', () => {
  const stops = [
    { nearest_arrival: null },
    { nearest_arrival: { service: '58', minutes: null, load: null, is_wab: false } },
  ];
  assert.equal(pickBestPreview(stops), null);
});

test('pickBestPreview returns null for an empty or missing stop list', () => {
  assert.equal(pickBestPreview([]), null);
  assert.equal(pickBestPreview(undefined), null);
  assert.equal(pickBestPreview(null), null);
});
