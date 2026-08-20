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
