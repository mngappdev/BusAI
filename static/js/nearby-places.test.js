const test = require('node:test');
const assert = require('node:assert/strict');
const { groupByCategory, formatWalkLabel } = require('./nearby-places.js');

const CATEGORIES = [
  { id: 'food-mall', icon: '🍽️', nameEn: 'Food & Mall', nameZh: '美食与商场' },
  { id: 'amenities', icon: '🚻', nameEn: 'Public Amenities', nameZh: '公共便民' },
];

const PLACES = [
  { id: 'a', category: 'amenities', distance_m: 10 },
  { id: 'b', category: 'food-mall', distance_m: 5 },
  { id: 'c', category: 'amenities', distance_m: 20 },
];

test('groupByCategory returns one group per category, in category order', () => {
  const groups = groupByCategory(CATEGORIES, PLACES);
  assert.deepEqual(groups.map((g) => g.id), ['food-mall', 'amenities']);
});

test('groupByCategory assigns each place to its own category, preserving input order', () => {
  const groups = groupByCategory(CATEGORIES, PLACES);
  const amenities = groups.find((g) => g.id === 'amenities');
  assert.deepEqual(amenities.places.map((p) => p.id), ['a', 'c']);
});

test('groupByCategory carries the category metadata (icon, names) onto each group', () => {
  const groups = groupByCategory(CATEGORIES, PLACES);
  const foodMall = groups.find((g) => g.id === 'food-mall');
  assert.equal(foodMall.icon, '🍽️');
  assert.equal(foodMall.nameEn, 'Food & Mall');
});

test('groupByCategory includes a category even when it has no places', () => {
  const groups = groupByCategory(CATEGORIES, [{ id: 'b', category: 'food-mall', distance_m: 5 }]);
  const amenities = groups.find((g) => g.id === 'amenities');
  assert.deepEqual(amenities.places, []);
});

test('groupByCategory drops a place whose category does not exist', () => {
  const groups = groupByCategory(CATEGORIES, [{ id: 'x', category: 'ghost', distance_m: 1 }, ...PLACES]);
  const all = groups.flatMap((g) => g.places.map((p) => p.id));
  assert.ok(!all.includes('x'));
});

test('formatWalkLabel rounds down to "arrived" for essentially zero distance', () => {
  assert.equal(formatWalkLabel(0, 0, 'en'), 'Here');
  assert.equal(formatWalkLabel(0, 0, 'zh'), '就在这里');
});

test('formatWalkLabel shows walk minutes otherwise', () => {
  assert.equal(formatWalkLabel(320, 4, 'en'), '320m · 4 min walk');
  assert.equal(formatWalkLabel(320, 4, 'zh'), '320米 · 步行4分钟');
});
