import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';

const context = {};
vm.runInNewContext(readFileSync(new URL('../static/assets/themes.js', import.meta.url), 'utf8'), context);
const themes = context.LiThemes;
const forest = themes.builtins.find(theme => theme.id === 'forest');
function storage(initial = null) {
  return { value: initial, getItem() { return this.value; }, setItem(key, value) { this.value = value; } };
}

test('every built-in has readable text and button contrast', () => {
  for (const theme of themes.builtins) assert.equal(themes.validate(theme).name, theme.name);
});
test('custom appearances persist without a fixed theme count or changing built-ins', () => {
  const saved = storage();
  const library = themes.library(saved);
  for (let i = 0; i < 150; i++) library.save({ ...forest, name: `Theme ${i}` }, `custom-${i}`);
  assert.equal(themes.library(saved).all().length, 153);
  assert.equal(library.find('forest').name, 'Forest');
  assert.equal(library.find('removed-theme').id, 'dark');
  assert.throws(() => library.save(forest, 'dark'));
  assert.throws(() => library.save(forest, 'custom-1'));
});
test('rejects executable CSS, unsupported fonts and unreadable palettes', () => {
  for (const draft of [{ ...forest, accent: 'url(https://example.com)' }, { ...forest, font: 'url(evil)' }, { ...forest, text: forest.bg }, { ...forest, onAccent: forest.accent }]) {
    assert.throws(() => themes.validate(draft));
  }
  const safe = themes.validate({ ...forest, script: 'alert(1)', css: 'display:none' });
  assert.equal(safe.script, undefined);
  assert.equal(safe.css, undefined);
});
test('corrupt storage falls back and failed writes do not claim a saved theme', () => {
  assert.equal(themes.library(storage('{broken')).all().length, 3);
  const library = themes.library({ getItem() { throw Error('blocked'); }, setItem() { throw Error('quota'); } });
  assert.throws(() => library.save(forest, 'custom-test'), /cannot save/);
  assert.equal(library.all().length, 3);
});
test('theme application changes only appearance tokens and browser chrome', () => {
  const tokens = new Map();
  const root = { style: { setProperty: (key, value) => tokens.set(key, value) }, dataset: {} };
  const meta = {};
  themes.apply(forest, root, meta);
  assert.equal(root.dataset.theme, 'forest');
  assert.equal(meta.content, '#F6F4EF');
  assert.equal(tokens.get('--purple'), '#1E5B44');
  assert.equal(tokens.get('--card-radius'), '20px');
  themes.apply(themes.builtins[0], root, meta);
  assert.equal(root.dataset.theme, 'dark');
  assert.equal(tokens.get('--sidebar-surface'), '#070812');
});

test('editing a custom theme persists in place and never changes built-ins', () => {
  const saved = storage(); const library = themes.library(saved);
  library.save(forest, 'custom-edit');
  library.update({ ...forest, name: 'Edited', radius: '28' }, 'custom-edit');
  assert.equal(library.all().length, 4);
  assert.equal(themes.library(saved).find('custom-edit').name, 'Edited');
  assert.equal(library.find('forest').radius, '20');
  assert.throws(() => library.update(forest, 'forest'), /Only an existing custom/);
  assert.throws(() => library.update(forest, 'custom-missing'));
});

test('invalid edits and failed writes leave the saved theme untouched', () => {
  const saved = storage(); const library = themes.library(saved);
  library.save(forest, 'custom-edit'); const before = saved.value;
  assert.throws(() => library.update({ ...forest, text: forest.bg }, 'custom-edit'));
  saved.setItem = () => { throw Error('quota'); };
  assert.throws(() => library.update({ ...forest, name: 'Failed' }, 'custom-edit'), /previous theme is unchanged/);
  assert.equal(saved.value, before); assert.equal(library.find('custom-edit').name, forest.name);
});

test('portable appearance round trip has only validated settings, no IDs or extras', () => {
  const text = themes.serialize({ ...forest, id: 'custom-private', token: 'not-exported', css: 'not-exported' });
  const envelope = JSON.parse(text);
  assert.equal(envelope.version, 1); assert.equal(envelope.format, 'li-appearance');
  assert.equal(envelope.theme.id, undefined); assert.equal(envelope.theme.token, undefined);
  assert.equal(envelope.theme.css, undefined);
  assert.equal(JSON.stringify(themes.parseTransfer(text)), JSON.stringify(themes.validate(forest)));
});

test('import rejects unknown versions, fields, malformed, oversized and unsafe content', () => {
  const theme = themes.validate(forest);
  const good = { format: 'li-appearance', version: 1, theme };
  for (const bad of [null, [], {}, { ...good, version: 2 }, { ...good, script: 'evil' },
    { ...good, theme: { ...theme, css: 'url(evil)' } }, { ...good, theme: { ...theme, id: 'dark' } },
    { ...good, theme: { ...theme, accent: 'url(evil)' } }, { ...good, theme: { ...theme, text: theme.bg } }]) {
    assert.throws(() => themes.parseTransfer(JSON.stringify(bad)));
  }
  assert.throws(() => themes.parseTransfer('{bad'));
  assert.throws(() => themes.parseTransfer(' '.repeat(themes.transferLimit + 1)), /16 KB/);
  assert.throws(() => themes.parseTransfer(JSON.stringify(good).replace('"theme":', '"__proto__":{},"theme":')));
});

test('importing duplicate names adds new custom IDs without overwriting', () => {
  const library = themes.library(storage()); const text = themes.serialize(forest);
  library.save(themes.parseTransfer(text), 'custom-one');
  library.save(themes.parseTransfer(text), 'custom-two');
  assert.equal(library.all().length, 5);
  assert.equal(library.find('forest').id, 'forest');
});
