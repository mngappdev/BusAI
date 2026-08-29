const test = require('node:test');
const assert = require('node:assert/strict');
const { classify, classifyCode, ERROR_CODES } = require('./speech-errors.js');
const { translate } = require('./i18n.js');

// One onerror handler receives everything from "nobody spoke" to "this browser
// has no recognition service". The kiosk has to tell those apart.

test('classify reads the code straight off the error event', () => {
  const failure = classify({ error: 'network' });
  assert.equal(failure.code, 'network');
  assert.equal(failure.key, 'voiceErrNetwork');
});

test('a passenger saying nothing is retryable and needs nobody', () => {
  const failure = classify({ error: 'no-speech' });
  assert.equal(failure.retryable, true);
  assert.equal(failure.needsAttention, false);
});

test('an aborted attempt needs nobody either', () => {
  const failure = classify({ error: 'aborted' });
  assert.equal(failure.needsAttention, false);
});

test('a missing microphone is flagged for a person to fix', () => {
  const failure = classify({ error: 'audio-capture' });
  assert.equal(failure.retryable, false);
  assert.equal(failure.needsAttention, true);
});

test('a denied microphone permission is flagged for a person to fix', () => {
  const failure = classify({ error: 'not-allowed' });
  assert.equal(failure.needsAttention, true);
  assert.equal(failure.key, 'voiceErrNotAllowed');
});

test('a browser build without the recognition service is distinguishable from a denial', () => {
  const blocked = classify({ error: 'service-not-allowed' });
  const denied = classify({ error: 'not-allowed' });

  assert.notEqual(blocked.key, denied.key, 'these need different instructions');
  assert.equal(blocked.needsAttention, true);
});

test('network failures are retryable but still worth logging', () => {
  const failure = classify({ error: 'network' });
  assert.equal(failure.retryable, true);
  assert.equal(failure.needsAttention, true);
});

// ─── Robustness ───────────────────────────────────────────────────────────

test('an unknown code still surfaces rather than being swallowed', () => {
  const failure = classify({ error: 'teleportation-failed' });
  assert.equal(failure.code, 'teleportation-failed');
  assert.equal(failure.key, 'voiceError');
  assert.equal(failure.needsAttention, true);
});

test('a missing or malformed event never throws', () => {
  for (const input of [undefined, null, {}, { error: '' }, { error: 42 }]) {
    const failure = classify(input);
    assert.equal(failure.code, 'unknown');
    assert.equal(failure.key, 'voiceError');
  }
});

test('classifyCode accepts a bare code string', () => {
  assert.equal(classifyCode('no-speech').key, 'voiceErrNoSpeech');
});

// ─── i18n coverage ────────────────────────────────────────────────────────

test('every error code has a distinct message in both languages', () => {
  for (const lang of ['zh', 'en']) {
    const seen = new Map();
    for (const code of ERROR_CODES) {
      const key = classifyCode(code).key;
      const text = translate(lang, key);

      assert.ok(text, `${lang}/${key} has no translation`);
      assert.notEqual(text, key, `${lang}/${key} fell through to the raw key`);
      assert.ok(!seen.has(text), `${lang}: "${text}" is reused by ${seen.get(text)} and ${code}`);
      seen.set(text, code);
    }
  }
});

test('the unknown-error fallback is translated in both languages', () => {
  for (const lang of ['zh', 'en']) {
    const text = translate(lang, classify({}).key);
    assert.ok(text && text !== 'voiceError');
  }
});
