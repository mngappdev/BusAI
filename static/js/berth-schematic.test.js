const test = require('node:test');
const assert = require('node:assert/strict');
const { BOARDING_BERTHS, buildSchematicHtml } = require('./berth-schematic.js');

test('BOARDING_BERTHS lists exactly B1 through B10', () => {
  assert.deepEqual(BOARDING_BERTHS, ['B1', 'B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B9', 'B10']);
});

test('buildSchematicHtml renders all 10 boarding berths', () => {
  const html = buildSchematicHtml('B5');
  BOARDING_BERTHS.forEach((berth) => {
    assert.ok(html.includes(`>${berth}<`), `expected ${berth} cell in output`);
  });
});

test('buildSchematicHtml marks exactly the requested berth as active', () => {
  const html = buildSchematicHtml('B5');
  const activeCount = (html.match(/berth-cell active/g) || []).length;
  assert.equal(activeCount, 1);
  assert.ok(html.includes('berth-cell active">B5<'));
});

test('buildSchematicHtml marks no berth active when the requested berth does not exist', () => {
  const html = buildSchematicHtml('B99');
  assert.ok(!html.includes('active'));
});

test('buildSchematicHtml marks no berth active when given null', () => {
  const html = buildSchematicHtml(null);
  assert.ok(!html.includes('active'));
});
