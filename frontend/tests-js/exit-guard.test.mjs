import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFileSync } from 'node:fs';

test('warning is conditional, deduplicated, and does not act on stale clean state', () => {
  const context = {};
  vm.runInNewContext(readFileSync(new URL('../static/assets/exit-guard.js', import.meta.url), 'utf8'), context);
  const listeners = new Map(); let added = 0, removed = 0, pending = false;
  const guard = context.LiExitGuard.create({ window: {
    addEventListener(name, handler) { assert.equal(name, 'beforeunload'); listeners.set(name, handler); added++; },
    removeEventListener(name, handler) { assert.equal(listeners.get(name), handler); listeners.delete(name); removed++; },
  }, hasPendingWork: () => pending });
  guard.refresh(); assert.equal(added, 0);
  pending = true; guard.refresh(); guard.refresh(); assert.equal(added, 1);
  let prevented = 0; const event = { preventDefault() { prevented++; } };
  listeners.get('beforeunload')(event);
  assert.equal(prevented, 1); assert.equal(event.returnValue, true);
  pending = false;
  listeners.get('beforeunload')({ preventDefault() { throw new Error('Clean page must leave normally'); } });
  guard.refresh(); assert.equal(removed, 1); assert.equal(listeners.size, 0);
});
