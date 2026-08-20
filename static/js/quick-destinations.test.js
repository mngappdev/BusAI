const test = require('node:test');
const assert = require('node:assert/strict');
const { QUICK_DESTINATIONS } = require('./quick-destinations.js');

test('QUICK_DESTINATIONS has 4 entries with unique ids', () => {
  assert.equal(QUICK_DESTINATIONS.length, 4);
  const ids = QUICK_DESTINATIONS.map((d) => d.id);
  assert.equal(new Set(ids).size, ids.length);
});

test('every entry has an icon, labelKey, lat, and lon', () => {
  QUICK_DESTINATIONS.forEach((dest) => {
    assert.equal(typeof dest.icon, 'string');
    assert.equal(typeof dest.labelKey, 'string');
    assert.equal(typeof dest.lat, 'number');
    assert.equal(typeof dest.lon, 'number');
  });
});

test('every coordinate is within Singapore\'s bounding box', () => {
  QUICK_DESTINATIONS.forEach((dest) => {
    assert.ok(dest.lat > 1.0 && dest.lat < 1.6, `${dest.id} latitude out of range: ${dest.lat}`);
    assert.ok(dest.lon > 103.5 && dest.lon < 104.1, `${dest.id} longitude out of range: ${dest.lon}`);
  });
});
