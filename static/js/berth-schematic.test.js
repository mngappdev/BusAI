const test = require('node:test');
const assert = require('node:assert/strict');
const {
  BOARDING_BERTHS,
  BERTH_SERVICES,
  ALIGHTING_IDS,
  BOARDING_POSITIONS,
  KIOSK_POSITION,
  ROUTE_WAYPOINTS,
  buildFloorPlanSvg,
} = require('./berth-schematic.js');

test('BOARDING_BERTHS lists exactly B1 through B10', () => {
  assert.deepEqual(BOARDING_BERTHS, ['B1', 'B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B9', 'B10']);
});

test('ALIGHTING_IDS lists exactly A1 through A5', () => {
  assert.deepEqual(ALIGHTING_IDS, ['A1', 'A2', 'A3', 'A4', 'A5']);
});

// ── Signage data (landtransportguru.net + the official BERTH LAYOUT diagram) ──

test('BERTH_SERVICES matches the published berth assignments', () => {
  assert.deepEqual(BERTH_SERVICES.B1, ['58', '88']);
  assert.deepEqual(BERTH_SERVICES.B2, ['12', '12e', '21']);
  assert.deepEqual(BERTH_SERVICES.B3, ['17', '68']);
  assert.deepEqual(BERTH_SERVICES.B4, ['359W', '403']);
  assert.deepEqual(BERTH_SERVICES.B5, ['358W', '46']);
  assert.deepEqual(BERTH_SERVICES.B6, ['359E', '354']);
  assert.deepEqual(BERTH_SERVICES.B7, ['358E', '3']);
  assert.deepEqual(BERTH_SERVICES.B8, ['5', '6']);
  assert.deepEqual(BERTH_SERVICES.B9, ['15', '518', '518A']);
  assert.deepEqual(BERTH_SERVICES.B10, []);
});

test('the two looping services appear at both of their berths', () => {
  assert.ok(BERTH_SERVICES.B4.includes('359W') && BERTH_SERVICES.B6.includes('359E'));
  assert.ok(BERTH_SERVICES.B5.includes('358W') && BERTH_SERVICES.B7.includes('358E'));
});

// ── Geometry ────────────────────────────────────────────────────────────────

test('every boarding berth has a position and a route from the kiosk', () => {
  BOARDING_BERTHS.forEach((berth) => {
    const pos = BOARDING_POSITIONS[berth];
    assert.equal(typeof pos.x, 'number', `${berth} missing x`);
    assert.equal(typeof pos.y, 'number', `${berth} missing y`);
    const route = ROUTE_WAYPOINTS[berth];
    assert.ok(Array.isArray(route) && route.length >= 2, `${berth} missing route waypoints`);
  });
});

test('every route starts at the kiosk and ends at its berth', () => {
  BOARDING_BERTHS.forEach((berth) => {
    const route = ROUTE_WAYPOINTS[berth];
    const [firstX, firstY] = route[0];
    assert.equal(firstX, KIOSK_POSITION.x, `${berth} route does not start at the kiosk`);
    assert.equal(firstY, KIOSK_POSITION.y, `${berth} route does not start at the kiosk`);
    const [lastX, lastY] = route[route.length - 1];
    const pos = BOARDING_POSITIONS[berth];
    const distance = Math.hypot(lastX - pos.x, lastY - pos.y);
    assert.ok(distance < 60, `${berth} route ends ${Math.round(distance)}u from the berth`);
  });
});

// ── Rendering ───────────────────────────────────────────────────────────────

test('buildFloorPlanSvg renders every berth, its services and the alighting strip', () => {
  const svg = buildFloorPlanSvg('B7');
  BOARDING_BERTHS.forEach((berth) => {
    assert.ok(svg.includes(`>${berth}<`), `expected a ${berth} label`);
  });
  assert.ok(svg.includes('>359W<') && svg.includes('>359E<'), 'expected both 359 loop labels');
  assert.ok(svg.includes('>12e<'), 'expected service 12e');
  assert.ok(svg.includes('A1'), 'expected the alighting strip');
});

test('buildFloorPlanSvg names the interchange and marks the kiosk', () => {
  const svg = buildFloorPlanSvg('B3');
  assert.ok(svg.includes('PASIR RIS BUS INTERCHANGE'));
  assert.ok(svg.includes('fp-kiosk'), 'expected a you-are-here marker');
});

test('buildFloorPlanSvg highlights exactly the requested berth', () => {
  const svg = buildFloorPlanSvg('B7');
  assert.equal((svg.match(/fp-berth-active/g) || []).length, 1);
  assert.equal((svg.match(/class="fp-route"/g) || []).length, 1);
});

test('buildFloorPlanSvg highlights both berths of an ambiguous service', () => {
  const svg = buildFloorPlanSvg(['B4', 'B6']);
  assert.equal((svg.match(/fp-berth-active/g) || []).length, 2);
  assert.equal((svg.match(/class="fp-route"/g) || []).length, 2, 'expected a route to each berth');
});

test('buildFloorPlanSvg route ends at the target berth', () => {
  const svg = buildFloorPlanSvg('B9');
  const route = ROUTE_WAYPOINTS.B9;
  const [endX, endY] = route[route.length - 1];
  assert.ok(svg.includes(`${endX} ${endY}`), 'expected the path to reach B9');
});

test('buildFloorPlanSvg omits routes when nothing is active', () => {
  [null, undefined, [], 'B99'].forEach((input) => {
    const svg = buildFloorPlanSvg(input);
    assert.ok(!svg.includes('class="fp-route"'), `expected no route for ${JSON.stringify(input)}`);
    assert.ok(!svg.includes('fp-berth-active'), `expected no highlight for ${JSON.stringify(input)}`);
  });
});

test('buildFloorPlanSvg still renders the full plan when nothing is active', () => {
  const svg = buildFloorPlanSvg(null);
  BOARDING_BERTHS.forEach((berth) => {
    assert.ok(svg.includes(`>${berth}<`), `expected a ${berth} label`);
  });
});

test('buildFloorPlanSvg emits well-formed, complete markup', () => {
  const svg = buildFloorPlanSvg('B3');
  assert.equal((svg.match(/<svg/g) || []).length, 1);
  assert.equal((svg.match(/<\/svg>/g) || []).length, 1);
  assert.ok(!svg.includes('undefined'), 'output contains "undefined"');
  assert.ok(!svg.includes('NaN'), 'output contains "NaN"');
  assert.equal((svg.match(/<g/g) || []).length, (svg.match(/<\/g>/g) || []).length, 'unbalanced <g>');
  assert.equal((svg.match(/<text/g) || []).length, (svg.match(/<\/text>/g) || []).length, 'unbalanced <text>');
});
