(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.KioskViewRouter = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  const TILES = [
    {
      id: 'wayfinding',
      icon: '🧭',
      titleKey: 'homeTileWayfindingTitle',
      subtitleKey: 'homeTileWayfindingSubtitle',
    },
    {
      id: 'lost-found',
      icon: '🎒',
      titleKey: 'homeTileLostFoundTitle',
      subtitleKey: 'homeTileLostFoundSubtitle',
    },
    {
      id: 'feedback',
      icon: '💬',
      titleKey: 'homeTileFeedbackTitle',
      subtitleKey: 'homeTileFeedbackSubtitle',
    },
    {
      id: 'nearby',
      icon: '📍',
      titleKey: 'homeTileNearbyTitle',
      subtitleKey: 'homeTileNearbySubtitle',
    },
  ];

  const VALID_VIEWS = ['home', ...TILES.map((tile) => tile.id)];

  function resolveView(requestedView) {
    return VALID_VIEWS.includes(requestedView) ? requestedView : 'home';
  }

  return { TILES, VALID_VIEWS, resolveView };
});
