const test = require('node:test');
const assert = require('node:assert/strict');
const { translate, DICTIONARIES } = require('./i18n.js');

test('translate returns the zh string for a static key', () => {
  assert.equal(translate('zh', 'homeTileWayfindingTitle'), '路线指引');
});

test('translate returns the en string for a static key', () => {
  assert.equal(translate('en', 'homeTileWayfindingTitle'), 'Wayfinding');
});

test('translate calls a function-valued key with the given args', () => {
  assert.equal(translate('zh', 'loadRoute', '118'), '已加载线路 118');
});

test('translate falls back to the key itself when missing from both dictionaries', () => {
  assert.equal(translate('zh', 'thisKeyDoesNotExist'), 'thisKeyDoesNotExist');
});

test('translate falls back to zh dictionary when the language is unknown', () => {
  assert.equal(translate('fr', 'homeTileWayfindingTitle'), DICTIONARIES.zh.homeTileWayfindingTitle);
});

test('both dictionaries define every "Find My Berth" key', () => {
  ['berthLookupLabel', 'berthLookupTitle', 'berthLookupSubtitle'].forEach((key) => {
    assert.ok(DICTIONARIES.en[key], `en.${key} missing`);
    assert.ok(DICTIONARIES.zh[key], `zh.${key} missing`);
  });
});

test('both dictionaries mention the stop name in the offsite-boarding note', () => {
  assert.ok(translate('en', 'berthOffsiteNote', 'Exit B').includes('Exit B'));
  assert.ok(translate('zh', 'berthOffsiteNote', 'Exit B').includes('Exit B'));
});

test('both dictionaries define every "Nearby Places" key', () => {
  [
    'nearbyPlacesHeading', 'nearbyPlacesLoading', 'nearbyPlacesError',
    'nearbyPlacesFilterAll', 'nearbyPlacesAccessible', 'nearbyPlacesApprox',
  ].forEach((key) => {
    assert.ok(DICTIONARIES.en[key], `en.${key} missing`);
    assert.ok(DICTIONARIES.zh[key], `zh.${key} missing`);
  });
});
