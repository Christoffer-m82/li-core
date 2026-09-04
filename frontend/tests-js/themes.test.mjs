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
