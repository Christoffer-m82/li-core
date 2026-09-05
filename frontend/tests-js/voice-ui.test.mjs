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
const profileSource = readFileSync(
  new URL('../static/assets/profile-photo.js', import.meta.url),
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
  contains(child) { return this.children.includes(child); }
  showModal() { this.open = true; }
  close() { this.open = false; this.events.get('close')?.(); }
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

function loadApp({ geolocation, storageBlocked = false, storageWriteFails = false,
  chatResponses = [], sessionValues = new Map(), uuidValues = ['test-id'] } = {}) {
  const elements = new Map();
  const getElement = (selector) => {
    if (!elements.has(selector)) elements.set(selector, new FakeElement());
    return elements.get(selector);
  };
  const timers = new Map();
  const windowEvents = new Map();
  let nextTimer = 1;
  const requests = [];
  const downloads = []; const revoked = [];

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
    body: new FakeElement(),
    createElement: () => new FakeElement(),
    createTextNode: (text) => ({ textContent: text }),
    documentElement: new FakeElement(),
    querySelector: getElement,
    querySelectorAll: (selector) => selector === '.li-orb' ? [getElement('#li-orb')] : [],
  };
  const localStorage = {
    values: new Map(),
    getItem(key) { return this.values.get(key) ?? null; },
    setItem(key, value) {
      if (storageWriteFails) throw new Error('Storage quota exceeded');
      this.values.set(key, String(value));
    },
  };
  const sessionStorage = {
    values: sessionValues,
    getItem(key) { return this.values.get(key) ?? null; },
    setItem(key, value) { this.values.set(key, String(value)); },
    removeItem(key) { this.values.delete(key); },
  };
  let uuidIndex = 0;
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
      if (chatResponses.length) return chatResponses.shift();
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
    addEventListener(name, handler) { windowEvents.set(name, handler); },
    clearTimeout,
    confirm: () => false,
    localStorage,
    sessionStorage,
    matchMedia: () => ({ matches: false, addEventListener() {} }),
    navigator: { language: 'en-GB', geolocation },
    setTimeout,
  };
  const context = {
    Blob,
    URL: { createObjectURL(blob) { downloads.push(blob); return 'blob:synthetic-theme'; }, revokeObjectURL(url) { revoked.push(url); } },
    console,
    crypto: { randomUUID: () => uuidValues[Math.min(uuidIndex++, uuidValues.length - 1)] },
    document,
    fetch,
    FormData: class { append() {} },
    Intl,
    localStorage,
    sessionStorage,
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
  if (storageBlocked) Object.defineProperty(context, 'localStorage', {
    get() { throw new Error('Storage access denied'); },
  });
  vm.runInNewContext(voiceSource, context);
  vm.runInNewContext(readFileSync(new URL('../static/assets/themes.js', import.meta.url), 'utf8'), context);
  vm.runInNewContext(profileSource, context);
  vm.runInNewContext(appSource, context);

  return {
    themes: window.LiThemes,
    themeLibrary: vm.runInNewContext('themeLibrary', context),
    downloads, revoked, localStorage,
    createSpecialistAvatar: vm.runInNewContext('createSpecialistAvatar', context),
    openSpecialistPortrait: vm.runInNewContext('openSpecialistPortrait', context),
    systemAgents: vm.runInNewContext('SYSTEM_AGENTS', context),
    setView: vm.runInNewContext('setView', context),
    sendMessage: vm.runInNewContext('sendMessage', context),
    document,
    elements,
    requests,
    setConversation(value) { vm.runInNewContext(`state.conversationId = ${JSON.stringify(value)}`, context); },
    setTemporaryUpload(value) { vm.runInNewContext(`state.temporaryUploadContext = ${JSON.stringify(value)}`, context); },
    async dispatchWindow(name, event = {}) {
      await windowEvents.get(name)?.(event);
      await this.settle();
    },
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

test('blocked storage does not prevent startup, theme selection, or voice controls', async () => {
  const app = loadApp({ storageBlocked: true });
  await app.settle();
  assert.ok(app.requests.some(request => request.url === '/api/session'));
  const forest = app.elements.get('#theme-library').children.find(button => button.dataset.themeChoice === 'forest');
  await forest.click();
  assert.equal(app.document.documentElement.dataset.theme, 'forest');
  await app.elements.get('#voice-output-toggle').click();
  assert.equal(app.elements.get('#voice-output-toggle').getAttribute('aria-pressed'), 'true');
  await app.elements.get('#voice-output-toggle').click();
  assert.equal(app.elements.get('#voice-output-toggle').getAttribute('aria-pressed'), 'false');
});

test('theme editor updates a custom theme without duplicating it; cancel preserves saved values', async () => {
  const app = loadApp(); await app.settle();
  await app.elements.get('#theme-copy-selected').click();
  app.elements.get('#theme-name').value = 'My theme';
  const submit = () => app.elements.get('#theme-editor').events.get('submit')({preventDefault(){}});
  submit(); assert.equal(app.themeLibrary.all().length, 4);
  assert.equal(app.elements.get('#theme-edit-selected').disabled, false);
  await app.elements.get('#theme-edit-selected').click();
  app.elements.get('#theme-name').value = 'Edited theme'; submit();
  assert.equal(app.themeLibrary.all().length, 4);
  assert.equal(app.themeLibrary.find('custom-test-id').name, 'Edited theme');
  app.elements.get('#theme-name').value = 'Discarded';
  await app.elements.get('#theme-editor-cancel').click();
  assert.equal(app.themeLibrary.find('custom-test-id').name, 'Edited theme');
  assert.equal(app.elements.get('#theme-editor-panel').open, false);
});

test('theme file import validates before opening a draft and does not save or call APIs', async () => {
  const app = loadApp(); await app.settle(); const count = app.requests.length;
  const input = app.elements.get('#theme-import');
  const text = app.themes.serialize(app.themes.builtins[2]);
  await input.events.get('change')({target:{files:[{size:text.length, text:async()=>text}],value:'selected'}});
  assert.equal(app.elements.get('#theme-name').value, 'Forest');
  assert.equal(app.themeLibrary.all().length,3);
  assert.equal(app.document.documentElement.dataset.theme,'dark');
  assert.equal(app.requests.length,count);
  assert.match(app.elements.get('#theme-transfer-status').textContent,/editor only/);
  const previous = app.elements.get('#theme-name').value;
  await input.events.get('change')({target:{files:[{size:100,text:async()=>'{broken'}],value:''}});
  assert.equal(app.elements.get('#theme-name').value,previous);
  assert.match(app.elements.get('#theme-transfer-status').textContent,/not valid JSON/);
});

test('oversized imports are rejected before reading and stale imports cannot replace edited drafts', async () => {
  const app = loadApp(); await app.settle(); const change = app.elements.get('#theme-import').events.get('change');
  let reads = 0;
  await change({target:{files:[{size:17000,text:async()=>{reads++;return '';}}],value:''}});
  assert.equal(reads,0); assert.match(app.elements.get('#theme-transfer-status').textContent,/16 KB/);
  let finish;
  const pending = change({target:{files:[{size:100,text:()=>new Promise(resolve=>{finish=resolve;})}],value:''}});
  await app.elements.get('#theme-copy-selected').click();
  app.elements.get('#theme-name').value = 'New draft';
  finish(app.themes.serialize(app.themes.builtins[2])); await pending;
  assert.equal(app.elements.get('#theme-name').value,'New draft');
  const pendingTyping = change({target:{files:[{size:100,text:()=>new Promise(resolve=>{finish=resolve;})}],value:''}});
  app.elements.get('#theme-editor').events.get('input')();
  finish(app.themes.serialize(app.themes.builtins[2])); await pendingTyping;
  assert.equal(app.elements.get('#theme-name').value,'New draft');
});

test('theme export downloads only appearance data and releases the temporary URL', async () => {
  const app = loadApp(); await app.settle(); const count=app.requests.length;
  await app.elements.get('#theme-export').click();
  assert.equal(app.downloads.length,1);
  const envelope=JSON.parse(await app.downloads[0].text());
  assert.equal(envelope.format,'li-appearance'); assert.equal(envelope.theme.name,'Dark');
  assert.equal(app.document.body.children[0].download,'li-appearance.json');
  assert.equal(app.requests.length,count);
  await app.runTimer(1000); assert.deepEqual(app.revoked,['blob:synthetic-theme']);
});

test('failed preference writes do not prevent disabling spoken responses', async () => {
  const app = loadApp({ storageWriteFails: true });
  await app.elements.get('#voice-output-toggle').click();
  assert.equal(app.elements.get('#voice-output-toggle').getAttribute('aria-pressed'), 'true');
  await app.elements.get('#voice-output-toggle').click();
  assert.equal(app.elements.get('#voice-output-toggle').getAttribute('aria-pressed'), 'false');
});

test('blocked storage does not falsely report a custom theme as saved', () => {
  const app = loadApp({ storageBlocked: true });
  const values = { name: 'My theme', mode: 'light', bg: '#ffffff', surface: '#ffffff',
    tile: '#ffffff', text: '#111111', muted: '#333333', accent: '#222222',
    onAccent: '#ffffff', font: 'modern', radius: '20' };
  for (const [key, value] of Object.entries(values)) app.document.querySelector(`#theme-${key}`).value = value;
  const originalCount = app.elements.get('#theme-library').children.length;
  app.elements.get('#theme-editor').events.get('submit')({ preventDefault() {} });
  assert.match(app.elements.get('#theme-editor-status').textContent, /cannot save/);
  assert.equal(app.elements.get('#theme-library').children.length, originalCount);
});

test('each specialist uses a local decorative portrait with initials fallback', () => {
  const app = loadApp();
  for (const id of ['sofia','marco','elena','amelia','freja','oliver','james','victor','nora','milo','iris','clara']) {
    const avatar = app.createSpecialistAvatar({id, name:id, initials:id.slice(0,2).toUpperCase()});
    assert.equal(avatar.getAttribute('aria-hidden'), 'true');
    assert.equal(avatar.children.length, 1);
    const image = avatar.children[0];
    assert.equal(image.src, `/assets/portraits/${id}.png`);
    assert.equal(image.alt, '');
    assert.equal(image.loading, 'lazy');
    image.events.get('error')();
    assert.equal(avatar.children[0].textContent, id.slice(0,2).toUpperCase());
  }
  const unknown = app.createSpecialistAvatar({id:'../private', name:'New specialist', initials:'NS'});
  assert.equal(unknown.children.length, 0);
  assert.equal(unknown.textContent, 'NS');
});

test('late Auto location callback cannot replace a subsequently selected theme', async () => {
  let locationCallback;
  const app = loadApp({ geolocation: { getCurrentPosition(callback) { locationCallback = callback; } } });
  const choices = app.elements.get('#theme-library').children;
  await choices.find(button => button.dataset.themeChoice === 'auto').click();
  await choices.find(button => button.dataset.themeChoice === 'forest').click();
  locationCallback({ coords: { latitude: 52, longitude: 13 } });
  assert.equal(app.document.documentElement.dataset.theme, 'forest');
});

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
    turn_id: 'test-id',
    conversation_id: null,
    temporary_upload_context: null,
  });
  assert.equal('audio' in JSON.parse(chatRequests[0].options.body), false);
});

test('failed main-chat retry reuses the turn and does not duplicate the owner bubble', async () => {
  const app = loadApp({ chatResponses: [
    { ok: false, status: 503, json: async () => ({ detail: { message: 'Try safely.' } }) },
    { ok: true, status: 200, json: async () => ({
      conversation_id: 'conversation-1', response: 'Recovered.', artifacts: [],
      action_intents: [], turn_state: 'completed_replay',
    }) },
  ] });

  await app.sendMessage('Please add this once.');
  await app.sendMessage('Please add this once.');

  const requests = app.requests.filter((request) => request.url === '/api/chat');
  assert.equal(requests.length, 2);
  assert.equal(JSON.parse(requests[0].options.body).turn_id, 'test-id');
  assert.equal(JSON.parse(requests[1].options.body).turn_id, 'test-id');
  assert.equal(
    app.elements.get('#messages').children.filter((entry) => entry.className === 'message user').length,
    1,
  );
});

test('edited main-chat envelope gets a new turn identity', async () => {
  const app = loadApp({
    uuidValues: ['turn-one', 'turn-two'],
    chatResponses: [
      { ok: false, status: 503, json: async () => ({ detail: { message: 'Try safely.' } }) },
      { ok: true, status: 200, json: async () => ({
        conversation_id: 'conversation-1', response: 'New request completed.', artifacts: [],
        action_intents: [], turn_state: 'completed',
      }) },
    ],
  });
  await app.sendMessage('First request.');
  app.setConversation('different-conversation');
  app.setTemporaryUpload('different attachment');
  await app.sendMessage('Edited request.');
  const bodies = app.requests.filter(({ url }) => url === '/api/chat')
    .map(({ options }) => JSON.parse(options.body));
  assert.equal(bodies[0].turn_id, 'turn-one');
  assert.equal(bodies[1].turn_id, 'turn-two');
});

test('main-chat retry identity survives a page reload without storing message content', async () => {
  const sessionValues = new Map();
  const first = loadApp({
    sessionValues, uuidValues: ['stable-turn'],
    chatResponses: [
      { ok: false, status: 503, json: async () => ({ detail: { message: 'Try safely.' } }) },
    ],
  });
  await first.sendMessage('Private synthetic message.');
  assert.equal([...sessionValues.values()].some((value) => value.includes('Private synthetic')), false);

  const second = loadApp({ sessionValues, uuidValues: ['should-not-be-used'] });
  await second.sendMessage('Private synthetic message.');
  const body = JSON.parse(second.requests.find(({ url }) => url === '/api/chat').options.body);
  assert.equal(body.turn_id, 'stable-turn');
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

test('system-agent cards use selected portraits and open read-only profiles without API calls', async () => {
  const app = loadApp(); await app.settle();
  const requests = app.requests.length;
  assert.equal(app.elements.has('#home-system-agents'), false);
  for (const selector of ['#directory-system-agents', '#backend-system-agents']) {
    const cards = app.elements.get(selector).children;
    assert.equal(cards.length, 3);
    for (const [i, card] of cards.entries()) {
      const item = app.systemAgents[i];
      assert.equal(card.children[0].children[0].src, `/assets/portraits/${item.id}.png`);
      card.click();
      const profile = app.elements.get('#system-agent-heading').children[0];
      assert.equal(profile.children[1].children[0].textContent, item.name);
      assert.equal(profile.children[1].children[1].textContent, item.role);
      assert.equal(app.elements.get('#system-agent-boundary').textContent, item.boundary);
      profile.children[0].click();
      assert.equal(app.elements.get('#specialist-portrait-name').textContent, item.name);
      app.elements.get('#specialist-portrait-close').click();
    }
  }
  assert.equal(app.requests.length, requests);
});

test('portrait dialog uses originals, ignores stale image events, and closes on navigation', async () => {
  const app = loadApp();
  await app.settle();
  const get = (id) => app.document.querySelector(`#specialist-portrait-${id}`);
  const initialRequests = app.requests.length;
  app.openSpecialistPortrait({ id: 'elena', name: 'Elena', role: 'Nutrition & Cooking' });
  assert.equal(get('dialog').open, true);
  assert.equal(get('name').textContent, 'Elena');
  assert.equal(get('role').textContent, 'Nutrition & Cooking');
  const oldImage = get('image').children[0];
  assert.equal(oldImage.src, '/assets/portraits/elena.png');
  assert.equal(oldImage.width, 1254);
  assert.equal(get('original').href, oldImage.src);
  oldImage.events.get('load')();
  assert.equal(get('status').textContent, '');
  get('close').click();
  assert.equal(get('dialog').open, false);
  assert.equal(get('image').children.length, 0);
  app.openSpecialistPortrait({ id: '../../unknown', name: 'Unknown', role: 'Unknown' });
  assert.equal(get('dialog').open, false);
  app.openSpecialistPortrait({ id: 'nora', name: 'Nora', role: 'Research' });
  oldImage.events.get('error')();
  assert.equal(get('status').textContent, 'Loading portrait…');
  const currentImage = get('image').children[0];
  currentImage.events.get('error')();
  assert.equal(currentImage.hidden, true);
  assert.match(get('status').textContent, /could not be loaded/);
  assert.equal(app.requests.length, initialRequests);
  app.setView('home');
  assert.equal(get('dialog').open, false);
});

test('install prompt is offered once and reports accepted installation', async () => {
  const app = loadApp();
  let prevented = false;
  let prompts = 0;
  const installEvent = {
    preventDefault() { prevented = true; },
    prompt: async () => { prompts += 1; },
    userChoice: Promise.resolve({ outcome: 'accepted' }),
  };

  await app.dispatchWindow('beforeinstallprompt', installEvent);
  const installButton = app.elements.get('#install-app');
  assert.equal(prevented, true);
  assert.equal(installButton.classList.contains('hidden'), false);
  assert.equal(app.elements.get('#install-status').textContent, 'Li is ready to install from this browser.');

  await installButton.click();
  await app.settle();

  assert.equal(prompts, 1);
  assert.equal(installButton.classList.contains('hidden'), true);
  assert.equal(app.elements.get('#install-status').textContent, 'Li installation started.');

  await app.dispatchWindow('appinstalled');
  assert.equal(app.elements.get('#install-status').textContent, 'Li is installed on this device.');
});
