(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.KioskDigitalHuman = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  // The concierge figure in the map overlay reflects what the kiosk is doing,
  // the way the assistant-status line does — so a passenger glancing at the
  // person, not the text, still knows whether it is listening or answering.
  //
  //   idle       — breathing float, blue aura
  //   listening  — mic is open (recognition.onstart .. onend), cyan aura
  //   speaking   — TTS is talking (utterance.onstart .. onend), green aura
  //
  // The CSS lives in index.html keyed off `.dh-state-<name>` on the figure's
  // container. This module only owns which one is set.

  const STATES = ['idle', 'listening', 'speaking'];
  const PREFIX = 'dh-state-';

  function resolve(state) {
    return STATES.indexOf(state) === -1 ? 'idle' : state;
  }

  function stateClass(state) {
    return PREFIX + resolve(state);
  }

  function setState(el, state) {
    const resolved = resolve(state);
    const list = el && el.classList;
    if (list && typeof list.add === 'function') {
      STATES.forEach((s) => list.remove(PREFIX + s));
      list.add(PREFIX + resolved);
    }
    return resolved;
  }

  return { setState, stateClass, STATES };
});
