const test = require('node:test');
const assert = require('node:assert/strict');
const { createStore, planStatus, DEFAULT_KEY } = require('./assistant-status.js');
const { translate } = require('./i18n.js');

// ─── The bug this exists to prevent ───────────────────────────────────────
// planJourney announced "正在规划最佳巴士方案…" and nothing ever took it down.
// renderTripSummary returns through four separate branches and none of them
// touched the status, so a finished route sat on screen next to a line still
// claiming it was being planned.

test('a completed direct plan reports the chosen service, not "planning"', () => {
  const status = planStatus({ type: 'bus', mode: 'direct', best: { service: '53', stops: 12 } });

  assert.equal(status.key, 'bestOption');
  assert.deepEqual(status.args, ['53']);
  assert.notEqual(status.key, 'planning');
});

test('a completed transfer plan names both services', () => {
  const status = planStatus({
    type: 'bus',
    mode: 'transfer',
    options: [{ leg1: { service: '53' }, leg2: { service: '12' } }],
  });

  assert.equal(status.key, 'bestOption');
  assert.deepEqual(status.args, ['53 → 12']);
});

test('a walk-only result reports the walk, not "planning"', () => {
  const status = planStatus({ type: 'walk', minutes: 7, dist_m: 560 });

  assert.equal(status.key, 'statusWalkSuggested');
  assert.deepEqual(status.args, [7]);
});

test('no route found reports no route', () => {
  assert.equal(planStatus({ type: 'none' }).key, 'noRoute');
});

test('every plan shape produces a terminal status', () => {
  const shapes = [
    { type: 'bus', mode: 'direct', best: { service: '53' } },
    { type: 'bus', mode: 'direct', options: [{ service: '21' }] },
    { type: 'bus', mode: 'direct', options: [] },
    { type: 'bus', mode: 'transfer', options: [{ leg1: { service: '5' }, leg2: { service: '9' } }] },
    { type: 'bus', mode: 'transfer', options: [] },
    { type: 'walk', minutes: 3 },
    { type: 'none' },
    {},
    null,
    undefined,
  ];

  for (const shape of shapes) {
    const status = planStatus(shape);
    assert.ok(status.key, `no status for ${JSON.stringify(shape)}`);
    assert.notEqual(status.key, 'planning', `left as "planning" for ${JSON.stringify(shape)}`);
    assert.ok(translate('zh', status.key, ...status.args), `${status.key} has no zh text`);
    assert.ok(translate('en', status.key, ...status.args), `${status.key} has no en text`);
  }
});

test('a malformed plan response falls back rather than throwing', () => {
  assert.equal(planStatus({ type: 'bus', mode: 'direct' }).key, 'noRoute');
  assert.equal(planStatus({ type: 'bus', mode: 'transfer', options: [{}] }).key, 'noRoute');
});

// ─── Language switching ───────────────────────────────────────────────────
// setLanguage used to overwrite the line with t('ready'), discarding real
// state. The store keeps the key so the same status re-renders in the new
// language instead.

test('the same status re-renders in the other language', () => {
  const store = createStore(translate);
  store.set('planning');

  assert.equal(store.render('zh'), '正在规划最佳巴士方案…');
  assert.equal(store.render('en'), 'Planning the best bus options…');
});

test('arguments survive a language switch', () => {
  const store = createStore(translate);
  store.set('bestOption', '53');

  assert.ok(store.render('zh').includes('53'));
  assert.ok(store.render('en').includes('53'));
  assert.notEqual(store.render('zh'), store.render('en'));
});

test('switching language does not silently become "ready"', () => {
  const store = createStore(translate);
  store.set('planning');

  const after = store.render('en');
  assert.notEqual(after, translate('en', 'ready'), 'in-progress state was discarded');
});

test('the store starts idle', () => {
  const store = createStore(translate);
  assert.equal(store.current().key, DEFAULT_KEY);
  assert.equal(store.render('zh'), translate('zh', 'ready'));
});

test('reset returns to idle', () => {
  const store = createStore(translate);
  store.set('planning');
  store.reset();
  assert.equal(store.current().key, DEFAULT_KEY);
});

test('an empty key is ignored rather than blanking the line', () => {
  const store = createStore(translate);
  store.set('planning');
  store.set('');
  store.set(null);
  assert.equal(store.current().key, 'planning');
});

test('current() hands back a copy, not the live args', () => {
  const store = createStore(translate);
  store.set('bestOption', '53');
  store.current().args.push('tampered');
  assert.deepEqual(store.current().args, ['53']);
});

// ─── i18n coverage for the keys this feature introduces ───────────────────

const REQUIRED_KEYS = [
  'planning', 'ready', 'noRoute', 'bestOption', 'routeFailed', 'planFailed',
  'foundNearby', 'statusWalkSuggested', 'destinationResolved', 'nearbyFailed',
  'searchingFor', 'destinationNotFound', 'destinationUnresolvable',
];

test('every status key is translated in both languages', () => {
  for (const key of REQUIRED_KEYS) {
    for (const lang of ['zh', 'en']) {
      const text = translate(lang, key, 'X');
      assert.ok(text, `${lang}/${key} missing`);
      assert.notEqual(text, key, `${lang}/${key} fell through to the raw key`);
    }
  }
});

test('the two languages actually differ for status text', () => {
  for (const key of ['planning', 'ready', 'noRoute', 'destinationNotFound']) {
    assert.notEqual(
      translate('zh', key, 'X'),
      translate('en', key, 'X'),
      `${key} reads identically in both languages`,
    );
  }
});
