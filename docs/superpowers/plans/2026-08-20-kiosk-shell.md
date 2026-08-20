# Kiosk Shell (Home Screen + Accessibility) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing single-purpose Wayfinding page into a kiosk shell with a
4-tile home screen (Wayfinding / Lost & Found / Feedback / Explore Nearby), a bilingual
EN/中文 toggle that covers every screen, and accessibility controls (font scale,
read-aloud, fullscreen) — without regressing any existing Wayfinding behavior.

**Architecture:** `index.html` stays a single static page served by FastAPI, but gains
three small, dependency-free JS modules under `static/js/` (i18n dictionary, view
router, accessibility helpers) that are unit-tested with Node's built-in test runner
and then wired into the existing inline `<script>` for DOM behavior. A `data-view`
attribute on each top-level screen element drives simple show/hide navigation; no
frontend framework or build step is introduced.

**Tech Stack:** FastAPI (existing), vanilla JS + Tailwind CDN + Leaflet CDN (existing),
Node.js 18+ built-in test runner for the new JS modules (no new npm dependency),
pytest + httpx for one new backend test (first backend test in this repo).

**Spec:** [docs/superpowers/specs/2026-08-20-goahead-kiosk-system.md](../specs/2026-08-20-goahead-kiosk-system.md)
— this plan implements the "双语与无障碍切换" and "首页 4 大核心入口" sections only.
The four module screens' real functionality (Lost & Found, Feedback, Nearby POI) are
separate follow-up plans; this plan only builds their navigation stubs.

## Global Constraints

- Node.js 18+ is required to run the new JS tests (`node --test`) — no npm/package.json
  is introduced.
- `pytest` and `httpx` are added to `requirements.txt` as this repo's first backend
  test dependencies.
- No new frontend build tooling: Tailwind and Leaflet remain CDN `<script>` tags;
  `static/js/*.js` files are plain browser scripts loaded via `<script src>`.
- Every new user-facing string must have both a `zh` and an `en` entry in
  `static/js/i18n.js` — bilingual parity is a hard requirement from the spec.
- Existing Wayfinding behavior (postcode search, nearby stops, route planning, voice
  input, TTS, news ticker, weather widget) must work identically after this plan —
  it is being wrapped into a `data-view="wayfinding"` screen, not rewritten.
- Font scaling uses the CSS `zoom` property (Chromium/Safari only, not Firefox) —
  acceptable because kiosk hardware runs a Chromium-based browser in kiosk mode.

---

### Task 1: Static asset serving + i18n module

**Files:**
- Create: `conftest.py` (repo root)
- Create: `tests/test_static_assets.py`
- Create: `static/js/i18n.js`
- Create: `static/js/i18n.test.js`
- Modify: `main.py:1-20`
- Modify: `requirements.txt`

**Interfaces:**
- Produces: `KioskI18n.DICTIONARIES` (object with `zh`/`en` keys, each a dictionary of
  string or function-valued entries), `KioskI18n.translate(lang, key, ...args)` →
  string. In the browser this is exposed as the global `KioskI18n`; in Node it is the
  `module.exports` of `static/js/i18n.js`.

- [ ] **Step 1: Write the failing backend test for static file serving**

Create `tests/test_static_assets.py`:

```python
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_serves_i18n_js_from_static():
    response = client.get("/static/js/i18n.js")
    assert response.status_code == 200
    assert "translate" in response.text
```

Create an empty `conftest.py` at the repo root (its presence makes pytest add the
repo root to `sys.path`, so `from main import app` resolves regardless of where
`pytest` is invoked from):

```python
```

(empty file)

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_static_assets.py -v`
Expected: FAIL with a 404 (no `/static` mount and no file yet), or a collection
error if `pytest`/`httpx` aren't installed yet — install them first:

```bash
pip install pytest httpx
```

Then re-run and confirm the 404 failure specifically (not an import error).

- [ ] **Step 3: Add pytest and httpx to requirements.txt**

Edit `requirements.txt` to add two lines:

```text
fastapi
uvicorn
gunicorn
requests
pydantic
python-multipart
pytest
httpx
```

- [ ] **Step 4: Create the i18n module**

Create `static/js/i18n.js`. This migrates the existing inline dictionary from
`index.html` (all keys used today) and adds the new keys this plan's home screen,
stub screens, and accessibility toolbar need:

```javascript
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.KioskI18n = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  const DICTIONARIES = {
    zh: {
      brand: 'Bus Concierge',
      schedules: '时刻表',
      routes: '路线',
      liveMap: '实时地图',
      accessibility: '无障碍',
      concierge: '礼宾助手',
      online: '在线',
      startJourney: '开始行程',
      home: '首页',
      nearbyStops: '附近站点',
      savedRoutes: '收藏路线',
      aiAssistant: 'AI 助手',
      whereToGo: '您要去哪里？',
      whichBus: '哪辆巴士什么时候到？',
      currentLocation: '当前地点',
      currentLocationSubtitle: '当前位置',
      searchPlaceholder: '输入邮编或地点 | Enter postcode or place',
      ready: '准备好后可语音输入或点击站点。',
      listening: '正在聆听… 说出目的地',
      searching: '正在搜索附近站点…',
      planning: '正在规划最佳巴士方案…',
      noMatch: '未找到匹配站点',
      noRoute: '未找到直达方案',
      noNearby: '未找到附近站点。',
      routeDetails: '线路详情',
      noRouteDetails: '线路详情不可用',
      postcodeNotFound: '邮编未找到',
      loadRoute: (svc) => `已加载线路 ${svc}`,
      updatedLocation: (label) => `当前位置已更新：${label}`,
      bestOption: (service) => `最佳方案：${service}`,
      heard: (text) => `识别到：${text}`,
      welcomeSpeak: (service, mins) => `推荐乘坐 ${service} 路，${mins} 分钟后到达`,
      routeCoords: '路线坐标',
      startCoords: '起点坐标',
      endCoords: '终点坐标',
      suggestedRoute: '建议路线',
      services: '服务',
      walkMinutes: (m) => `步行 ${m} 分钟`,
      arrivingSoon: '即将到达',
      noLiveData: '暂无实时数据',
      terminal: '终点站',
      details: '详情',
      quiet: '舒适',
      moderate: '适中',
      tryAnother: '请尝试其他目的地或站点。',
      foundNearby: (n) => `找到 ${n} 个附近站点。`,
      currentUpdated: (label) => `当前位置已更新：${label}`,
      focusedOn: (name) => `已聚焦到 ${name}`,
      routeFailed: '路线规划失败。',
      planFailed: '规划失败',
      voiceError: '语音输入错误',
      loadingRouteDetails: '线路详情不可用',
      nearLabel: (label) => `附近：${label}`,
      homeHeading: '欢迎使用 Go-Ahead 智能站亭',
      homeSubheading: '点击图标开始 | Tap a tile to get started',
      homeTileWayfindingTitle: '路线指引',
      homeTileWayfindingSubtitle: '查询乘车方案与候车泊位',
      homeTileLostFoundTitle: '失物招领',
      homeTileLostFoundSubtitle: '登记报失或查询招领物品',
      homeTileFeedbackTitle: '意见反馈',
      homeTileFeedbackSubtitle: '评价服务或提交事件报告',
      homeTileNearbyTitle: '周边探索',
      homeTileNearbySubtitle: '商场、洗手间、诊所等周边设施',
      backToHome: '返回首页',
      comingSoonLostFoundTitle: '失物招领',
      comingSoonFeedbackTitle: '意见反馈',
      comingSoonNearbyTitle: '周边探索',
      comingSoonBody: '此功能即将上线，敬请期待。',
      a11yFontIncrease: '放大字体',
      a11yFontDecrease: '缩小字体',
      a11yReadAloud: '朗读开关',
      a11yFullscreen: '全屏切换',
    },
    en: {
      brand: 'Bus Concierge',
      schedules: 'Schedules',
      routes: 'Routes',
      liveMap: 'Live Map',
      accessibility: 'Accessibility',
      concierge: 'Concierge',
      online: 'Online',
      startJourney: 'Start Journey',
      home: 'Home',
      nearbyStops: 'Nearby Stops',
      savedRoutes: 'Saved Routes',
      aiAssistant: 'AI Assistant',
      whereToGo: 'Where to go?',
      whichBus: 'Which bus arrives when?',
      currentLocation: 'Current Location',
      currentLocationSubtitle: '当前位置',
      searchPlaceholder: 'Enter postcode or place | 输入邮编或地点',
      ready: 'Ready to search by voice or tap a stop.',
      listening: 'Listening… say your destination',
      searching: 'Searching nearby stops…',
      planning: 'Planning the best bus options…',
      noMatch: 'No matching stops',
      noRoute: 'No direct bus found',
      noNearby: 'No nearby stops found.',
      routeDetails: 'Route details',
      noRouteDetails: 'Route details unavailable',
      postcodeNotFound: 'Postcode not found',
      loadRoute: (svc) => `Loaded route ${svc}`,
      updatedLocation: (label) => `Current location updated: ${label}`,
      bestOption: (service) => `Best option: ${service}`,
      heard: (text) => `Heard: ${text}`,
      welcomeSpeak: (service, mins) => `Recommended bus ${service}, arriving in about ${mins} minutes`,
      routeCoords: 'Route coordinates',
      startCoords: 'Start coordinates',
      endCoords: 'End coordinates',
      suggestedRoute: 'Suggested route',
      services: 'Services',
      walkMinutes: (m) => `Walk ${m} min`,
      arrivingSoon: 'Arriving soon',
      noLiveData: 'No live data',
      terminal: 'Terminal',
      details: 'Details',
      quiet: 'Comfortable',
      moderate: 'Moderate',
      tryAnother: 'Try another destination or stop.',
      foundNearby: (n) => `Found ${n} nearby stops.`,
      currentUpdated: (label) => `Current location updated: ${label}`,
      focusedOn: (name) => `Focused on ${name}`,
      routeFailed: 'Route planning failed.',
      planFailed: 'Plan failed',
      voiceError: 'Voice input error',
      loadingRouteDetails: 'Route details unavailable',
      nearLabel: (label) => `Near: ${label}`,
      homeHeading: 'Welcome to the Go-Ahead Smart Kiosk',
      homeSubheading: 'Tap a tile to get started | 点击图标开始',
      homeTileWayfindingTitle: 'Wayfinding',
      homeTileWayfindingSubtitle: 'Find your bus and berth number',
      homeTileLostFoundTitle: 'Lost & Found',
      homeTileLostFoundSubtitle: 'Report a loss or search claimed items',
      homeTileFeedbackTitle: 'Feedback',
      homeTileFeedbackSubtitle: 'Rate your trip or report an incident',
      homeTileNearbyTitle: 'Explore Nearby',
      homeTileNearbySubtitle: 'Malls, restrooms, clinics and more',
      backToHome: 'Back to Home',
      comingSoonLostFoundTitle: 'Lost & Found',
      comingSoonFeedbackTitle: 'Feedback',
      comingSoonNearbyTitle: 'Explore Nearby',
      comingSoonBody: 'This feature is coming soon.',
      a11yFontIncrease: 'Increase text size',
      a11yFontDecrease: 'Decrease text size',
      a11yReadAloud: 'Toggle read aloud',
      a11yFullscreen: 'Toggle fullscreen',
    },
  };

  function translate(lang, key, ...args) {
    const dict = DICTIONARIES[lang] || DICTIONARIES.zh;
    const value = key in dict ? dict[key] : DICTIONARIES.zh[key];
    if (value === undefined) return key;
    return typeof value === 'function' ? value(...args) : value;
  }

  return { DICTIONARIES, translate };
});
```

- [ ] **Step 5: Mount the static directory in FastAPI**

Edit `main.py`. Add the import and mount right after `BASE_DIR` is defined:

```python
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from bus_engine import BusSmartEngine

app = FastAPI()

# 允许跨域，方便本地 index.html 调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = BusSmartEngine()
BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
```

(Only two lines are new: the `StaticFiles` import and the `app.mount(...)` call.)

- [ ] **Step 6: Run the backend test to verify it passes**

Run: `pytest tests/test_static_assets.py -v`
Expected: PASS

- [ ] **Step 7: Write the Node tests for the i18n module**

Create `static/js/i18n.test.js`:

```javascript
const test = require('node:test');
const assert = require('node:assert/strict');
const { translate, DICTIONARIES } = require('./i18n.js');

test('translate returns the zh string for a static key', () => {
  assert.equal(translate('zh', 'homeTileWayfindingTitle'), '路线指引');
});

test('translate returns the en string for a static key', () => {
  assert.equal(translate('en', 'homeTileWayfindingTitle'), 'Wayfinding');
});

test('translate calls a function-valued key with the given args', () => {
  assert.equal(translate('zh', 'loadRoute', '118'), '已加载线路 118');
});

test('translate falls back to the key itself when missing from both dictionaries', () => {
  assert.equal(translate('zh', 'thisKeyDoesNotExist'), 'thisKeyDoesNotExist');
});

test('translate falls back to zh dictionary when the language is unknown', () => {
  assert.equal(translate('fr', 'homeTileWayfindingTitle'), DICTIONARIES.zh.homeTileWayfindingTitle);
});
```

- [ ] **Step 8: Run the Node tests to verify they pass**

Run: `node --test static/js/i18n.test.js`
Expected: PASS (5 tests)

- [ ] **Step 9: Commit**

```bash
git add conftest.py tests/test_static_assets.py static/js/i18n.js static/js/i18n.test.js main.py requirements.txt
git commit -m "feat: add static asset serving and i18n module"
```

---

### Task 2: View router module

**Files:**
- Create: `static/js/view-router.js`
- Create: `static/js/view-router.test.js`

**Interfaces:**
- Consumes: nothing (self-contained).
- Produces: `KioskViewRouter.TILES` (array of `{ id, icon, titleKey, subtitleKey }`,
  one entry per home-screen tile, in spec order), `KioskViewRouter.VALID_VIEWS`
  (array of view ids: `'home'` plus each tile's `id`), `KioskViewRouter.resolveView(requestedView)`
  → a valid view id, falling back to `'home'` for anything not in `VALID_VIEWS`.
  Browser global: `KioskViewRouter`. Node: `module.exports` of `static/js/view-router.js`.

- [ ] **Step 1: Write the failing Node tests**

Create `static/js/view-router.test.js`:

```javascript
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `node --test static/js/view-router.test.js`
Expected: FAIL with "Cannot find module './view-router.js'"

- [ ] **Step 3: Create the view router module**

Create `static/js/view-router.js`:

```javascript
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.KioskViewRouter = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  const TILES = [
    {
      id: 'wayfinding',
      icon: '🧭',
      titleKey: 'homeTileWayfindingTitle',
      subtitleKey: 'homeTileWayfindingSubtitle',
    },
    {
      id: 'lost-found',
      icon: '🎒',
      titleKey: 'homeTileLostFoundTitle',
      subtitleKey: 'homeTileLostFoundSubtitle',
    },
    {
      id: 'feedback',
      icon: '💬',
      titleKey: 'homeTileFeedbackTitle',
      subtitleKey: 'homeTileFeedbackSubtitle',
    },
    {
      id: 'nearby',
      icon: '📍',
      titleKey: 'homeTileNearbyTitle',
      subtitleKey: 'homeTileNearbySubtitle',
    },
  ];

  const VALID_VIEWS = ['home', ...TILES.map((tile) => tile.id)];

  function resolveView(requestedView) {
    return VALID_VIEWS.includes(requestedView) ? requestedView : 'home';
  }

  return { TILES, VALID_VIEWS, resolveView };
});
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `node --test static/js/view-router.test.js`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add static/js/view-router.js static/js/view-router.test.js
git commit -m "feat: add view router module for kiosk home screen navigation"
```

---

### Task 3: Accessibility module (font scale)

**Files:**
- Create: `static/js/accessibility.js`
- Create: `static/js/accessibility.test.js`

**Interfaces:**
- Consumes: nothing (self-contained).
- Produces: `KioskAccessibility.FONT_SCALE_MIN` (`0.85`), `FONT_SCALE_MAX` (`1.6`),
  `FONT_SCALE_STEP` (`0.15`), `FONT_SCALE_DEFAULT` (`1`), `clampFontScale(scale)` →
  number clamped to `[FONT_SCALE_MIN, FONT_SCALE_MAX]` rounded to 2 decimals,
  `nextFontScale(current, direction)` where `direction` is `'increase'` or
  `'decrease'` → clamped next scale. Browser global: `KioskAccessibility`. Node:
  `module.exports` of `static/js/accessibility.js`.

- [ ] **Step 1: Write the failing Node tests**

Create `static/js/accessibility.test.js`:

```javascript
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `node --test static/js/accessibility.test.js`
Expected: FAIL with "Cannot find module './accessibility.js'"

- [ ] **Step 3: Create the accessibility module**

Create `static/js/accessibility.js`:

```javascript
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.KioskAccessibility = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  const FONT_SCALE_MIN = 0.85;
  const FONT_SCALE_MAX = 1.6;
  const FONT_SCALE_STEP = 0.15;
  const FONT_SCALE_DEFAULT = 1;

  function clampFontScale(scale) {
    const rounded = Math.round(scale * 100) / 100;
    return Math.min(FONT_SCALE_MAX, Math.max(FONT_SCALE_MIN, rounded));
  }

  function nextFontScale(current, direction) {
    const base = current === undefined || current === null ? FONT_SCALE_DEFAULT : current;
    const delta = direction === 'increase' ? FONT_SCALE_STEP : -FONT_SCALE_STEP;
    return clampFontScale(base + delta);
  }

  return {
    FONT_SCALE_MIN,
    FONT_SCALE_MAX,
    FONT_SCALE_STEP,
    FONT_SCALE_DEFAULT,
    clampFontScale,
    nextFontScale,
  };
});
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `node --test static/js/accessibility.test.js`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add static/js/accessibility.js static/js/accessibility.test.js
git commit -m "feat: add accessibility module for kiosk font scaling"
```

---

### Task 4: Home screen + view routing in index.html

**Files:**
- Modify: `index.html:9-174` (styles)
- Modify: `index.html:176-309` (markup)
- Modify: `index.html:313-611` (script: remove inline i18n, wire modules, add view routing)

**Interfaces:**
- Consumes: `KioskI18n.translate` (via a rewritten local `t()` wrapper), `KioskViewRouter.TILES`,
  `KioskViewRouter.resolveView` from Task 1 and Task 2.
- Produces: `showView(requestedView)` (global function in the inline script) that all
  later tasks (and future module plans) call to navigate; `renderHomeTiles()` (re-renders
  the 4 tiles in the current language, called from `setLanguage()`).

- [ ] **Step 1: Load the new modules and drop the inline i18n object**

In `index.html`, add three `<script>` tags right before the existing inline
`<script>` tag (currently at line 313):

```html
  <script src="/static/js/i18n.js"></script>
  <script src="/static/js/view-router.js"></script>
  <script src="/static/js/accessibility.js"></script>
  <script>
```

Then delete the entire inline `const i18n = { zh: {...}, en: {...} };` block
(currently `index.html:458-569`) — its content now lives in `static/js/i18n.js`
from Task 1.

Replace the `t()` function (currently `index.html:576-579`):

```javascript
function t(key, ...args) {
  return KioskI18n.translate(stateLang.ui, key, ...args);
}
```

- [ ] **Step 2: Run the existing Wayfinding UI to verify it still works with the new i18n wiring**

Start the app:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open `http://127.0.0.1:8000` in a browser. Expected (this step only touches i18n
plumbing, no view routing yet): the page loads exactly as before this task — map,
chat pill, nearby stops list, route cards all render, and clicking "EN" / "中文"
still switches every label. Open the browser devtools console and confirm no errors.

- [ ] **Step 3: Add the CSS for the tile grid, home hero, stub screens, and toolbar**

In `index.html`, inside the existing `<style>` block, add (right before the closing
`</style>` tag, i.e. after the `@media (max-width: 768px)` block that currently ends
around line 173):

```css
    .kiosk-view-full { grid-column: 1 / -1; grid-row: 2; padding: 0 16px 16px; overflow-y:auto; }
    .home-hero { padding: 40px 8px 24px; text-align:center; }
    .home-hero h1 { font-size:36px; font-weight:800; color:var(--text); margin:0 0 8px; }
    .home-hero p { font-size:18px; color:var(--muted); margin:0; }
    .tile-grid { display:grid; grid-template-columns:repeat(2, minmax(0,1fr)); gap:24px; max-width:960px; margin:32px auto 0; padding:0 8px; }
    .tile-card { background:var(--panel); border:2px solid var(--border); border-radius:28px; padding:32px 24px; display:flex; flex-direction:column; align-items:flex-start; gap:12px; cursor:pointer; box-shadow:0 12px 32px rgba(15,23,42,.06); transition:.15s transform ease, .15s box-shadow ease; min-height:220px; text-align:left; font-family:inherit; }
    .tile-card:hover, .tile-card:focus-visible { transform:translateY(-2px); box-shadow:0 18px 40px rgba(15,79,214,.14); border-color:var(--blue); outline:none; }
    .tile-icon { font-size:48px; }
    .tile-title { font-size:24px; font-weight:800; color:var(--text); }
    .tile-subtitle { font-size:15px; color:var(--muted); }
    .a11y-toolbar { display:flex; gap:8px; align-items:center; }
    .a11y-btn { width:40px; height:40px; border-radius:12px; border:1px solid var(--border); background:#fff; font-weight:800; font-size:16px; color:#334155; display:grid; place-items:center; cursor:pointer; }
    .a11y-btn.active { background:#0f4fd6; color:#fff; border-color:#0f4fd6; }
    .home-btn { display:none; }
    .home-btn.visible { display:inline-flex; }
    .coming-soon-card { max-width:560px; margin:64px auto; text-align:center; padding:48px 32px; }
    .coming-soon-icon { font-size:56px; margin-bottom:16px; }
    @media (max-width:768px) {
      .tile-grid { grid-template-columns:1fr; }
    }
```

- [ ] **Step 4: Add the home screen markup and the Home/accessibility toolbar buttons**

In `index.html`, inside `<header class="topbar">`, add a Home button right before
the closing `</button>` of the profile button (i.e. after the existing
`<div class="flex items-center gap-6 text-slate-600">` block's `lang-switch` div,
before the profile `<button>`):

```html
        <button id="home-btn" class="home-btn w-10 h-10 rounded-full hover:bg-slate-100 grid place-items-center" title="Home" type="button">🏠</button>
        <div class="a11y-toolbar" role="group" aria-label="Accessibility controls">
          <button id="font-decrease-btn" class="a11y-btn" type="button">A-</button>
          <button id="font-increase-btn" class="a11y-btn" type="button">A+</button>
          <button id="read-aloud-btn" class="a11y-btn" type="button">🔊</button>
          <button id="fullscreen-btn" class="a11y-btn" type="button">⛶</button>
        </div>
```

Add `data-view="wayfinding"` to the two existing screen elements so the router can
find them — change `<main class="main">` to `<main class="main" data-view="wayfinding">`
and `<aside class="right">` to `<aside class="right" data-view="wayfinding">`.

Immediately after the closing `</aside>` of `aside.right` and before `<footer class="footer">`,
add the home screen section:

```html
    <section class="kiosk-view-full" data-view="home" id="view-home">
      <div class="home-hero">
        <h1 id="home-heading"></h1>
        <p id="home-subheading"></p>
      </div>
      <div class="tile-grid" id="tile-grid"></div>
    </section>
```

- [ ] **Step 5: Wire the view router and tile rendering into the inline script**

In `index.html`'s inline `<script>`, add near the top (after the `const state = {...}`
block, before the Leaflet icon setup):

```javascript
    let currentView = 'home';

    function getViewEls() {
      return document.querySelectorAll('[data-view]');
    }

    function showView(requestedView) {
      const nextViewId = KioskViewRouter.resolveView(requestedView);
      const wasWayfinding = currentView === 'wayfinding';
      currentView = nextViewId;
      getViewEls().forEach((el) => {
        el.style.display = el.dataset.view === nextViewId ? '' : 'none';
      });
      document.getElementById('home-btn').classList.toggle('visible', nextViewId !== 'home');
      if (nextViewId === 'wayfinding' && !wasWayfinding) {
        setTimeout(() => map.invalidateSize(), 50);
      }
    }

    function renderHomeTiles() {
      const grid = document.getElementById('tile-grid');
      grid.innerHTML = '';
      KioskViewRouter.TILES.forEach((tile) => {
        const card = document.createElement('button');
        card.type = 'button';
        card.className = 'tile-card';
        card.innerHTML = `
          <div class="tile-icon">${tile.icon}</div>
          <div class="tile-title">${t(tile.titleKey)}</div>
          <div class="tile-subtitle">${t(tile.subtitleKey)}</div>`;
        card.addEventListener('click', () => showView(tile.id));
        grid.appendChild(card);
      });
    }

    document.getElementById('home-btn').addEventListener('click', () => showView('home'));
```

`map.invalidateSize()` is required because `#map` starts inside a `display:none`
container (the home screen is shown first) — Leaflet sizes its canvas incorrectly
when initialized inside a hidden container, so it must be told to recompute its size
the first time the wayfinding view becomes visible.

- [ ] **Step 6: Update `setLanguage()` to render the home screen text and tiles**

In `index.html`'s `setLanguage(lang)` function (currently `index.html:581-611`), add
these lines right before the existing `renderNearbyStops(state.nearby);` call at the
end of the function:

```javascript
      document.getElementById('home-heading').textContent = t('homeHeading');
      document.getElementById('home-subheading').textContent = t('homeSubheading');
      document.getElementById('home-btn').setAttribute('title', t('home'));
      renderHomeTiles();
```

- [ ] **Step 7: Show the home screen on load**

In `index.html`'s init sequence at the bottom of the script (currently
`index.html:1368-1375`), add `showView('home');` right after `setLanguage('zh');`:

```javascript
    initVoice();
    setLanguage('zh');
    showView('home');
    startNewsTicker();
    loadNearby(defaultLocation.lat, defaultLocation.lon);
    planJourney();
    updateWeatherInfo();
    setInterval(updateWeatherInfo, weatherRefreshIntervalMs);
```

- [ ] **Step 8: Manually verify the home screen and navigation**

Restart `uvicorn` (Ctrl+C, then `uvicorn main:app --reload --host 0.0.0.0 --port 8000`)
and reload `http://127.0.0.1:8000`. Verify:

1. The page loads showing the home screen: heading, subheading, and 4 tiles
   (Wayfinding / Lost & Found / Feedback / Explore Nearby) in a 2x2 grid. The map,
   chat pill, and nearby-stops sidebar are **not** visible.
2. Click the "Wayfinding" tile (🧭 路线指引). The home screen disappears and the
   full existing map UI appears — map tiles render correctly (not blank/mis-sized),
   the hero chat pill, nearby stops list, and route cards are all present and
   functioning exactly as before this task (try a postcode search).
3. Click the Home button (🏠, now visible in the top bar) — it returns to the home
   screen, and the Home button itself hides again.
4. Click "EN" / "中文" while on the home screen — heading, subheading, and all 4
   tile titles/subtitles switch language. Navigate to Wayfinding and confirm the
   language choice persisted and Wayfinding UI is still in the selected language.

- [ ] **Step 9: Commit**

```bash
git add index.html
git commit -m "feat: add kiosk home screen with 4-tile navigation"
```

---

### Task 5: Stub screens + accessibility toolbar wiring

**Files:**
- Modify: `index.html` (markup: 3 stub screens; script: accessibility wiring)

**Interfaces:**
- Consumes: `showView` and `renderHomeTiles` from Task 4; `KioskAccessibility.clampFontScale`,
  `KioskAccessibility.nextFontScale`, `KioskAccessibility.FONT_SCALE_DEFAULT` from Task 3.
- Produces: nothing consumed by later tasks — this closes out the Kiosk Shell plan.
  Future module plans (Lost & Found, Feedback, Nearby POI) replace the stub
  `<section data-view="...">` markup added here with real functionality, reusing the
  same `data-view` attribute and `showView()` call already wired.

- [ ] **Step 1: Add the three stub screens**

In `index.html`, immediately after the `</section>` closing the `view-home` section
added in Task 4 (and before `<footer class="footer">`), add:

```html
    <section class="kiosk-view-full" data-view="lost-found" id="view-lost-found">
      <div class="panel coming-soon-card">
        <div class="coming-soon-icon">🎒</div>
        <div id="coming-soon-lost-found-title" class="text-2xl font-extrabold mb-2"></div>
        <p id="coming-soon-lost-found-body" class="text-slate-500 mb-6"></p>
        <button class="rounded-full bg-blue-700 text-white px-6 py-3 text-lg font-extrabold back-home-btn" type="button"></button>
      </div>
    </section>

    <section class="kiosk-view-full" data-view="feedback" id="view-feedback">
      <div class="panel coming-soon-card">
        <div class="coming-soon-icon">💬</div>
        <div id="coming-soon-feedback-title" class="text-2xl font-extrabold mb-2"></div>
        <p id="coming-soon-feedback-body" class="text-slate-500 mb-6"></p>
        <button class="rounded-full bg-blue-700 text-white px-6 py-3 text-lg font-extrabold back-home-btn" type="button"></button>
      </div>
    </section>

    <section class="kiosk-view-full" data-view="nearby" id="view-nearby">
      <div class="panel coming-soon-card">
        <div class="coming-soon-icon">📍</div>
        <div id="coming-soon-nearby-title" class="text-2xl font-extrabold mb-2"></div>
        <p id="coming-soon-nearby-body" class="text-slate-500 mb-6"></p>
        <button class="rounded-full bg-blue-700 text-white px-6 py-3 text-lg font-extrabold back-home-btn" type="button"></button>
      </div>
    </section>
```

- [ ] **Step 2: Wire the back-to-home buttons and stub screen text**

In the inline `<script>`, right after the `document.getElementById('home-btn').addEventListener(...)`
line added in Task 4 Step 5, add:

```javascript
    document.querySelectorAll('.back-home-btn').forEach((btn) => {
      btn.addEventListener('click', () => showView('home'));
    });
```

In `setLanguage(lang)`, right after the `renderHomeTiles();` line added in Task 4
Step 6, add:

```javascript
      document.getElementById('coming-soon-lost-found-title').textContent = t('comingSoonLostFoundTitle');
      document.getElementById('coming-soon-lost-found-body').textContent = t('comingSoonBody');
      document.getElementById('coming-soon-feedback-title').textContent = t('comingSoonFeedbackTitle');
      document.getElementById('coming-soon-feedback-body').textContent = t('comingSoonBody');
      document.getElementById('coming-soon-nearby-title').textContent = t('comingSoonNearbyTitle');
      document.getElementById('coming-soon-nearby-body').textContent = t('comingSoonBody');
      document.querySelectorAll('.back-home-btn').forEach((btn) => {
        btn.textContent = t('backToHome');
      });
```

- [ ] **Step 3: Manually verify the stub screens**

Restart `uvicorn` and reload. Click "Lost & Found" — a centered card appears with a
🎒 icon, title, "此功能即将上线，敬请期待。" body text, and a "返回首页" button.
Click it — returns to home. Repeat for "Feedback" (💬) and "Explore Nearby" (📍).
Switch language to EN first, then repeat — titles/body/button text are all English.

- [ ] **Step 4: Wire the accessibility toolbar**

In the inline `<script>`, add this block right after the `showView`/`renderHomeTiles`
functions added in Task 4 Step 5 (before the `document.getElementById('home-btn')`
listener):

```javascript
    const accessibilityState = {
      fontScale: KioskAccessibility.FONT_SCALE_DEFAULT,
      readAloudEnabled: false,
    };

    function applyFontScale(scale) {
      accessibilityState.fontScale = scale;
      document.body.style.zoom = String(scale);
      localStorage.setItem('kiosk_font_scale', String(scale));
    }

    function applyReadAloud(enabled) {
      accessibilityState.readAloudEnabled = enabled;
      document.getElementById('read-aloud-btn').classList.toggle('active', enabled);
      localStorage.setItem('kiosk_read_aloud', enabled ? '1' : '0');
    }

    function viewTitleFor(viewId) {
      if (viewId === 'home') return t('homeHeading');
      const tile = KioskViewRouter.TILES.find((item) => item.id === viewId);
      return tile ? t(tile.titleKey) : '';
    }

    function initAccessibility() {
      const storedScale = parseFloat(localStorage.getItem('kiosk_font_scale'));
      applyFontScale(
        Number.isFinite(storedScale)
          ? KioskAccessibility.clampFontScale(storedScale)
          : KioskAccessibility.FONT_SCALE_DEFAULT
      );
      applyReadAloud(localStorage.getItem('kiosk_read_aloud') === '1');

      document.getElementById('font-increase-btn').addEventListener('click', () => {
        applyFontScale(KioskAccessibility.nextFontScale(accessibilityState.fontScale, 'increase'));
      });
      document.getElementById('font-decrease-btn').addEventListener('click', () => {
        applyFontScale(KioskAccessibility.nextFontScale(accessibilityState.fontScale, 'decrease'));
      });
      document.getElementById('read-aloud-btn').addEventListener('click', () => {
        applyReadAloud(!accessibilityState.readAloudEnabled);
      });
      document.getElementById('fullscreen-btn').addEventListener('click', () => {
        if (document.fullscreenElement) {
          document.exitFullscreen();
        } else {
          document.documentElement.requestFullscreen().catch(() => {});
        }
      });
      document.addEventListener('fullscreenchange', () => {
        document.getElementById('fullscreen-btn').classList.toggle('active', !!document.fullscreenElement);
      });
    }
```

Now make `showView` speak the destination screen's title when read-aloud is on.
Replace the `showView` function body added in Task 4 Step 5 with:

```javascript
    function showView(requestedView) {
      const nextViewId = KioskViewRouter.resolveView(requestedView);
      const wasWayfinding = currentView === 'wayfinding';
      currentView = nextViewId;
      getViewEls().forEach((el) => {
        el.style.display = el.dataset.view === nextViewId ? '' : 'none';
      });
      document.getElementById('home-btn').classList.toggle('visible', nextViewId !== 'home');
      if (nextViewId === 'wayfinding' && !wasWayfinding) {
        setTimeout(() => map.invalidateSize(), 50);
      }
      if (accessibilityState.readAloudEnabled) {
        speak(viewTitleFor(nextViewId));
      }
    }
```

- [ ] **Step 5: Set bilingual aria-labels on the accessibility toolbar**

In `setLanguage(lang)`, right after the `back-home-btn` block added in Step 2, add:

```javascript
      document.getElementById('font-increase-btn').setAttribute('aria-label', t('a11yFontIncrease'));
      document.getElementById('font-decrease-btn').setAttribute('aria-label', t('a11yFontDecrease'));
      document.getElementById('read-aloud-btn').setAttribute('aria-label', t('a11yReadAloud'));
      document.getElementById('fullscreen-btn').setAttribute('aria-label', t('a11yFullscreen'));
```

- [ ] **Step 6: Call `initAccessibility()` during init**

In the init sequence at the bottom of the script, call `initAccessibility()` before
`setLanguage('zh')` so a persisted font scale/read-aloud preference is applied before
the first render:

```javascript
    initAccessibility();
    initVoice();
    setLanguage('zh');
    showView('home');
    startNewsTicker();
    loadNearby(defaultLocation.lat, defaultLocation.lon);
    planJourney();
    updateWeatherInfo();
    setInterval(updateWeatherInfo, weatherRefreshIntervalMs);
```

- [ ] **Step 7: Manually verify accessibility controls and run the full regression pass**

Restart `uvicorn` and reload `http://127.0.0.1:8000`. Verify:

1. **Font scale**: click "A+" three times — the entire page (text, tiles, buttons,
   map controls) grows uniformly. Click "A+" several more times — it stops growing
   once it hits the max (further clicks have no visible effect). Click "A-" repeatedly
   — shrinks, then clamps at the min. Reload the page — the scale you left it at is
   still applied (persisted via `localStorage`).
2. **Read aloud**: click the 🔊 button (it highlights as active). Click the Home
   button, then a tile, then a back-to-home button — each navigation is spoken aloud
   in the current UI language. Click 🔊 again to disable — navigation is silent again.
   Reload — the read-aloud on/off state persisted.
3. **Fullscreen**: click the ⛶ button — the browser enters fullscreen and the button
   highlights as active. Click again (or press Escape) — exits fullscreen and the
   button un-highlights.
4. **Full regression on the Wayfinding screen**: navigate to Wayfinding via its tile.
   Confirm: map renders correctly sized, postcode search still geocodes and updates
   nearby stops, nearby stop cards still show live arrivals, clicking a route card's
   "Details" button still speaks the route and shows a toast, the mic button still
   triggers voice recognition (if supported by the browser), the news ticker and
   weather widget still update. All of this must behave identically to how it did
   before this plan — only reachable via the Wayfinding tile now instead of being
   the only screen.
5. **Language parity**: switch to EN, then repeat steps 1–4's visible text checks —
   every string on every screen (home, all 3 stubs, accessibility toolbar labels,
   Wayfinding) is in English with no leftover Chinese text or missing translations
   (no raw i18n key names visible anywhere).

- [ ] **Step 8: Run the full automated test suite one more time**

Run:

```bash
pytest -v
node --test "static/js/*.test.js"
```

Expected: all backend and JS tests PASS.

- [ ] **Step 9: Commit**

```bash
git add index.html
git commit -m "feat: wire accessibility toolbar and stub screens into kiosk shell"
```
