import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const source = readFileSync(
  new URL('../static/assets/voice.js', import.meta.url),
  'utf8',
);

function loadVoice(overrides = {}) {
  const window = {
    navigator: { language: 'en-US' },
    setTimeout,
    clearTimeout,
    ...overrides,
  };
  vm.runInNewContext(source, { window });
  return window.LiVoice;
}

test('recognition resolves one trimmed final transcript and reports state', async () => {
  let recognition;
  class FakeRecognition {
    constructor() { recognition = this; }
    start() {
      this.onstart?.();
      const result = [{ transcript: '  book dentist  ', confidence: 0.92 }];
      result.isFinal = true;
      queueMicrotask(() => this.onresult({ resultIndex: 0, results: [result] }));
    }
    abort() {}
  }
  const voice = loadVoice({ SpeechRecognition: FakeRecognition });
  const states = [];
  const interim = [];
  const provider = new voice.BrowserVoiceTranscriptionProvider({ language: 'sv-SE' });

  const transcript = await provider.start({
    onState: (state) => states.push(state),
    onInterim: (value) => interim.push(value),
  });

  assert.equal(transcript, 'book dentist');
  assert.deepEqual(states, ['listening']);
  assert.deepEqual(interim, ['book dentist']);
  assert.equal(recognition.lang, 'sv-SE');
  assert.equal(recognition.interimResults, true);
  assert.equal(recognition.continuous, false);
  assert.equal(recognition.maxAlternatives, 1);
});

test('cancellation aborts recognition and settles the pending promise', async () => {
  let recognition;
  class FakeRecognition {
    constructor() { recognition = this; }
    start() {}
    abort() { this.aborted = true; }
  }
  const voice = loadVoice({ SpeechRecognition: FakeRecognition });
  const provider = new voice.BrowserVoiceTranscriptionProvider();
  const pending = provider.start();

  provider.cancel();

  await assert.rejects(pending, { message: 'cancelled' });
  assert.equal(recognition.aborted, true);
});

test('a late callback from a cancelled session cannot disturb its replacement', async () => {
  const recognitions = [];
  class FakeRecognition {
    constructor() { recognitions.push(this); }
    start() {}
    abort() {
      const oldError = this.onerror;
      queueMicrotask(() => oldError?.({ error: 'aborted' }));
    }
  }
  const voice = loadVoice({ SpeechRecognition: FakeRecognition });
  const provider = new voice.BrowserVoiceTranscriptionProvider();
  const first = provider.start();
  const second = provider.start();

  await assert.rejects(first, { message: 'cancelled' });
  await new Promise((resolve) => queueMicrotask(resolve));
  const result = [{ transcript: 'replacement', confidence: 0.9 }];
  result.isFinal = true;
  recognitions[1].onresult({ resultIndex: 0, results: [result] });

  assert.equal(await second, 'replacement');
});

test('timeout wins even when abort synchronously emits an error', async () => {
  class FakeRecognition {
    start() {}
    abort() { this.onerror?.({ error: 'aborted' }); }
  }
  const voice = loadVoice({ SpeechRecognition: FakeRecognition });
  const provider = new voice.BrowserVoiceTranscriptionProvider({ timeoutMs: 1 });

  await assert.rejects(provider.start(), { message: 'timeout' });
});

test('provider surfaces permission and no-speech failures', async () => {
  class DeniedRecognition {
    start() { queueMicrotask(() => this.onerror({ error: 'not-allowed' })); }
    abort() {}
  }
  let voice = loadVoice({ SpeechRecognition: DeniedRecognition });
  await assert.rejects(
    new voice.BrowserVoiceTranscriptionProvider().start(),
    { message: 'not-allowed' },
  );

  class SilentRecognition {
    start() { queueMicrotask(() => this.onend()); }
    abort() {}
  }
  voice = loadVoice({ SpeechRecognition: SilentRecognition });
  await assert.rejects(
    new voice.BrowserVoiceTranscriptionProvider().start(),
    { message: 'no-speech' },
  );
});

test('speech synthesis selects the matching voice and remains cancellable', () => {
  const spoken = [];
  let cancellations = 0;
  class FakeUtterance {
    constructor(text) { this.text = text; }
  }
  const synthesis = {
    getVoices: () => [{ lang: 'en-GB' }, { lang: 'sv-SE' }],
    cancel: () => { cancellations += 1; },
    speak: (utterance) => {
      spoken.push(utterance);
      utterance.onstart?.();
      utterance.onend?.();
    },
  };
  const voice = loadVoice({
    speechSynthesis: synthesis,
    SpeechSynthesisUtterance: FakeUtterance,
  });
  const states = [];
  const provider = new voice.BrowserVoiceSynthesisProvider();

  assert.equal(provider.speak('Hej', 'sv-SE', {
    onStart: () => states.push('started'),
    onEnd: () => states.push('ended'),
  }), true);
  assert.equal(spoken[0].text, 'Hej');
  assert.equal(spoken[0].lang, 'sv-SE');
  assert.equal(spoken[0].voice.lang, 'sv-SE');
  assert.deepEqual(states, ['started', 'ended']);
  assert.equal(cancellations, 1);

  provider.stop();
  assert.equal(cancellations, 2);
});

test('language detection supports Swedish signals and safe fallback', () => {
  const voice = loadVoice();

  assert.equal(voice.detectLanguage('Tack för hjälpen'), 'sv-SE');
  assert.equal(voice.detectLanguage('Thank you', 'en-GB'), 'en-US');
  assert.equal(voice.detectLanguage('', 'sv-FI'), 'sv-SE');
  assert.equal(voice.capability.rawAudioRetention, 'none');
});
