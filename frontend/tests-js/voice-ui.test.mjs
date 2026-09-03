import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const voiceSource = readFileSync(
  new URL('../static/assets/voice.js', import.meta.url),
  'utf8',
);
const appSource = readFileSync(
  new URL('../static/assets/app.js', import.meta.url),
  'utf8',
);

class FakeElement {
  constructor() {
    this.attributes = new Map();
    this.children = [];
    const classes = new Set();
    this.classList = {
      add: (...names) => names.forEach((name) => classes.add(name)),
      remove: (...names) => names.forEach((name) => classes.delete(name)),
      contains: (name) => classes.has(name),
      toggle: (name, force) => {
        const enabled = force === undefined ? !classes.has(name) : force;
        if (enabled) classes.add(name); else classes.delete(name);
        return enabled;
      },
    };
    this.dataset = {};
    this.disabled = false;
    this.events = new Map();
    this.options = [];
    this.style = { setProperty() {} };
    this.textContent = '';
    this.value = '';
  }

  addEventListener(name, handler) { this.events.set(name, handler); }
  append(...children) { this.children.push(...children); }
  appendChild(child) { this.children.push(child); return child; }
  before() {}
  click() { return this.events.get('click')?.({ target: this, preventDefault() {} }); }
  focus() {}
  getAttribute(name) { return this.attributes.get(name) ?? null; }
  hasAttribute(name) { return this.attributes.has(name); }
  querySelector() { return null; }
  querySelectorAll() { return []; }
  remove() {}
  replaceChildren(...children) { this.children = children; }
  scrollTo() {}
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
}

function loadApp() {
  const elements = new Map();
  const getElement = (selector) => {
    if (!elements.has(selector)) elements.set(selector, new FakeElement());
    return elements.get(selector);
  };
  const timers = new Map();
  let nextTimer = 1;
  const requests = [];

  class FakeRecognition {
    start() {
      queueMicrotask(() => {
        this.onstart?.();
        const result = [{ transcript: ' check tomorrow calendar ', confidence: 0.96 }];
        result.isFinal = true;
        this.onresult?.({ resultIndex: 0, results: [result] });
      });
    }
    abort() { this.aborted = true; }
  }

  const document = {
    createElement: () => new FakeElement(),
    createTextNode: (text) => ({ textContent: text }),
    documentElement: new FakeElement(),
    querySelector: getElement,
    querySelectorAll: (selector) => selector === '.li-orb' ? [getElement('#li-orb')] : [],
  };
  const localStorage = {
    values: new Map(),
    getItem(key) { return this.values.get(key) ?? null; },
    setItem(key, value) { this.values.set(key, String(value)); },
  };
  const setTimeout = (callback, delay) => {
    const id = nextTimer++;
    timers.set(id, { callback, delay });
    return id;
  };
  const clearTimeout = (id) => timers.delete(id);
  const fetch = async (url, options = {}) => {
    requests.push({ url, options });
    if (url === '/api/session') return { ok: false, status: 401, json: async () => ({}) };
    if (url === '/api/chat') {
      return {
        ok: true,
        status: 200,
        json: async () => ({
          conversation_id: 'conversation-1',
          response: 'Your calendar is clear.',
          artifacts: [],
          action_intents: [],
        }),
      };
    }
    if (url === '/api/specialists') {
      return { ok: true, status: 200, json: async () => ({ specialists: [] }) };
    }
    return { ok: false, status: 503, json: async () => ({}) };
  };
  const window = {
    SpeechRecognition: FakeRecognition,
    addEventListener() {},
    clearTimeout,
    confirm: () => false,
    localStorage,
    matchMedia: () => ({ matches: false, addEventListener() {} }),
    navigator: { language: 'en-GB' },
    setTimeout,
  };
  const context = {
    console,
    crypto: { randomUUID: () => 'test-id' },
    document,
    fetch,
    FormData: class { append() {} },
    Intl,
    localStorage,
    matchMedia: window.matchMedia,
    navigator: window.navigator,
    Option: class {},
    queueMicrotask,
    setInterval: () => 1,
    clearInterval() {},
    setTimeout,
    clearTimeout,
    window,
  };
  vm.runInNewContext(voiceSource, context);
  vm.runInNewContext(appSource, context);

  return {
    elements,
    requests,
    async settle() {
      await new Promise((resolve) => queueMicrotask(resolve));
      await new Promise((resolve) => queueMicrotask(resolve));
    },
    async runTimer(delay) {
      const entry = [...timers.entries()].find(([, timer]) => timer.delay === delay);
      assert.ok(entry, `expected a ${delay} ms timer`);
      timers.delete(entry[0]);
      entry[1].callback();
      await this.settle();
    },
    hasTimer(delay) { return [...timers.values()].some((timer) => timer.delay === delay); },
  };
}

test('microphone interaction sends one visible transcript through normal chat', async () => {
  const app = loadApp();
  const microphone = app.elements.get('#microphone-button');

  await microphone.click();
  await app.settle();

  assert.equal(app.elements.get('#message-input').value, 'check tomorrow calendar');
  assert.match(app.elements.get('#voice-status-text').textContent, /sending shortly/);
  assert.equal(microphone.getAttribute('aria-pressed'), 'false');

  await app.runTimer(1200);

  const chatRequests = app.requests.filter((request) => request.url === '/api/chat');
  assert.equal(chatRequests.length, 1);
  assert.deepEqual(JSON.parse(chatRequests[0].options.body), {
    message: 'check tomorrow calendar',
    conversation_id: null,
    temporary_upload_context: null,
  });
  assert.equal('audio' in JSON.parse(chatRequests[0].options.body), false);
});

test('cancel after transcription prevents the pending chat request', async () => {
  const app = loadApp();

  await app.elements.get('#microphone-button').click();
  await app.settle();
  await app.elements.get('#voice-cancel').click();

  assert.equal(app.elements.get('#microphone-button').getAttribute('aria-pressed'), 'false');
  assert.equal(app.elements.get('#voice-status').classList.contains('hidden'), true);
  assert.equal(app.hasTimer(1200), false);
  assert.equal(app.requests.some((request) => request.url === '/api/chat'), false);
});
