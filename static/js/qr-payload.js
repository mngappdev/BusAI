(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.KioskQrPayload = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  const DEFAULT_LABELS = { bus: 'Bus', to: '->', stops: 'stops', berth: 'Berth' };

  function buildDirectTripPayload(trip, labels) {
    const L = labels || DEFAULT_LABELS;
    const lines = [
      `${L.bus} ${trip.service}`,
      `${trip.fromName} ${L.to} ${trip.toName}`,
      `${trip.stops} ${L.stops}`,
    ];
    if (trip.berth) {
      lines.push(`${L.berth} ${trip.berth}`);
    }
    return lines.join('\n');
  }

  function utf8ToBytes(str) {
    const bytes = [];
    for (let i = 0; i < str.length; i++) {
      const c = str.charCodeAt(i);
      if (c < 0x80) {
        bytes.push(c);
      } else if (c < 0x800) {
        bytes.push(0xc0 | (c >> 6), 0x80 | (c & 0x3f));
      } else if (c >= 0xd800 && c < 0xdc00 && i + 1 < str.length) {
        i++;
        const c2 = str.charCodeAt(i);
        const cp = 0x10000 + ((c & 0x3ff) << 10) + (c2 & 0x3ff);
        bytes.push(
          0xf0 | (cp >> 18),
          0x80 | ((cp >> 12) & 0x3f),
          0x80 | ((cp >> 6) & 0x3f),
          0x80 | (cp & 0x3f)
        );
      } else {
        bytes.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 0x3f), 0x80 | (c & 0x3f));
      }
    }
    return bytes;
  }

  return { DEFAULT_LABELS, buildDirectTripPayload, utf8ToBytes };
});
