const test = require('node:test');
const assert = require('node:assert/strict');
const { levelForLoad, labelKeyForLevel } = require('./crowding.js');

test('levelForLoad maps 有座 to green', () => {
  assert.equal(levelForLoad('有座'), 'green');
});

test('levelForLoad maps 较挤 to amber', () => {
  assert.equal(levelForLoad('较挤'), 'amber');
});

test('levelForLoad maps 拥挤 to red', () => {
  assert.equal(levelForLoad('拥挤'), 'red');
});

test('levelForLoad maps null to gray', () => {
  assert.equal(levelForLoad(null), 'gray');
});

test('levelForLoad maps an unrecognized string to gray', () => {
  assert.equal(levelForLoad('未知'), 'gray');
});

test('labelKeyForLevel maps each level to the right i18n key', () => {
  assert.equal(labelKeyForLevel('green'), 'quiet');
  assert.equal(labelKeyForLevel('amber'), 'moderate');
  assert.equal(labelKeyForLevel('red'), 'crowded');
  assert.equal(labelKeyForLevel('gray'), 'noLiveData');
});

test('labelKeyForLevel falls back to noLiveData for an unknown level', () => {
  assert.equal(labelKeyForLevel('bogus'), 'noLiveData');
});
