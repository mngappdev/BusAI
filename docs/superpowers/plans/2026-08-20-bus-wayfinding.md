# Bus Wayfinding Enhancements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fill in the parts of the spec's "1. 智能寻路与乘车指引 (Bus Wayfinding)" section the
existing Wayfinding screen doesn't cover yet: berth/bay display for boarding, a
crowding indicator (Green/Amber/Red), "热门直达" quick-destination buttons, a
QR-code takeaway of the planned route, and unifying the search box so it accepts
bus stop codes/names in addition to postcodes and addresses — without touching the
Kiosk Shell's home screen, navigation, or accessibility features (already shipped).

**Architecture:** The Wayfinding screen already exists (`data-view="wayfinding"` in
`index.html`, wired to the FastAPI backend in `main.py`/`bus_engine.py`). This plan
adds one new static data file (`berth_map.json`, hand-curated real data for one real
interchange — Pasir Ris Bus Interchange), one backend lookup method, and four new
dependency-free UMD JS modules under `static/js/` (following the exact pattern
`static/js/i18n.js`/`view-router.js`/`accessibility.js` already established:
`node --test` for pure logic, DOM wiring added to the existing inline script). One
new CDN `<script>` tag adds QR-code generation, matching the existing
Leaflet/Tailwind CDN pattern — no npm/build step anywhere in this repo.

**Tech Stack:** FastAPI (existing), vanilla JS + Tailwind CDN + Leaflet CDN
(existing), one new CDN dependency (`qrcode-generator`, a small dependency-free JS
QR encoder), Node.js 18+ built-in test runner for the new JS modules, pytest for
the new backend logic (both already set up in this repo).

**Spec:** [docs/superpowers/specs/2026-08-20-goahead-kiosk-system.md](../specs/2026-08-20-goahead-kiosk-system.md)
— this plan implements the "1. 智能寻路与乘车指引 (Bus Wayfinding)" section only.
Sections 2-4 (Lost & Found, Feedback, Nearby POI) are separate future plans.

## Global Constraints

- Node.js 18+ required for `node --test "static/js/*.test.js"` (the quoted-glob
  form — the bare-directory form doesn't work on Node 24, see the Kiosk Shell
  plan's Global Constraints for why).
- No new frontend build tooling: everything stays plain `<script src>` CDN tags.
- Every new user-facing string needs both a `zh` and an `en` entry in
  `static/js/i18n.js`.
- Berth/bay data is real but scoped to exactly one interchange (Pasir Ris Bus
  Interchange, LTA `BusStopCode` `77009`) — hand-curated from public
  documentation (landtransportguru.net), since LTA's open DataMall does not
  publish berth-level data for any interchange. Every other stop in the system
  has no berth data and must show "no berth info" gracefully, not an error.
- The berth "floor plan" is an abstract schematic grid (which berth is
  highlighted), not a scaled reproduction of the interchange's physical layout —
  no real floor-plan image/blueprint exists in this repo to reproduce from.
- This plan does not touch the Kiosk Shell's home screen, view router, or
  accessibility toolbar (`static/js/view-router.js`, `static/js/accessibility.js`,
  the `showView`/`renderHomeTiles`/`initAccessibility` functions in
  `index.html`) — only the `data-view="wayfinding"` screen's own content and the
  Wayfinding-specific backend endpoints.

---

### Task 1: Berth data + `BusSmartEngine.get_berth()`

**Files:**
- Create: `berth_map.json` (repo root, same location as `bus_stops.json`/`bus_routes.json`)
- Modify: `bus_engine.py:1-24` (`__init__`)
- Test: `tests/test_berth.py`

**Interfaces:**
- Produces: `BusSmartEngine.get_berth(self, stop_code, service_no)` → berth id
  string (e.g. `'B1'`) or `None`. `service_no` may be a string or int; the method
  coerces it to `str` before lookup (matching the existing `get_realtime_v3`
  pattern at `bus_engine.py:118-119`).

- [ ] **Step 1: Write the failing test**

Create `tests/test_berth.py`:

```python
import pytest

from bus_engine import BusSmartEngine


@pytest.fixture(scope="module")
def engine():
    return BusSmartEngine()


def test_get_berth_known_stop_and_service(engine):
    assert engine.get_berth('77009', '58') == 'B1'


def test_get_berth_coerces_int_service_no(engine):
    assert engine.get_berth('77009', 58) == 'B1'


def test_get_berth_unknown_service_at_known_stop(engine):
    assert engine.get_berth('77009', '999') is None


def test_get_berth_unknown_stop(engine):
    assert engine.get_berth('00000', '58') is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_berth.py -v`
Expected: FAIL with `AttributeError: 'BusSmartEngine' object has no attribute 'get_berth'`

- [ ] **Step 3: Create the berth data file**

Create `berth_map.json` at the repo root. This is real, hand-curated data for
Pasir Ris Bus Interchange (LTA `BusStopCode` `77009`) — 10 boarding berths
(B1-B10) and 5 alighting berths (A1-A5), sourced from public documentation of
the interchange's service assignments. Every `ServiceNo` listed below was
verified to actually appear in this repo's `bus_routes.json` at stop `77009`.
Berth B10 (an EW-line bridging bus to Tuas Link) has no `ServiceNo` because
bridging buses aren't part of LTA's regular DataMall services dataset — it's
listed for schematic completeness but will never match a route lookup, which
is correct (no fabricated ServiceNo):

```json
{
  "77009": {
    "nameEn": "Pasir Ris Bus Interchange",
    "nameZh": "巴西立巴士转换站",
    "boarding": [
      { "berth": "B1", "services": ["58", "58B", "88"] },
      { "berth": "B2", "services": ["12", "12e", "21"] },
      { "berth": "B3", "services": ["17", "68"] },
      { "berth": "B4", "services": ["359", "403"] },
      { "berth": "B5", "services": ["358", "46"] },
      { "berth": "B6", "services": ["354"] },
      { "berth": "B7", "services": ["3"] },
      { "berth": "B8", "services": ["5", "6"] },
      { "berth": "B9", "services": ["15", "15A", "518", "518A"] },
      { "berth": "B10", "services": [] }
    ],
    "alighting": ["A1", "A2", "A3", "A4", "A5"]
  }
}
```

- [ ] **Step 4: Implement `get_berth()`**

Edit `bus_engine.py`. Modify the `__init__` method (currently lines 11-24) to
load the berth map right after the existing `stop_to_routes` construction, and
add two new private helpers plus the public `get_berth` method right after
`_initialize_data` (currently ending at line 24, right before the `# ─── Utilities
────` comment at line 44):

```python
    def __init__(self):
        base_path = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(base_path, "bus_routes.json"), 'r', encoding='utf-8') as f:
            self.routes = json.load(f)
        with open(os.path.join(base_path, "bus_stops.json"), 'r', encoding='utf-8') as f:
            self.stops = json.load(f)

        self.stop_map = {s['BusStopCode']: s for s in self.stops if 'BusStopCode' in s}
        self.stop_to_routes = defaultdict(list)
        for r in self.routes:
            self.stop_to_routes[r['BusStopCode']].append(r)
        self._arrival_cache = {}

        self.berth_map = self._load_berth_map(base_path)
        self.berth_lookup = self._build_berth_lookup()

        self._initialize_data()
```

(Only the `self.berth_map = ...` and `self.berth_lookup = ...` lines are new;
everything else in `__init__` is unchanged.)

Add the two new private helpers and the public method after `_initialize_data`
(currently `bus_engine.py:26-42`), right before the `# ─── Utilities ──` section
comment (currently line 44):

```python
    def _load_berth_map(self, base_path):
        try:
            with open(os.path.join(base_path, "berth_map.json"), 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def _build_berth_lookup(self):
        lookup = {}
        for stop_code, info in self.berth_map.items():
            for entry in info.get('boarding', []):
                for svc in entry.get('services', []):
                    lookup[(stop_code, svc)] = entry['berth']
        return lookup

    def get_berth(self, stop_code, service_no):
        return self.berth_lookup.get((stop_code, str(service_no)))
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python -m pytest tests/test_berth.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add berth_map.json bus_engine.py tests/test_berth.py
git commit -m "feat: add curated berth data for Pasir Ris Bus Interchange"
```

---

### Task 2: Wire berth into route planning

**Files:**
- Modify: `bus_engine.py` (`_format_leg`, currently lines 156-182)
- Test: `tests/test_berth_wiring.py`

**Interfaces:**
- Consumes: `BusSmartEngine.get_berth(stop_code, service_no)` from Task 1.
- Produces: every leg dict returned by `_format_leg` (and therefore every route
  option's top-level `berth` field returned by `/api/v1/plan` — used directly by
  `opt.berth` / `opt.leg1.berth` / `opt.leg2.berth` in the frontend, wired in
  Task 4) now includes a `'berth'` key: the berth id string or `None`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_berth_wiring.py`:

```python
import pytest

from bus_engine import BusSmartEngine


@pytest.fixture(scope="module")
def engine():
    return BusSmartEngine()


def test_format_leg_includes_berth_for_a_mapped_service(engine):
    routes_at_stop = [r for r in engine.stop_to_routes['77009'] if r['ServiceNo'] == '58']
    assert routes_at_stop, 'service 58 should stop at 77009 in the fixture data'
    r_start = routes_at_stop[0]
    leg = engine._format_leg('77009', '77009', r_start, r_start)
    assert leg['berth'] == 'B1'


def test_format_leg_berth_is_none_for_an_unmapped_stop(engine):
    routes_at_stop = engine.stop_to_routes.get('01012')
    assert routes_at_stop, 'stop 01012 should have at least one route in the fixture data'
    r_start = routes_at_stop[0]
    leg = engine._format_leg('01012', '01012', r_start, r_start)
    assert leg['berth'] is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_berth_wiring.py -v`
Expected: FAIL with `KeyError: 'berth'`

- [ ] **Step 3: Wire berth into `_format_leg`**

Edit `bus_engine.py`'s `_format_leg` method (currently lines 156-182). It
currently ends with:

```python
        live = self.get_realtime_arrivals(s_code).get(str(svc))
        return {
            'service': svc,
            'from_code': s_code,
            'from_name': self.stop_map[s_code]['Description'],
            'to_code': e_code,
            'to_name': self.stop_map[e_code]['Description'],
            'stops': end_seq - start_seq,
            'dist_km': round(float(r_end['Distance']) - float(r_start['Distance']), 2),
            'polyline': polyline,
            'live': live,
        }
```

Change the returned dict to add a `'berth'` key:

```python
        live = self.get_realtime_arrivals(s_code).get(str(svc))
        return {
            'service': svc,
            'from_code': s_code,
            'from_name': self.stop_map[s_code]['Description'],
            'to_code': e_code,
            'to_name': self.stop_map[e_code]['Description'],
            'stops': end_seq - start_seq,
            'dist_km': round(float(r_end['Distance']) - float(r_start['Distance']), 2),
            'polyline': polyline,
            'live': live,
            'berth': self.get_berth(s_code, svc),
        }
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_berth_wiring.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the full backend suite**

Run: `python -m pytest -v`
Expected: all tests pass (the Kiosk Shell plan's `tests/test_static_assets.py`
plus this plan's `tests/test_berth.py` and `tests/test_berth_wiring.py`).

- [ ] **Step 6: Commit**

```bash
git add bus_engine.py tests/test_berth_wiring.py
git commit -m "feat: include berth id in route-planning leg data"
```

---

### Task 3: Crowding indicator (Green/Amber/Red)

**Files:**
- Create: `static/js/crowding.js`
- Create: `static/js/crowding.test.js`
- Modify: `index.html` (styles, `renderRouteCards`, `renderNearbyStops`, `static/js/i18n.js`)

**Interfaces:**
- Produces: `KioskCrowding.levelForLoad(load)` → `'green' | 'amber' | 'red' | 'gray'`
  (`load` is the raw Chinese string the backend already returns: `'有座'`,
  `'较挤'`, `'拥挤'`, or `null`/anything else). `KioskCrowding.labelKeyForLevel(level)`
  → an i18n key name (`'quiet' | 'moderate' | 'crowded' | 'noLiveData'`) — reuses
  the `quiet`/`moderate`/`noLiveData` keys that already exist in
  `static/js/i18n.js`, plus one new `crowded` key added in this task.

- [ ] **Step 1: Write the failing Node tests**

Create `static/js/crowding.test.js`:

```javascript
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `node --test static/js/crowding.test.js`
Expected: FAIL with "Cannot find module './crowding.js'"

- [ ] **Step 3: Create the crowding module**

Create `static/js/crowding.js`:

```javascript
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.KioskCrowding = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  const LOAD_TO_LEVEL = {
    '有座': 'green',
    '较挤': 'amber',
    '拥挤': 'red',
  };

  const LEVEL_LABEL_KEYS = {
    green: 'quiet',
    amber: 'moderate',
    red: 'crowded',
    gray: 'noLiveData',
  };

  function levelForLoad(load) {
    return LOAD_TO_LEVEL[load] || 'gray';
  }

  function labelKeyForLevel(level) {
    return LEVEL_LABEL_KEYS[level] || LEVEL_LABEL_KEYS.gray;
  }

  return { LOAD_TO_LEVEL, LEVEL_LABEL_KEYS, levelForLoad, labelKeyForLevel };
});
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `node --test static/js/crowding.test.js`
Expected: PASS (7 tests)

- [ ] **Step 5: Add the `crowded` i18n key**

Edit `static/js/i18n.js`. Add one new key to both dictionaries, right after
the existing `a11yFullscreen` key (the last key in each dictionary, currently
`static/js/i18n.js:81` for zh and `:155` for en):

In the `zh` dictionary, change:
```javascript
      a11yFullscreen: '全屏切换',
    },
```
to:
```javascript
      a11yFullscreen: '全屏切换',
      crowded: '拥挤',
    },
```

In the `en` dictionary, change:
```javascript
      a11yFullscreen: 'Toggle fullscreen',
    },
```
to:
```javascript
      a11yFullscreen: 'Toggle fullscreen',
      crowded: 'Crowded',
    },
```

- [ ] **Step 6: Add the crowd-dot CSS**

Edit `index.html`'s `<style>` block. Add right after the existing
`.route-chip.warn { background:#fff7ed; color:#9a3412; }` rule (currently line 82):

```css
    .crowd-dot { width:10px; height:10px; border-radius:999px; display:inline-block; margin-right:6px; vertical-align:middle; }
    .crowd-dot.green { background:#16a34a; }
    .crowd-dot.amber { background:#d97706; }
    .crowd-dot.red { background:#dc2626; }
    .crowd-dot.gray { background:#94a3b8; }
```

- [ ] **Step 7: Load the crowding module and wire it into route cards**

Add a new `<script src="/static/js/crowding.js"></script>` tag in `index.html`
right after the existing `<script src="/static/js/accessibility.js"></script>`
tag (currently line 377), before the inline `<script>` tag.

In `renderRouteCards` (in the inline script), find this line (currently line 963):

```javascript
            <span class="route-chip ${live ? 'good' : 'warn'}">${live ? `Load: ${live.load}` : t('noLiveData')}</span>
```

Replace it with:

```javascript
            <span class="route-chip ${live ? 'good' : 'warn'}">${(() => {
              const level = KioskCrowding.levelForLoad(live ? live.load : null);
              return `<span class="crowd-dot ${level}"></span>${t(KioskCrowding.labelKeyForLevel(level))}`;
            })()}</span>
```

- [ ] **Step 8: Wire crowding into nearby-stop cards**

In `renderNearbyStops` (in the inline script), find this line (currently line 919):

```javascript
              <span class="stop-arrival-time">${nearestLabel} · ${arrivalLine}</span>
```

Replace it with:

```javascript
              <span class="stop-arrival-time"><span class="crowd-dot ${KioskCrowding.levelForLoad(nearest ? nearest.load : null)}"></span>${nearestLabel} · ${arrivalLine}</span>
```

- [ ] **Step 9: Manually verify**

Start the server (`python -m uvicorn main:app --host 0.0.0.0 --port 8000`) and
open `http://127.0.0.1:8000`. Navigate to the Wayfinding tile. Without
`LTA_API_KEY` set, all live arrivals are empty, so every route card and nearby
stop card should show a **gray** dot with "暂无实时数据"/"No live data" (the
`noLiveData` key). This confirms the gray/no-live-data path renders without
errors. (Testing the green/amber/red paths end-to-end requires a live
`LTA_API_KEY` and a bus that happens to be reporting that load level at that
moment — not something a demo environment can force. The color mapping itself
is already covered by Node tests in Step 4.)

- [ ] **Step 10: Commit**

```bash
git add static/js/crowding.js static/js/crowding.test.js static/js/i18n.js index.html
git commit -m "feat: add Green/Amber/Red crowding indicator to route and stop cards"
```

---

### Task 4: Berth badge + schematic in the trip summary

**Files:**
- Create: `static/js/berth-schematic.js`
- Create: `static/js/berth-schematic.test.js`
- Modify: `index.html` (styles, `buildDirectTimeline`, `buildTransferTimeline`, `static/js/i18n.js`)

**Interfaces:**
- Consumes: `opt.berth` / `leg1.berth` / `leg2.berth` fields produced by Task 2's
  backend change (available on every route option `/api/v1/plan` returns).
- Produces: `KioskBerthSchematic.BOARDING_BERTHS` (array of 10 berth id strings,
  `'B1'`..`'B10'`), `KioskBerthSchematic.buildSchematicHtml(activeBerth)` → an
  HTML string rendering all 10 berths with the matching one marked `active`
  (no match if `activeBerth` isn't one of the 10, e.g. `null`).

- [ ] **Step 1: Write the failing Node tests**

Create `static/js/berth-schematic.test.js`:

```javascript
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `node --test static/js/berth-schematic.test.js`
Expected: FAIL with "Cannot find module './berth-schematic.js'"

- [ ] **Step 3: Create the berth schematic module**

Create `static/js/berth-schematic.js`:

```javascript
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.KioskBerthSchematic = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  const BOARDING_BERTHS = ['B1', 'B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B9', 'B10'];

  function buildSchematicHtml(activeBerth) {
    const cells = BOARDING_BERTHS.map((berth) => {
      const active = berth === activeBerth;
      return `<div class="berth-cell${active ? ' active' : ''}">${berth}</div>`;
    }).join('');
    return `<div class="berth-schematic">${cells}</div>`;
  }

  return { BOARDING_BERTHS, buildSchematicHtml };
});
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `node --test static/js/berth-schematic.test.js`
Expected: PASS (5 tests)

- [ ] **Step 5: Add the `berthLabel`/`berthUnavailable` i18n keys**

Edit `static/js/i18n.js`. In the `zh` dictionary, change the line added by
Task 3 (`crowded: '拥挤',`) to add two more keys after it:

```javascript
      crowded: '拥挤',
      berthLabel: '泊位',
      berthUnavailable: '暂无泊位信息',
    },
```

In the `en` dictionary, change the line added by Task 3 (`crowded: 'Crowded',`)
to add two more keys after it:

```javascript
      crowded: 'Crowded',
      berthLabel: 'Berth',
      berthUnavailable: 'No berth info',
    },
```

- [ ] **Step 6: Add the schematic CSS**

Edit `index.html`'s `<style>` block. Add right after the `.crowd-dot.gray`
rule added by Task 3:

```css
    .berth-schematic { display:grid; grid-template-columns:repeat(5, 1fr); gap:8px; max-width:360px; margin:10px 0 0; }
    .berth-cell { padding:10px 0; text-align:center; border-radius:10px; background:#f1f5f9; color:#334155; font-weight:800; font-size:13px; border:2px solid transparent; }
    .berth-cell.active { background:#0f4fd6; color:#fff; border-color:#0c3fa8; box-shadow:0 4px 12px rgba(15,79,214,.3); }
```

- [ ] **Step 7: Load the module**

Add `<script src="/static/js/berth-schematic.js"></script>` right after the
`<script src="/static/js/crowding.js"></script>` tag added by Task 3, before
the inline `<script>` tag.

- [ ] **Step 8: Wire the berth block into `buildDirectTimeline`**

In the inline script's `buildDirectTimeline` function, find the closing of the
returned template literal — the last `<div class="tl-row">` block (arrival row)
right before the closing `` </div>` `` backtick that ends the function
(currently the block starting `<div class="tl-row">` at line 1169 and the
literal's closing `` </div>` `` at line 1174):

```javascript
          <div class="tl-row">
            <span class="tl-time">${fmtTime(arriveT)}</span>
            <div class="tl-dot dest"></div>
            <span class="tl-stop">${state.destination.label || best.to_name}</span>
          </div>
        </div>`;
    }
```

Replace it with (adds a berth block right after the arrival row, still inside
the same returned template literal):

```javascript
          <div class="tl-row">
            <span class="tl-time">${fmtTime(arriveT)}</span>
            <div class="tl-dot dest"></div>
            <span class="tl-stop">${state.destination.label || best.to_name}</span>
          </div>
        </div>
        ${best.berth ? `
        <div class="mt-3">
          <span class="route-chip good">${t('berthLabel')}: ${best.berth}</span>
          ${KioskBerthSchematic.buildSchematicHtml(best.berth)}
        </div>` : ''}`;
    }
```

- [ ] **Step 9: Wire the berth block into `buildTransferTimeline`**

In the inline script's `buildTransferTimeline` function, find its closing
arrival row and template-literal end (currently the block starting
`<div class="tl-row">` at line 1238 and the literal's closing `` </div>` ``
at line 1243):

```javascript
          <div class="tl-row">
            <span class="tl-time">${fmtTime(arriveT)}</span>
            <div class="tl-dot dest"></div>
            <span class="tl-stop">${state.destination.label || leg2.to_name}</span>
          </div>
        </div>`;
    }
```

Replace it with (uses `leg1.berth` — the berth the passenger boards from at the
start of the trip; `leg2`'s boarding point is a transfer stop, not the
interchange, so it's out of scope for this curated single-interchange dataset):

```javascript
          <div class="tl-row">
            <span class="tl-time">${fmtTime(arriveT)}</span>
            <div class="tl-dot dest"></div>
            <span class="tl-stop">${state.destination.label || leg2.to_name}</span>
          </div>
        </div>
        ${leg1.berth ? `
        <div class="mt-3">
          <span class="route-chip good">${t('berthLabel')}: ${leg1.berth}</span>
          ${KioskBerthSchematic.buildSchematicHtml(leg1.berth)}
        </div>` : ''}`;
    }
```

- [ ] **Step 10: Manually verify**

Restart the server and open `http://127.0.0.1:8000`. Navigate to Wayfinding.
Since the demo's default current location (Tampines, until Task 7 changes it to
Pasir Ris) won't match the curated interchange, the trip summary should show no
berth block (`best.berth` is `null` for services not in `berth_map.json`) — this
confirms the "no data" path doesn't render a broken/empty block. This is fully
verified end-to-end once Task 7 switches the default location to Pasir Ris
Interchange, where a berth badge and 5×2 schematic grid (with one cell
highlighted in blue) should appear below the trip timeline.

- [ ] **Step 11: Commit**

```bash
git add static/js/berth-schematic.js static/js/berth-schematic.test.js static/js/i18n.js index.html
git commit -m "feat: show berth badge and schematic in the trip summary"
```

---

### Task 5: "热门直达" quick-destination buttons

**Files:**
- Create: `static/js/quick-destinations.js`
- Create: `static/js/quick-destinations.test.js`
- Modify: `index.html` (styles, markup, inline script, `static/js/i18n.js`)

**Interfaces:**
- Produces: `KioskQuickDestinations.QUICK_DESTINATIONS` — array of
  `{ id, icon, labelKey, lat, lon }`, 4 entries, all real Singapore locations
  near the curated interchange (an airport, a hospital, a mall, a community
  club — matching the spec's "附近综合医院、商场、政府机构、樟宜机场" examples).

- [ ] **Step 1: Write the failing Node tests**

Create `static/js/quick-destinations.test.js`:

```javascript
const test = require('node:test');
const assert = require('node:assert/strict');
const { QUICK_DESTINATIONS } = require('./quick-destinations.js');

test('QUICK_DESTINATIONS has 4 entries with unique ids', () => {
  assert.equal(QUICK_DESTINATIONS.length, 4);
  const ids = QUICK_DESTINATIONS.map((d) => d.id);
  assert.equal(new Set(ids).size, ids.length);
});

test('every entry has an icon, labelKey, lat, and lon', () => {
  QUICK_DESTINATIONS.forEach((dest) => {
    assert.equal(typeof dest.icon, 'string');
    assert.equal(typeof dest.labelKey, 'string');
    assert.equal(typeof dest.lat, 'number');
    assert.equal(typeof dest.lon, 'number');
  });
});

test('every coordinate is within Singapore\'s bounding box', () => {
  QUICK_DESTINATIONS.forEach((dest) => {
    assert.ok(dest.lat > 1.0 && dest.lat < 1.6, `${dest.id} latitude out of range: ${dest.lat}`);
    assert.ok(dest.lon > 103.5 && dest.lon < 104.1, `${dest.id} longitude out of range: ${dest.lon}`);
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `node --test static/js/quick-destinations.test.js`
Expected: FAIL with "Cannot find module './quick-destinations.js'"

- [ ] **Step 3: Create the quick-destinations module**

Create `static/js/quick-destinations.js`:

```javascript
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.KioskQuickDestinations = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  const QUICK_DESTINATIONS = [
    { id: 'changi-airport', icon: '✈️', labelKey: 'quickDestChangi', lat: 1.3575, lon: 103.9885 },
    { id: 'changi-hospital', icon: '🏥', labelKey: 'quickDestHospital', lat: 1.3405, lon: 103.9493 },
    { id: 'white-sands-mall', icon: '🛍️', labelKey: 'quickDestMall', lat: 1.3721, lon: 103.9493 },
    { id: 'elias-cc', icon: '🏛️', labelKey: 'quickDestCC', lat: 1.3806, lon: 103.9427 },
  ];

  return { QUICK_DESTINATIONS };
});
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `node --test static/js/quick-destinations.test.js`
Expected: PASS (3 tests)

- [ ] **Step 5: Add the quick-destination i18n keys**

Edit `static/js/i18n.js`. In the `zh` dictionary, change the line added by
Task 4 (`berthUnavailable: '暂无泊位信息',`) to add five more keys after it:

```javascript
      berthUnavailable: '暂无泊位信息',
      quickDestHeading: '热门直达',
      quickDestChangi: '樟宜机场 T2',
      quickDestHospital: '樟宜综合医院',
      quickDestMall: '白沙购物广场',
      quickDestCC: '巴西立民众俱乐部',
    },
```

In the `en` dictionary, change the line added by Task 4
(`berthUnavailable: 'No berth info',`) to add five more keys after it:

```javascript
      berthUnavailable: 'No berth info',
      quickDestHeading: 'Popular Destinations',
      quickDestChangi: 'Changi Airport T2',
      quickDestHospital: 'Changi General Hospital',
      quickDestMall: 'White Sands Mall',
      quickDestCC: 'Elias Community Club',
    },
```

- [ ] **Step 6: Add the quick-destination row markup**

In `index.html`, inside the `.hero-chat` block, find the closing of the
chat-pill row (currently lines 276-279):

```html
                <div class="flex gap-3 flex-wrap">
                  <div id="pill-where" class="chat-pill primary">Where to go?｜您要去哪里?</div>
                  <div id="pill-arrival" class="chat-pill secondary">Which bus arrives when?｜哪辆巴士什么时候到?</div>
                </div>
```

Add a new row right after it, before the `<div class="flex items-center gap-3">`
that holds the voice bars:

```html
                <div class="flex gap-3 flex-wrap">
                  <div id="pill-where" class="chat-pill primary">Where to go?｜您要去哪里?</div>
                  <div id="pill-arrival" class="chat-pill secondary">Which bus arrives when?｜哪辆巴士什么时候到?</div>
                </div>
                <div id="quick-dest-row" class="flex gap-2 flex-wrap"></div>
```

- [ ] **Step 7: Load the module and render the quick-destination buttons**

Add `<script src="/static/js/quick-destinations.js"></script>` right after the
`<script src="/static/js/berth-schematic.js"></script>` tag added by Task 4,
before the inline `<script>` tag.

In the inline script, add a render function right after `renderRouteCards`
(currently ending at line 978, right before the `const stopIcon = L.divIcon(...)`
block):

```javascript
    function renderQuickDestinations() {
      const row = document.getElementById('quick-dest-row');
      row.innerHTML = '';
      KioskQuickDestinations.QUICK_DESTINATIONS.forEach((dest) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'chat-pill secondary';
        btn.textContent = `${dest.icon} ${t(dest.labelKey)}`;
        btn.addEventListener('click', async () => {
          await setDestinationLocation({ lat: dest.lat, lon: dest.lon, label: t(dest.labelKey) });
          await planJourney();
        });
        row.appendChild(btn);
      });
    }
```

- [ ] **Step 8: Call it from `setLanguage()` and at init**

In `setLanguage()`, right after the `renderRouteCards(state.routeOptions);`
line at the end of the function (currently line 689), add:

```javascript
      renderQuickDestinations();
```

In the init sequence at the bottom of the script, right after
`setLanguage('zh');` (currently line 1454), the call to `renderQuickDestinations()`
already happens as part of `setLanguage('zh')` calling it internally (from the
line just added above) — no separate init call is needed.

- [ ] **Step 9: Manually verify**

Restart the server and open `http://127.0.0.1:8000`. Navigate to Wayfinding.
Below the "Where to go?" / "Which bus arrives when?" pills, 4 new pill-style
buttons should appear: ✈️ Changi Airport T2, 🏥 Changi General Hospital, 🛍️
White Sands Mall, 🏛️ Elias Community Club (in Chinese when the UI language is
中文). Click one — the destination marker moves, the map flies to it, and route
planning re-runs (toast + trip summary update), exactly like typing a
destination by voice. Switch language to EN and confirm all 4 button labels
update.

- [ ] **Step 10: Commit**

```bash
git add static/js/quick-destinations.js static/js/quick-destinations.test.js static/js/i18n.js index.html
git commit -m "feat: add popular quick-destination buttons to Wayfinding"
```

---

### Task 6: Search box accepts bus stop codes/names, not just postcodes

**Files:**
- Modify: `index.html` (inline script only)

**Interfaces:**
- Consumes: nothing new.
- Produces: `searchStopAsLocation(query)` (async, extracted from the existing
  voice-search fallback logic) — later code should call this instead of
  duplicating the bus-stop-search fetch.

- [ ] **Step 1: Extract the shared stop-search helper**

In the inline script, find `resolveLocationFromText` (currently lines
724-763). It currently has this stop-search block inline:

```javascript
      try {
        const stopRes = await fetch(`${apiBase}/api/v1/search-stops?q=${encodeURIComponent(query)}&limit=1`);
        const stopData = await stopRes.json();
        const firstStop = stopData?.results?.[0];
        if (firstStop?.latitude != null && firstStop?.longitude != null) {
          return {
            lat: Number(firstStop.latitude),
            lon: Number(firstStop.longitude),
            label: firstStop.name || firstStop.code || query,
          };
        }
      } catch (err) {
        console.warn('stop search failed', err);
      }

      return null;
    }
```

Replace the whole `resolveLocationFromText` function with this version, which
extracts the stop-search block into a standalone `searchStopAsLocation`
function placed right before it, and has `resolveLocationFromText` call it:

```javascript
    async function searchStopAsLocation(query) {
      try {
        const stopRes = await fetch(`${apiBase}/api/v1/search-stops?q=${encodeURIComponent(query)}&limit=1`);
        const stopData = await stopRes.json();
        const firstStop = stopData?.results?.[0];
        if (firstStop?.latitude != null && firstStop?.longitude != null) {
          return {
            lat: Number(firstStop.latitude),
            lon: Number(firstStop.longitude),
            label: firstStop.name || firstStop.code || query,
          };
        }
      } catch (err) {
        console.warn('stop search failed', err);
      }
      return null;
    }

    async function resolveLocationFromText(text) {
      const query = normalizeVoiceQuery(text);
      if (!query) return null;

      if (/机场|t2|changi|airport/i.test(query)) {
        return demoDestination;
      }

      try {
        const geoRes = await fetch(`https://www.onemap.gov.sg/api/common/elastic/search?searchVal=${encodeURIComponent(query)}&returnGeom=Y&getAddrDetails=Y&pageNum=1`);
        const geoData = await geoRes.json();
        const geoResult = geoData?.results?.[0];
        if (geoResult?.LATITUDE && geoResult?.LONGITUDE) {
          return {
            lat: Number(geoResult.LATITUDE),
            lon: Number(geoResult.LONGITUDE),
            label: geoResult.ADDRESS || geoResult.SEARCHVAL || query,
          };
        }
      } catch (err) {
        console.warn('geocode failed', err);
      }

      return searchStopAsLocation(query);
    }
```

- [ ] **Step 2: Use the shared helper as a fallback for the postcode/search box**

Find `updateCurrentLocationFromPostcode` (currently lines 1086-1111):

```javascript
    async function updateCurrentLocationFromPostcode(postcode) {
      try {
        setAssistantStatus(stateLang.ui === 'zh' ? `正在搜索邮编 ${postcode}…` : `Searching postcode ${postcode}…`);
        const location = await geocodePostcode(postcode);
        if (!location) {
          showToast(t('postcodeNotFound'));
          setAssistantStatus(stateLang.ui === 'zh' ? '未找到该邮编的位置。' : 'No location found for that postcode.');
          return;
        }
```

Change the middle section to add the stop-code/name fallback before giving up:

```javascript
    async function updateCurrentLocationFromPostcode(postcode) {
      try {
        setAssistantStatus(stateLang.ui === 'zh' ? `正在搜索邮编 ${postcode}…` : `Searching postcode ${postcode}…`);
        let location = await geocodePostcode(postcode);
        if (!location) {
          location = await searchStopAsLocation(postcode);
        }
        if (!location) {
          showToast(t('postcodeNotFound'));
          setAssistantStatus(stateLang.ui === 'zh' ? '未找到该邮编的位置。' : 'No location found for that postcode.');
          return;
        }
```

The rest of the function (from `state.current = location;` onward) is
unchanged.

- [ ] **Step 3: Manually verify**

Restart the server and open `http://127.0.0.1:8000`. Navigate to Wayfinding.
Type a real bus stop code that exists in `bus_stops.json` (e.g. `77009`, the
curated interchange) into the search box and press Enter — the map should fly
to that stop (OneMap's geocoder won't resolve a 5-digit bus stop code to an
address, so this only works via the new `searchStopAsLocation` fallback,
proving the fallback fires). Then try a real postcode (e.g. `018956`) and
confirm it still resolves via OneMap as before (no regression to the existing
path).

- [ ] **Step 4: Commit**

```bash
git add index.html
git commit -m "feat: search box falls back to bus stop code/name lookup"
```

---

### Task 7: QR-code takeaway + demo default location + full regression

**Files:**
- Create: `static/js/qr-payload.js`
- Create: `static/js/qr-payload.test.js`
- Modify: `index.html` (head script tag, styles, markup, inline script, `static/js/i18n.js`)

**Interfaces:**
- Consumes: `qrcode` global (from the new CDN script), `best.berth` / `leg1.berth`
  from Task 4's wiring.
- Produces: `KioskQrPayload.buildDirectTripPayload(trip)` → a plain-text string
  summarizing a trip (`trip` is `{ service, fromName, toName, stops, berth }`,
  `berth` optional).

- [ ] **Step 1: Write the failing Node tests**

Create `static/js/qr-payload.test.js`:

```javascript
const test = require('node:test');
const assert = require('node:assert/strict');
const { buildDirectTripPayload } = require('./qr-payload.js');

test('buildDirectTripPayload includes service, stops, and berth', () => {
  const text = buildDirectTripPayload({
    service: '58',
    fromName: 'Pasir Ris Int',
    toName: 'Changi Airport',
    stops: 6,
    berth: 'B1',
  });
  assert.ok(text.includes('58'));
  assert.ok(text.includes('Pasir Ris Int'));
  assert.ok(text.includes('Changi Airport'));
  assert.ok(text.includes('6'));
  assert.ok(text.includes('B1'));
});

test('buildDirectTripPayload omits the berth line when berth is absent', () => {
  const text = buildDirectTripPayload({
    service: '5',
    fromName: 'Some Stop',
    toName: 'Other Stop',
    stops: 3,
  });
  assert.ok(!text.toLowerCase().includes('berth'));
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `node --test static/js/qr-payload.test.js`
Expected: FAIL with "Cannot find module './qr-payload.js'"

- [ ] **Step 3: Create the QR payload module**

Create `static/js/qr-payload.js`:

```javascript
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.KioskQrPayload = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  function buildDirectTripPayload(trip) {
    const lines = [
      `Bus ${trip.service}`,
      `${trip.fromName} -> ${trip.toName}`,
      `${trip.stops} stops`,
    ];
    if (trip.berth) {
      lines.push(`Berth ${trip.berth}`);
    }
    return lines.join('\n');
  }

  return { buildDirectTripPayload };
});
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `node --test static/js/qr-payload.test.js`
Expected: PASS (2 tests)

- [ ] **Step 5: Add the QR CDN script**

Edit `index.html`'s `<head>`. Add the QR library right after the existing
Leaflet `<script>` tag (currently line 11), before the Tailwind CDN tag:

```html
  <script src="https://cdn.jsdelivr.net/npm/qrcode-generator@1.4.4/qrcode.js"></script>
```

- [ ] **Step 6: Add the `qrTakeaway`/`qrHint` i18n keys**

Edit `static/js/i18n.js`. In the `zh` dictionary, change the line added by
Task 5 (`quickDestCC: '巴西立民众俱乐部',`) to add two more keys after it:

```javascript
      quickDestCC: '巴西立民众俱乐部',
      qrTakeaway: '扫码带走路线',
      qrHint: '用手机扫描保存路线信息',
    },
```

In the `en` dictionary, change the line added by Task 5
(`quickDestCC: 'Elias Community Club',`) to add two more keys after it:

```javascript
      quickDestCC: 'Elias Community Club',
      qrTakeaway: 'Scan to take route',
      qrHint: 'Scan with your phone to save this trip',
    },
```

- [ ] **Step 7: Add the QR container CSS**

Edit `index.html`'s `<style>` block. Add right after the `.berth-cell.active`
rule added by Task 4:

```css
    .trip-qr-block { margin-top:12px; padding-top:12px; border-top:1px solid var(--border); display:flex; align-items:center; gap:12px; }
    .trip-qr-block svg { width:72px; height:72px; flex-shrink:0; }
    .trip-qr-label { font-size:13px; font-weight:700; color:var(--muted); }
```

- [ ] **Step 8: Load the module and add the QR render helper**

Add `<script src="/static/js/qr-payload.js"></script>` right after the
`<script src="/static/js/quick-destinations.js"></script>` tag added by
Task 5, before the inline `<script>` tag.

In the inline script, add a render helper right after `renderQuickDestinations`
(added by Task 5):

```javascript
    function renderTripQr(text) {
      const container = document.getElementById('trip-qr-code');
      if (!container) return;
      container.innerHTML = '';
      const qr = qrcode(0, 'L');
      qr.addData(text);
      qr.make();
      container.innerHTML = qr.createSvgTag(3);
    }
```

- [ ] **Step 9: Add the QR block to `buildDirectTimeline` and call `renderTripQr`**

In `buildDirectTimeline`, find the berth block added by Task 4 (at the end of
the returned template literal):

```javascript
        ${best.berth ? `
        <div class="mt-3">
          <span class="route-chip good">${t('berthLabel')}: ${best.berth}</span>
          ${KioskBerthSchematic.buildSchematicHtml(best.berth)}
        </div>` : ''}`;
    }
```

Replace it with (adds a QR container after the berth block, still inside the
same template literal):

```javascript
        ${best.berth ? `
        <div class="mt-3">
          <span class="route-chip good">${t('berthLabel')}: ${best.berth}</span>
          ${KioskBerthSchematic.buildSchematicHtml(best.berth)}
        </div>` : ''}
        <div class="trip-qr-block">
          <div id="trip-qr-code"></div>
          <div>
            <div class="trip-qr-label">${t('qrTakeaway')}</div>
            <div class="small-label">${t('qrHint')}</div>
          </div>
        </div>`;
    }
```

Then, in `planJourney`'s direct-mode branch, find where `buildDirectTimeline`
is called and rendered (currently):

```javascript
        // Direct mode
        const best = data.best || data.options?.[0];
        summary.innerHTML = buildDirectTimeline(best, isZh);
```

Change it to also render the QR code right after:

```javascript
        // Direct mode
        const best = data.best || data.options?.[0];
        summary.innerHTML = buildDirectTimeline(best, isZh);
        if (best) {
          renderTripQr(KioskQrPayload.buildDirectTripPayload({
            service: best.service,
            fromName: best.from_name,
            toName: best.to_name,
            stops: best.stops,
            berth: best.berth,
          }));
        }
```

- [ ] **Step 10: Add the QR block to `buildTransferTimeline` and call `renderTripQr`**

In `buildTransferTimeline`, find the berth block added by Task 4:

```javascript
        ${leg1.berth ? `
        <div class="mt-3">
          <span class="route-chip good">${t('berthLabel')}: ${leg1.berth}</span>
          ${KioskBerthSchematic.buildSchematicHtml(leg1.berth)}
        </div>` : ''}`;
    }
```

Replace it with:

```javascript
        ${leg1.berth ? `
        <div class="mt-3">
          <span class="route-chip good">${t('berthLabel')}: ${leg1.berth}</span>
          ${KioskBerthSchematic.buildSchematicHtml(leg1.berth)}
        </div>` : ''}
        <div class="trip-qr-block">
          <div id="trip-qr-code"></div>
          <div>
            <div class="trip-qr-label">${t('qrTakeaway')}</div>
            <div class="small-label">${t('qrHint')}</div>
          </div>
        </div>`;
    }
```

Then, in `planJourney`'s transfer-mode branch, find:

```javascript
        // Transfer mode
        if (data.mode === 'transfer') {
          const firstOpt = data.options?.[0];
          const leg1 = firstOpt?.leg1;
          const leg2 = firstOpt?.leg2;
          summary.innerHTML = buildTransferTimeline(leg1, leg2, isZh);
```

Change it to also render the QR code right after:

```javascript
        // Transfer mode
        if (data.mode === 'transfer') {
          const firstOpt = data.options?.[0];
          const leg1 = firstOpt?.leg1;
          const leg2 = firstOpt?.leg2;
          summary.innerHTML = buildTransferTimeline(leg1, leg2, isZh);
          if (leg1 && leg2) {
            renderTripQr(KioskQrPayload.buildDirectTripPayload({
              service: `${leg1.service} -> ${leg2.service}`,
              fromName: leg1.from_name,
              toName: leg2.to_name,
              stops: leg1.stops + leg2.stops,
              berth: leg1.berth,
            }));
          }
```

- [ ] **Step 11: Switch the demo default location to the curated interchange**

In the inline script, find the `defaultLocation` constant (currently line 380):

```javascript
    const defaultLocation = { lat: 1.3542, lon: 103.9436, label: 'Tampines Bus Interchange'};
```

Change it to:

```javascript
    const defaultLocation = { lat: 1.373696, lon: 103.94845, label: 'Pasir Ris Bus Interchange'};
```

- [ ] **Step 12: Run the full automated test suite**

Run:

```bash
python -m pytest -v
node --test "static/js/*.test.js"
```

Expected: all backend and JS tests pass (this plan added `tests/test_berth.py`,
`tests/test_berth_wiring.py`, and 3 new `static/js/*.test.js` files, on top of
everything the Kiosk Shell plan already added).

- [ ] **Step 13: Full manual regression pass**

Restart the server and open `http://127.0.0.1:8000`. Navigate to Wayfinding.
Verify:

1. The map opens centered on Pasir Ris Bus Interchange (not Tampines).
2. The 4 quick-destination buttons and the search box both still work (Task 5,
   Task 6).
3. Type `77009` into the search box (or click a nearby-stop card for the
   interchange) as the current location, then set a destination reachable by
   one of the mapped services (any of: 58, 58B, 88, 12, 12e, 21, 17, 68, 359,
   403, 358, 46, 354, 3, 5, 6, 15, 15A, 518, 518A) — for example, search a stop
   a few stops down one of those routes. The route card and trip-summary panel
   should show: a colored crowding dot (Task 3), a berth badge with the 5×2
   schematic grid highlighting the correct berth (Task 4), and a QR code with
   "扫码带走路线"/"Scan to take route" (this task) that a phone's camera app can
   actually decode into readable text (open the SVG in a browser tab and scan
   it with a phone, or use any online QR decoder, to confirm it's not garbled).
4. Plan a trip from a stop that is NOT the curated interchange — confirm no
   berth block or broken markup appears (graceful "no berth data" case), and a
   QR code still renders (every direct/transfer result gets one, berth or not).
5. Switch to EN and repeat step 3's visible text checks — every new string
   (crowding label, berth label, quick-destination labels, QR labels) is in
   English with no leftover Chinese text.
6. Confirm the rest of the Wayfinding screen is unaffected: nearby-stop list,
   voice input, news ticker, weather widget, and navigation back to the Kiosk
   Shell's home screen all still work exactly as before this plan.

- [ ] **Step 14: Commit**

```bash
git add static/js/qr-payload.js static/js/qr-payload.test.js static/js/i18n.js index.html
git commit -m "feat: add QR-code trip takeaway and switch demo location to the curated interchange"
```
