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
    // The engine measures this from the alighting stop to the destination.
    // Never derive it from dist_km — that is the distance travelled ON the
    // bus, and scaling it once turned a 2-minute walk into 101 minutes.
    const walkMins = Math.max(1, best?.walk_to_dest_min ?? 5);
    return travelMins + walkMins;
  }

  return { computeDirectTripMinutes };
});
