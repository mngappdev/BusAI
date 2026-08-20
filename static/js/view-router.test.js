const test = require('node:test');
const assert = require('node:assert/strict');
const { TILES, VALID_VIEWS, resolveView } = require('./view-router.js');

test('VALID_VIEWS contains home plus one entry per tile, all unique', () => {
  assert.equal(VALID_VIEWS.length, TILES.length + 1);
  assert.equal(new Set(VALID_VIEWS).size, VALID_VIEWS.length);
  assert.ok(VALID_VIEWS.includes('home'));
});

test('TILES covers the four spec modules in spec order', () => {
  const ids = TILES.map((tile) => tile.id);
  assert.deepEqual(ids, ['wayfinding', 'lost-found', 'feedback', 'nearby']);
});

test('each tile has an icon, titleKey, and subtitleKey', () => {
  TILES.forEach((tile) => {
    assert.equal(typeof tile.icon, 'string');
    assert.equal(typeof tile.titleKey, 'string');
    assert.equal(typeof tile.subtitleKey, 'string');
  });
});

test('resolveView passes through a known view', () => {
  assert.equal(resolveView('wayfinding'), 'wayfinding');
});

test('resolveView falls back to home for an unknown view', () => {
  assert.equal(resolveView('bogus'), 'home');
});

test('resolveView falls back to home for undefined or null', () => {
  assert.equal(resolveView(undefined), 'home');
  assert.equal(resolveView(null), 'home');
});
