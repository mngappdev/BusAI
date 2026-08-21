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

  const ALIGHTING_IDS = ['A1', 'A2', 'A3', 'A4', 'A5'];
  const ALIGHTING_X = [40, 110, 180, 250, 320];

  const BOARDING_POSITIONS = {
    B1: { x: 90, y: 140 },
    B2: { x: 150, y: 140 },
    B3: { x: 210, y: 140 },
    B4: { x: 270, y: 140 },
    B5: { x: 330, y: 140 },
    B6: { x: 90, y: 210 },
    B7: { x: 150, y: 210 },
    B8: { x: 210, y: 210 },
    B9: { x: 270, y: 210 },
    B10: { x: 330, y: 210 },
  };

  const MRT_LINK_POSITION = { x: 45, y: 110 };

  function buildFloorPlanSvg(activeBerth) {
    const boardingCells = BOARDING_BERTHS.map((id) => {
      const pos = BOARDING_POSITIONS[id];
      const active = id === activeBerth;
      return `<g class="fp-berth${active ? ' fp-berth-active' : ''}">`
        + `<rect x="${pos.x - 24}" y="${pos.y - 16}" width="48" height="32" rx="8"></rect>`
        + `<text x="${pos.x}" y="${pos.y + 5}" text-anchor="middle">${id}</text>`
        + `</g>`;
    }).join('');

    const alightingCells = ALIGHTING_IDS.map((id, index) => {
      const x = ALIGHTING_X[index];
      return `<g class="fp-alighting">`
        + `<rect x="${x - 22}" y="14" width="44" height="28" rx="8"></rect>`
        + `<text x="${x}" y="33" text-anchor="middle">${id}</text>`
        + `</g>`;
    }).join('');

    const target = BOARDING_POSITIONS[activeBerth];
    const routePath = target
      ? `<path class="fp-route" fill="none" d="M ${MRT_LINK_POSITION.x} ${MRT_LINK_POSITION.y} L ${target.x} ${MRT_LINK_POSITION.y} L ${target.x} ${target.y}"></path>`
      : '';

    return `<svg viewBox="0 0 380 260" class="floor-plan-svg" xmlns="http://www.w3.org/2000/svg">`
      + `<rect x="10" y="10" width="360" height="235" rx="16" class="fp-boundary"></rect>`
      + `<g class="fp-mrt-link">`
      + `<rect x="10" y="90" width="70" height="40" rx="8"></rect>`
      + `<text x="45" y="106" text-anchor="middle">🚇</text>`
      + `<text x="45" y="122" text-anchor="middle" class="fp-mrt-label">MRT B</text>`
      + `</g>`
      + alightingCells
      + boardingCells
      + routePath
      + `</svg>`;
  }

  return {
    BOARDING_BERTHS,
    buildSchematicHtml,
    ALIGHTING_IDS,
    BOARDING_POSITIONS,
    MRT_LINK_POSITION,
    buildFloorPlanSvg,
  };
});
