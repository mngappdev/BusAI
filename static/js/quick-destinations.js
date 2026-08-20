(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.KioskQuickDestinations = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  const QUICK_DESTINATIONS = [
    { id: 'changi-airport', icon: '✈️', labelKey: 'quickDestChangi', lat: 1.3575, lon: 103.9885 },
    { id: 'changi-hospital', icon: '🏥', labelKey: 'quickDestHospital', lat: 1.3405, lon: 103.9493 },
    { id: 'white-sands-mall', icon: '🛍️', labelKey: 'quickDestMall', lat: 1.3721, lon: 103.9493 },
    { id: 'elias-cc', icon: '🏛️', labelKey: 'quickDestCC', lat: 1.3806, lon: 103.9427 },
  ];

  return { QUICK_DESTINATIONS };
});
