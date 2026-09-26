const test = require('node:test');
const assert = require('node:assert/strict');
const { fetchVoiceIntent, fetchTripNarration } = require('./ai-features.js');

function fakeFetchResolving(body, ok = true) {
  return async () => ({ ok, json: async () => body });
}

function fakeFetchNeverResolving() {
  return () => new Promise(() => {}); // never settles — exercises the timeout path
}

function fakeFetchRejecting() {
  return async () => { throw new Error('network down'); };
}

// ─── fetchVoiceIntent ───────────────────────────────────────────────────────

test('fetchVoiceIntent returns the parsed intent on success', async () => {
  const result = await fetchVoiceIntent({
    text: 'take me to white sands', lang: 'en',
    fetchImpl: fakeFetchResolving({ destination_query: 'white sands', target_arrival_time: null, confidence: 'high' }),
  });

  assert.deepEqual(result, { destination_query: 'white sands', target_arrival_time: null, confidence: 'high' });
});

test('fetchVoiceIntent sends the text and lang in the request body', async () => {
  let sentBody = null;
  const fetchImpl = async (url, options) => {
    sentBody = JSON.parse(options.body);
    return { ok: true, json: async () => ({ destination_query: null, target_arrival_time: null, confidence: 'low' }) };
  };

  await fetchVoiceIntent({ text: 'hello there', lang: 'zh', fetchImpl });

  assert.equal(sentBody.text, 'hello there');
  assert.equal(sentBody.lang, 'zh');
});

test('fetchVoiceIntent returns null on a non-ok response', async () => {
  const result = await fetchVoiceIntent({ text: 'x', lang: 'en', fetchImpl: fakeFetchResolving({}, false) });
  assert.equal(result, null);
});

test('fetchVoiceIntent returns null when fetch rejects', async () => {
  const result = await fetchVoiceIntent({ text: 'x', lang: 'en', fetchImpl: fakeFetchRejecting() });
  assert.equal(result, null);
});

test('fetchVoiceIntent returns null after the timeout elapses', async () => {
  const start = Date.now();
  const result = await fetchVoiceIntent({
    text: 'x', lang: 'en', timeoutMs: 30, fetchImpl: fakeFetchNeverResolving(),
  });
  const elapsed = Date.now() - start;

  assert.equal(result, null);
  assert.ok(elapsed < 500, `should resolve promptly after the 30ms timeout, took ${elapsed}ms`);
});

// ─── fetchTripNarration ─────────────────────────────────────────────────────

test('fetchTripNarration returns the narrative string on success', async () => {
  const result = await fetchTripNarration({
    trip: { service: '53', stops: 8 }, lang: 'en',
    fetchImpl: fakeFetchResolving({ narrative: 'Walk to Berth B1.' }),
  });

  assert.equal(result, 'Walk to Berth B1.');
});

test('fetchTripNarration returns null when the narrative field is null', async () => {
  const result = await fetchTripNarration({
    trip: { service: '53' }, lang: 'en', fetchImpl: fakeFetchResolving({ narrative: null }),
  });

  assert.equal(result, null);
});

test('fetchTripNarration returns null on a non-ok response', async () => {
  const result = await fetchTripNarration({ trip: {}, lang: 'en', fetchImpl: fakeFetchResolving({}, false) });
  assert.equal(result, null);
});

test('fetchTripNarration returns null when fetch rejects', async () => {
  const result = await fetchTripNarration({ trip: {}, lang: 'en', fetchImpl: fakeFetchRejecting() });
  assert.equal(result, null);
});

test('fetchTripNarration returns null after the timeout elapses', async () => {
  const start = Date.now();
  const result = await fetchTripNarration({
    trip: {}, lang: 'en', timeoutMs: 30, fetchImpl: fakeFetchNeverResolving(),
  });
  const elapsed = Date.now() - start;

  assert.equal(result, null);
  assert.ok(elapsed < 500, `should resolve promptly after the 30ms timeout, took ${elapsed}ms`);
});

test('fetchTripNarration sends the trip and lang in the request body', async () => {
  let sentBody = null;
  const fetchImpl = async (url, options) => {
    sentBody = JSON.parse(options.body);
    return { ok: true, json: async () => ({ narrative: null }) };
  };

  await fetchTripNarration({ trip: { service: '53' }, lang: 'zh', fetchImpl });

  assert.deepEqual(sentBody.trip, { service: '53' });
  assert.equal(sentBody.lang, 'zh');
});
