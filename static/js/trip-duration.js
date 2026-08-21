(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.KioskTripDuration = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  // Same formula buildDirectTimeline uses for its visible duration badge —
  // extracted so the spoken ETA can never drift from what the panel shows.
  // Deliberately excludes the live-arrival wait: that's how long until the
  // bus shows up, not how long the trip itself takes.
  function computeDirectTripMinutes(best) {
    const travelMins = Math.max(4, (best?.stops ?? 5) * 2);
    const walkMins = Math.round((best?.dist_km ?? 0.5) * 12);
    return travelMins + walkMins;
  }

  return { computeDirectTripMinutes };
});
