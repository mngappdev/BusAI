(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.KioskSpeechErrors = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  // The Web Speech API reports very different failures through one onerror
  // handler. Collapsing them all into "语音输入错误" hides the ones an operator
  // has to act on: an unplugged microphone, a denied permission, or a browser
  // build with no recognition service reads exactly like a passer-by saying
  // nothing. Each code is mapped to its own message and triaged.
  //
  //   retryable      — the passenger can simply try again
  //   needsAttention — a person has to fix something; log it loudly

  const ERRORS = {
    'no-speech': {
      key: 'voiceErrNoSpeech',
      retryable: true,
      needsAttention: false,
    },
    'aborted': {
      key: 'voiceErrAborted',
      retryable: true,
      needsAttention: false,
    },
    'audio-capture': {
      key: 'voiceErrAudioCapture',
      retryable: false,
      needsAttention: true,
    },
    'network': {
      key: 'voiceErrNetwork',
      retryable: true,
      needsAttention: true,
    },
    'not-allowed': {
      key: 'voiceErrNotAllowed',
      retryable: false,
      needsAttention: true,
    },
    'service-not-allowed': {
      key: 'voiceErrServiceNotAllowed',
      retryable: false,
      needsAttention: true,
    },
    'language-not-supported': {
      key: 'voiceErrLanguageNotSupported',
      retryable: false,
      needsAttention: true,
    },
    'bad-grammar': {
      key: 'voiceErrBadGrammar',
      retryable: false,
      needsAttention: true,
    },
  };

  // An unrecognised code is still worth surfacing rather than swallowing: the
  // spec grows, and a kiosk that says "unknown error (foo)" is diagnosable.
  const UNKNOWN = {
    key: 'voiceError',
    retryable: true,
    needsAttention: true,
  };

  function classify(error) {
    const code = typeof error === 'string' && error ? error : 'unknown';
    const entry = ERRORS[code] || UNKNOWN;
    return { code: code, key: entry.key, retryable: entry.retryable, needsAttention: entry.needsAttention };
  }

  // Accepts the SpeechRecognitionErrorEvent itself, so callers do not have to
  // remember which property carries the code.
  function classifyEvent(event) {
    return classify(event && event.error);
  }

  return { classify: classifyEvent, classifyCode: classify, ERROR_CODES: Object.keys(ERRORS) };
});
