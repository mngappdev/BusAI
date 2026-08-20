const test = require('node:test');
const assert = require('node:assert/strict');
const {
  FONT_SCALE_MIN,
  FONT_SCALE_MAX,
  FONT_SCALE_STEP,
  FONT_SCALE_DEFAULT,
  clampFontScale,
  nextFontScale,
} = require('./accessibility.js');

test('clampFontScale leaves an in-range value unchanged', () => {
  assert.equal(clampFontScale(1.15), 1.15);
});

test('clampFontScale clamps above the max', () => {
  assert.equal(clampFontScale(3), FONT_SCALE_MAX);
});

test('clampFontScale clamps below the min', () => {
  assert.equal(clampFontScale(0.1), FONT_SCALE_MIN);
});

test('nextFontScale increases by one step', () => {
  assert.equal(nextFontScale(FONT_SCALE_DEFAULT, 'increase'), FONT_SCALE_DEFAULT + FONT_SCALE_STEP);
});

test('nextFontScale decreases by one step', () => {
  assert.equal(nextFontScale(FONT_SCALE_DEFAULT, 'decrease'), FONT_SCALE_DEFAULT - FONT_SCALE_STEP);
});

test('nextFontScale stays clamped at the max when already there', () => {
  assert.equal(nextFontScale(FONT_SCALE_MAX, 'increase'), FONT_SCALE_MAX);
});

test('nextFontScale stays clamped at the min when already there', () => {
  assert.equal(nextFontScale(FONT_SCALE_MIN, 'decrease'), FONT_SCALE_MIN);
});

test('nextFontScale defaults the current scale to FONT_SCALE_DEFAULT when undefined', () => {
  assert.equal(nextFontScale(undefined, 'increase'), FONT_SCALE_DEFAULT + FONT_SCALE_STEP);
});
