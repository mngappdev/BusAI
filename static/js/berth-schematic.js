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
