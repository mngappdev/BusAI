const test = require('node:test');
const assert = require('node:assert/strict');
const {
  BOARDING_BERTHS,
  buildSchematicHtml,
  ALIGHTING_IDS,
  BOARDING_POSITIONS,
  buildFloorPlanSvg,
} = require('./berth-schematic.js');

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

test('BOARDING_POSITIONS has an x/y coordinate for every boarding berth', () => {
  BOARDING_BERTHS.forEach((berth) => {
    const pos = BOARDING_POSITIONS[berth];
    assert.equal(typeof pos.x, 'number', `${berth} missing x`);
    assert.equal(typeof pos.y, 'number', `${berth} missing y`);
  });
});

test('ALIGHTING_IDS lists exactly A1 through A5', () => {
  assert.deepEqual(ALIGHTING_IDS, ['A1', 'A2', 'A3', 'A4', 'A5']);
});

test('buildFloorPlanSvg renders all 10 boarding berths and 5 alighting berths', () => {
  const svg = buildFloorPlanSvg('B7');
  BOARDING_BERTHS.forEach((berth) => {
    assert.ok(svg.includes(`>${berth}<`), `expected ${berth} label in svg`);
  });
  ALIGHTING_IDS.forEach((id) => {
    assert.ok(svg.includes(`>${id}<`), `expected ${id} label in svg`);
  });
});

test('buildFloorPlanSvg marks exactly the requested berth active', () => {
  const svg = buildFloorPlanSvg('B7');
  const activeCount = (svg.match(/fp-berth-active/g) || []).length;
  assert.equal(activeCount, 1);
});

test('buildFloorPlanSvg draws a route path ending at the target berth\'s coordinates', () => {
  const svg = buildFloorPlanSvg('B9');
  const target = BOARDING_POSITIONS.B9;
  assert.ok(svg.includes('class="fp-route"'), 'expected a route path element');
  assert.ok(svg.includes(`${target.x} ${target.y}`), 'expected the path to end at B9\'s coordinates');
});

test('buildFloorPlanSvg omits the route path when no berth is active', () => {
  const svg = buildFloorPlanSvg(null);
  assert.ok(!svg.includes('class="fp-route"'));
});

test('buildFloorPlanSvg omits the route path for an unknown berth id', () => {
  const svg = buildFloorPlanSvg('B99');
  assert.ok(!svg.includes('class="fp-route"'));
});

test('buildFloorPlanSvg is valid enough XML to be embedded (balanced svg tags)', () => {
  const svg = buildFloorPlanSvg('B3');
  const opens = (svg.match(/<svg/g) || []).length;
  const closes = (svg.match(/<\/svg>/g) || []).length;
  assert.equal(opens, 1);
  assert.equal(closes, 1);
});
