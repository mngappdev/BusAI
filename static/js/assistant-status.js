(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.KioskAssistantStatus = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  // The assistant line under the concierge used to hold a finished string, so
  // switching EN/ZH could not re-render it — setLanguage just blanked it back
  // to "ready", throwing away whatever was actually happening. Keeping the key
  // and its arguments instead means the same status can be re-rendered in any
  // language, at any time.

  const DEFAULT_KEY = 'ready';

  function createStore(translate) {
    let current = { key: DEFAULT_KEY, args: [] };

    return {
      set(key, ...args) {
        if (!key) return current;
        current = { key: key, args: args };
        return current;
      },
      current() {
        return { key: current.key, args: current.args.slice() };
      },
      reset() {
        current = { key: DEFAULT_KEY, args: [] };
        return current;
      },
      render(lang) {
        return translate(lang, current.key, ...current.args);
      },
    };
  }

  // Whoever announces "planning" owns clearing it. planJourney sets this the
  // moment renderTripSummary returns, so the line can never be left claiming
  // the trip is still being planned while the route sits on screen.
  function planStatus(data) {
    if (!data) return { key: 'noRoute', args: [] };

    if (data.type === 'walk') {
      return { key: 'statusWalkSuggested', args: [data.minutes] };
    }

    if (data.type === 'none') {
      return { key: 'noRoute', args: [] };
    }

    if (data.mode === 'transfer') {
      const first = (data.options || [])[0];
      if (first && first.leg1 && first.leg2) {
        return { key: 'bestOption', args: [`${first.leg1.service} → ${first.leg2.service}`] };
      }
      return { key: 'noRoute', args: [] };
    }

    const best = data.best || (data.options || [])[0];
    if (best && best.service) {
      return { key: 'bestOption', args: [best.service] };
    }
    return { key: 'noRoute', args: [] };
  }

  return { createStore, planStatus, DEFAULT_KEY };
});
