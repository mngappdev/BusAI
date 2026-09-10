const test = require('node:test');
const assert = require('node:assert/strict');
const { setState, stateClass, STATES } = require('./digital-human.js');

// A tiny stand-in for element.classList — add/remove/contains over a Set.
function fakeEl(initial = []) {
  const set = new Set(initial);
  return {
    classList: {
      add: (...c) => c.forEach((x) => set.add(x)),
      remove: (...c) => c.forEach((x) => set.delete(x)),
      contains: (x) => set.has(x),
    },
    _classes: () => [...set],
  };
}

test('STATES is the three-state vocabulary, idle first', () => {
  assert.deepEqual(STATES, ['idle', 'listening', 'speaking']);
});

test('setState puts exactly one dh-state-* class on the element', () => {
  const el = fakeEl();
  setState(el, 'listening');
  assert.ok(el.classList.contains('dh-state-listening'));
  assert.equal(el._classes().filter((c) => c.startsWith('dh-state-')).length, 1);
});

test('setState replaces the previous state rather than stacking', () => {
  const el = fakeEl();
  setState(el, 'listening');
  setState(el, 'speaking');
  assert.ok(el.classList.contains('dh-state-speaking'));
  assert.ok(!el.classList.contains('dh-state-listening'));
});

test('setState leaves unrelated classes untouched', () => {
  const el = fakeEl(['digital-human', 'foo']);
  setState(el, 'speaking');
  assert.ok(el.classList.contains('digital-human'));
  assert.ok(el.classList.contains('foo'));
});

test('an unknown state falls back to idle', () => {
  const el = fakeEl();
  const resolved = setState(el, 'thinking');
  assert.equal(resolved, 'idle');
  assert.ok(el.classList.contains('dh-state-idle'));
});

test('a missing state falls back to idle', () => {
  const el = fakeEl();
  assert.equal(setState(el), 'idle');
  assert.equal(setState(el, null), 'idle');
  assert.equal(setState(el, ''), 'idle');
});

test('setState returns the resolved state name', () => {
  const el = fakeEl();
  assert.equal(setState(el, 'speaking'), 'speaking');
  assert.equal(setState(el, 'idle'), 'idle');
});

test('a null element is a no-op, not a throw', () => {
  assert.doesNotThrow(() => setState(null, 'speaking'));
  assert.doesNotThrow(() => setState(undefined, 'idle'));
  assert.equal(setState(null, 'speaking'), 'speaking');
});

test('an element without classList is a no-op, not a throw', () => {
  assert.doesNotThrow(() => setState({}, 'listening'));
});

test('stateClass maps a state to its class name', () => {
  assert.equal(stateClass('listening'), 'dh-state-listening');
  assert.equal(stateClass('thinking'), 'dh-state-idle');
  assert.equal(stateClass(), 'dh-state-idle');
});
