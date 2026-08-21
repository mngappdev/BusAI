(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.KioskBerthSchematic = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  // Floor plan for Pasir Ris Bus Interchange, drawn to the published BERTH
  // LAYOUT diagram and the berth assignments on landtransportguru.net.
  // Topology (which berth sits where, relative to the concourse and the
  // exits) is faithful; distances are not to scale.

  const BOARDING_BERTHS = ['B1', 'B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B9', 'B10'];
  const ALIGHTING_IDS = ['A1', 'A2', 'A3', 'A4', 'A5'];

  // Service numbers exactly as the interchange signage shows them. The W/E
  // suffixes matter: 359 and 358 each loop, and each loop direction boards
  // from a different berth.
  const BERTH_SERVICES = {
    B1: ['58', '88'],
    B2: ['12', '12e', '21'],
    B3: ['17', '68'],
    B4: ['359W', '403'],
    B5: ['358W', '46'],
    B6: ['359E', '354'],
    B7: ['358E', '3'],
    B8: ['5', '6'],
    B9: ['15', '518', '518A'],
    B10: [],
  };

  // Centre of each berth's label pill, in viewBox units.
  const BOARDING_POSITIONS = {
    B1: { x: 470, y: 397 },
    B2: { x: 330, y: 389 },
    B3: { x: 214, y: 337 },
    B4: { x: 196, y: 263 },
    B5: { x: 210, y: 189 },
    B6: { x: 247, y: 89 },
    B7: { x: 371, y: 89 },
    B8: { x: 490, y: 89 },
    B9: { x: 624, y: 89 },
    B10: { x: 769, y: 89 },
  };

  const KIOSK_POSITION = { x: 430, y: 320 };

  // Walking routes through the open concourse. They follow two corridors —
  // the y=320 spine and the x=300 spine — so no line cuts through a berth.
  const ROUTE_WAYPOINTS = {
    B1: [[430, 320], [470, 320], [470, 378]],
    B2: [[430, 320], [330, 320], [330, 370]],
    B3: [[430, 320], [300, 320], [300, 337], [268, 337]],
    B4: [[430, 320], [300, 320], [300, 263], [254, 263]],
    B5: [[430, 320], [300, 320], [300, 189], [266, 189]],
    B6: [[430, 320], [300, 320], [300, 145], [247, 145]],
    B7: [[430, 320], [371, 320], [371, 146]],
    B8: [[430, 320], [490, 320], [490, 146]],
    B9: [[430, 320], [624, 320], [624, 146]],
    B10: [[430, 320], [769, 320], [769, 146]],
  };

  // The hall's outline: angled west wall, stepped north and east edges.
  const HALL_OUTLINE = 'M 196 62 L 590 62 L 590 30 L 662 30 L 662 62 L 706 62 '
    + 'L 706 18 L 776 18 L 776 62 L 828 62 L 828 118 L 860 118 L 860 232 '
    + 'L 828 232 L 828 286 L 860 286 L 860 462 L 704 462 L 704 496 L 618 496 '
    + 'L 618 462 L 196 462 L 126 400 L 92 306 L 106 190 Z';

  const PILL_W = 96;
  const PILL_H = 26;
  const CHIP_H = 30;
  const CHIP_GAP = 6;

  // Some best-route stops (e.g. Pasir Ris Stn Exit B) are curbside stops
  // near the interchange but outside it — real bus stops with no berth
  // number, not a data gap. The route walks out of the hall to a labelled
  // pin instead of pointing at a berth that doesn't exist.
  // Threads the gap between B2 (right edge x=378) and B1 (left edge x=422)
  // before dropping below the alighting strip, so the line clears every
  // berth pill and the alighting box rather than cutting through them.
  const OFFSITE_WAYPOINTS = [[430, 320], [400, 320], [400, 480], [620, 480]];
  const OFFSITE_POSITION = { x: 620, y: 480 };

  function escapeXml(str) {
    return String(str).replace(/[&<>"']/g, (ch) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;',
    }[ch]));
  }

  function chipWidth(label) {
    return Math.max(34, 13 + 9 * label.length);
  }

  // Every signage label in physical berth order, for a "which berth is my
  // bus?" picker. Unlike BERTH_SERVICES this is a flat list, so a directional
  // pair like 359W/359E shows up as two separate, unambiguous choices.
  const ALL_SERVICES = BOARDING_BERTHS.reduce((acc, b) => acc.concat(BERTH_SERVICES[b]), []);

  function findBerthForService(label) {
    for (const berth of BOARDING_BERTHS) {
      if (BERTH_SERVICES[berth].indexOf(label) !== -1) return berth;
    }
    return null;
  }

  function normaliseActive(active) {
    const list = active == null ? [] : [].concat(active);
    return list.filter((berth) => Object.prototype.hasOwnProperty.call(BOARDING_POSITIONS, berth));
  }

  function renderBerth(id, isActive) {
    const pos = BOARDING_POSITIONS[id];
    const services = BERTH_SERVICES[id] || [];
    const pillX = pos.x - PILL_W / 2;
    const pillY = pos.y - PILL_H / 2;

    const totalW = services.reduce((sum, s) => sum + chipWidth(s), 0)
      + Math.max(0, services.length - 1) * CHIP_GAP;
    let cursor = pos.x - totalW / 2;
    const chipY = pillY + PILL_H + 6;

    const chips = services.map((label) => {
      const w = chipWidth(label);
      const chip = `<g class="fp-chip">`
        + `<rect x="${cursor}" y="${chipY}" width="${w}" height="${CHIP_H}" rx="6"></rect>`
        + `<text x="${cursor + w / 2}" y="${chipY + CHIP_H / 2 + 6}" text-anchor="middle">${label}</text>`
        + `</g>`;
      cursor += w + CHIP_GAP;
      return chip;
    }).join('');

    return `<g class="fp-berth${isActive ? ' fp-berth-active' : ''}">`
      + `<rect class="fp-pill" x="${pillX}" y="${pillY}" width="${PILL_W}" height="${PILL_H}" rx="7"></rect>`
      + `<text class="fp-pill-text" x="${pos.x}" y="${pos.y + 6}" text-anchor="middle">${id}</text>`
      + chips
      + `</g>`;
  }

  function renderRoute(id) {
    const points = ROUTE_WAYPOINTS[id];
    const d = points.map(([x, y], i) => `${i === 0 ? 'M' : 'L'} ${x} ${y}`).join(' ');
    const [endX, endY] = points[points.length - 1];
    return `<path class="fp-route" fill="none" d="${d}"></path>`
      + `<circle class="fp-route-end" cx="${endX}" cy="${endY}" r="9"></circle>`;
  }

  function renderExit(x, y, label) {
    return `<g class="fp-exit">`
      + `<rect x="${x}" y="${y}" width="88" height="42" rx="7"></rect>`
      + `<text x="${x + 44}" y="${y + 18}" text-anchor="middle">EXIT</text>`
      + `<text x="${x + 44}" y="${y + 33}" text-anchor="middle" class="fp-exit-sub">${label}</text>`
      + `</g>`;
  }

  function renderAlighting() {
    return `<g class="fp-alighting">`
      + `<rect x="560" y="416" width="270" height="30" rx="7"></rect>`
      + `<text x="695" y="436" text-anchor="middle">`
      + `ALIGHTING ${ALIGHTING_IDS[0]}-${ALIGHTING_IDS[ALIGHTING_IDS.length - 1]}</text>`
      + `</g>`;
  }

  function renderKiosk() {
    return `<g class="fp-kiosk">`
      + `<circle class="fp-kiosk-pulse" cx="${KIOSK_POSITION.x}" cy="${KIOSK_POSITION.y}" r="20"></circle>`
      + `<circle class="fp-kiosk-dot" cx="${KIOSK_POSITION.x}" cy="${KIOSK_POSITION.y}" r="10"></circle>`
      + `<text x="${KIOSK_POSITION.x}" y="${KIOSK_POSITION.y + 40}" text-anchor="middle">YOU ARE HERE</text>`
      + `</g>`;
  }

  // Shared chrome every floor-plan variant draws: the hall, its two known
  // amenity exits, the alighting strip, and every berth (unhighlighted).
  function renderHallChrome(berths) {
    return `<path class="fp-boundary" d="${HALL_OUTLINE}"></path>`
      + `<text class="fp-title" x="546" y="222" text-anchor="middle">PASIR RIS BUS INTERCHANGE</text>`
      + renderExit(8, 148, 'Pasir Ris Mall')
      + renderExit(8, 372, 'Polyclinic')
      + renderAlighting()
      + berths;
  }

  function buildFloorPlanSvg(active) {
    const activeBerths = normaliseActive(active);
    const isActive = (id) => activeBerths.indexOf(id) !== -1;

    const berths = BOARDING_BERTHS.map((id) => renderBerth(id, isActive(id))).join('');
    const routes = activeBerths.map(renderRoute).join('');

    return `<svg viewBox="0 0 880 520" class="floor-plan-svg" xmlns="http://www.w3.org/2000/svg" role="img">`
      + renderHallChrome(berths)
      + routes
      + renderKiosk()
      + `</svg>`;
  }

  function buildOffsiteFloorPlanSvg(stopName) {
    const berths = BOARDING_BERTHS.map((id) => renderBerth(id, false)).join('');
    const [d, [endX, endY]] = [
      OFFSITE_WAYPOINTS.map(([x, y], i) => `${i === 0 ? 'M' : 'L'} ${x} ${y}`).join(' '),
      OFFSITE_WAYPOINTS[OFFSITE_WAYPOINTS.length - 1],
    ];
    const safeName = escapeXml(stopName);

    const offsiteRoute = `<path class="fp-route fp-route-offsite" fill="none" d="${d}"></path>`
      + `<g class="fp-offsite-pin">`
      + `<circle cx="${endX}" cy="${endY}" r="10"></circle>`
      + `<text x="${endX}" y="${endY + 34}" text-anchor="middle">🚶 ${safeName}</text>`
      + `</g>`;

    return `<svg viewBox="0 0 880 520" class="floor-plan-svg" xmlns="http://www.w3.org/2000/svg" role="img">`
      + renderHallChrome(berths)
      + offsiteRoute
      + renderKiosk()
      + `</svg>`;
  }

  return {
    BOARDING_BERTHS,
    BERTH_SERVICES,
    ALIGHTING_IDS,
    BOARDING_POSITIONS,
    KIOSK_POSITION,
    ROUTE_WAYPOINTS,
    ALL_SERVICES,
    findBerthForService,
    buildFloorPlanSvg,
    OFFSITE_WAYPOINTS,
    OFFSITE_POSITION,
    buildOffsiteFloorPlanSvg,
  };
});
