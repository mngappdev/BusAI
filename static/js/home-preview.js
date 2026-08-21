(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.KioskHomePreview = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  function pickBestPreview(stops) {
    if (!Array.isArray(stops)) return null;
    for (const stop of stops) {
      const nearest = stop && stop.nearest_arrival;
      if (nearest && nearest.minutes != null) {
        return { service: nearest.service, minutes: nearest.minutes };
      }
    }
    return null;
  }

  return { pickBestPreview };
});
