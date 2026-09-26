(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.KioskAIFeatures = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  // Both functions here follow the same rule as their backend counterparts in
  // ai_features.py: any failure — timeout, network error, non-200, malformed
  // body — resolves to null, never rejects. The caller's own fallback (today's
  // exact behavior, pre-dating these features) always runs when this happens.

  async function withTimeout(fetchImpl, url, options, timeoutMs) {
    const controller = new AbortController();
    let timer;
    // Races the fetch against a plain timer that resolves to null. This race
    // is what actually bounds wall-clock time — aborting the signal is a
    // courtesy that lets a real fetch() free its connection early, but nothing
    // requires fetchImpl to honor it. A fetchImpl that ignores the signal
    // (any fake that doesn't wire it up, or a misbehaving real one) would hang
    // this forever without the race — confirmed by hand: an earlier version of
    // this function that only used `signal` (no race) hung indefinitely
    // against a fake fetch that never resolves.
    const timeoutPromise = new Promise((resolve) => {
      timer = setTimeout(() => {
        controller.abort();
        resolve(null);
      }, timeoutMs);
    });

    const fetchAndParse = (async () => {
      try {
        const res = await fetchImpl(url, { ...options, signal: controller.signal });
        if (!res.ok) return null;
        return await res.json();
      } catch (err) {
        return null;
      }
    })();

    const result = await Promise.race([fetchAndParse, timeoutPromise]);
    clearTimeout(timer);
    return result;
  }

  async function fetchVoiceIntent({ text, lang, apiBase = '', timeoutMs = 1200, fetchImpl = fetch }) {
    const data = await withTimeout(fetchImpl, `${apiBase}/api/v1/voice-intent`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, lang }),
    }, timeoutMs);

    if (!data || typeof data !== 'object') return null;
    return {
      destination_query: typeof data.destination_query === 'string' ? data.destination_query : null,
      target_arrival_time: typeof data.target_arrival_time === 'string' ? data.target_arrival_time : null,
      confidence: data.confidence === 'high' ? 'high' : 'low',
    };
  }

  async function fetchTripNarration({ trip, lang, apiBase = '', timeoutMs = 1500, fetchImpl = fetch }) {
    const data = await withTimeout(fetchImpl, `${apiBase}/api/v1/narrate-trip`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ trip, lang }),
    }, timeoutMs);

    if (!data || typeof data.narrative !== 'string' || !data.narrative.trim()) return null;
    return data.narrative;
  }

  return { fetchVoiceIntent, fetchTripNarration };
});
