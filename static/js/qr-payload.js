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
