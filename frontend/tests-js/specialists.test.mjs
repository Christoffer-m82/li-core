import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFileSync } from 'node:fs';

const source = readFileSync(new URL('../static/assets/specialists.js', import.meta.url), 'utf8');
class Element {
  children = []; textContent = ''; value = ''; dataset = {}; attributes = {}; handlers = {};
  classes = new Set();
  classList = { toggle: (name, on) => on ? this.classes.add(name) : this.classes.delete(name) };
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children = items; this.textContent = ''; }
  setAttribute(key, value) { this.attributes[key] = value; }
  addEventListener(key, fn) { this.handlers[key] = fn; }
  click() { return this.handlers.click?.(); }
}
function setup(fetch) {
  const elements = new Map();
  const tabs = ['live','history','statistics'].map(name => {const el = new Element(); el.dataset.specialistTab = name; return el;});
  const document = { createElement: () => new Element(), querySelectorAll: () => tabs,
    querySelector(id) { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); } };
  const context = {}; vm.runInNewContext(source, context);
  const api = context.LiSpecialists, conversations = [];
  const view = api.create({ document, fetch, evidencePanel: () => null, onConversation: id => conversations.push(id) });
  return { api, view, conversations, tabs, get: id => document.querySelector(`#${id}`) };
}
const response = interactions => ({ ok: true, json: async () => ({ interactions }) });
const agent = { id: 'nora', name: 'Nora' };
const entry = { interaction_id: 'one', request_text: 'Compare notebooks', status: 'completed', elapsed_ms: 2000,
  started_at: '2026-09-01T10:00:00Z', outcome: { recommendation: 'Compare export options', findings: ['Portable text'], key_assumptions: ['Offline matters'], follow_up_questions: ['Which device?'] } };
const content = el => [el.textContent, ...el.children.map(content)].join(' ');

test('metrics use loaded completed durations only and never invent missing measurements', () => {
  const { api } = setup();
  assert.equal(api.summary([]).average, 'Not measured');
  const stats = api.summary([entry, {status:'active', elapsed_ms:90000}, {status:'completed'}, {status:'failed'}]);
  assert.equal(stats.average, '2.0s'); assert.equal(stats.total, 4); assert.equal(stats.failed, 1);
});
test('search matches requests, recommendations and findings, combined with status', () => {
  const { api } = setup();
  assert.equal(api.filter([entry], 'PORTABLE', 'completed').length, 1);
  assert.equal(api.filter([entry], 'export', 'failed').length, 0);
  assert.equal(api.filter([entry], 'notebooks').length, 1);
});
test('history renders structured results as text and distinguishes missing evidence', async () => {
  const malicious = {...entry, request_text:'<img src=x onerror=alert(1)>'};
  const app = setup(async () => response([malicious])); await app.view.open(agent);
  const text = content(app.get('specialist-record'));
  for (const expected of ['<img src=x', 'Offline matters', 'Which device?', 'Portable text', 'not recorded', 'not a verbatim']) assert.ok(text.includes(expected));
  assert.equal(app.get('specialist-history-list').children[0].attributes['aria-pressed'], 'true');
  assert.match(app.get('specialist-load-status').textContent, /Up to 50/);
});
test('filters clear the selected record when no result matches', async () => {
  const app = setup(async () => response([entry])); await app.view.open(agent);
  app.get('specialist-search').value = 'missing'; app.get('specialist-search').handlers.input();
  assert.match(content(app.get('specialist-record')), /No interactions match/);
  assert.equal(app.get('specialist-history-list').children.length, 0);
});
test('temporary content is not mistaken for a missing successful answer; active and failed are explicit', async () => {
  const app = setup(async () => response([{...entry, outcome:{temporary_context:{content_retained:false}}}, {...entry, status:'active', outcome:{}}]));
  await app.view.open(agent);
  assert.match(content(app.get('specialist-record')), /not retained/);
  assert.match(content(app.get('specialist-live')), /No response recorded yet/);
});
test('outage clears stale results and permits retry, not empty-history claims', async () => {
  let ok = true; const app = setup(async () => ok ? response([entry]) : {ok:false}); await app.view.open(agent);
  ok = false; await app.get('specialist-refresh').click();
  assert.match(app.get('specialist-load-status').textContent, /unavailable/);
  assert.equal(app.get('specialist-record').children.length, 0);
  assert.equal(app.get('specialist-refresh').disabled, false);
  ok = true; await app.get('specialist-refresh').click(); assert.equal(app.get('specialist-history-list').children.length, 1);
});
test('switching specialists ignores a late response; logout invalidates pending reads', async () => {
  const pending = []; const app = setup(() => new Promise(resolve => pending.push(resolve)));
  const first = app.view.open(agent), second = app.view.open({id:'sofia',name:'Sofia'});
  pending[1](response([{...entry, request_text:'Sofia request'}])); await second;
  pending[0](response([entry])); await first;
  assert.match(content(app.get('specialist-record')), /Sofia request/);
  assert.ok(!content(app.get('specialist-record')).includes('Compare notebooks'));
  const third = app.view.open(agent); app.view.clear(); pending[2](response([entry])); await third;
  assert.equal(app.get('specialist-record').children.length, 0);
});
test('conversation link exists only for a valid record identifier', async () => {
  const id = '00000000-0000-0000-0000-000000000001';
  const app = setup(async () => response([{...entry, conversation_id:id}])); await app.view.open(agent);
  const aside = app.get('specialist-record').children[1]; await aside.children.at(-1).click();
  assert.deepEqual(app.conversations, [id]);
});

test('Workspace is default; direct History entry survives loading and Refresh; Statistics switches independently', async () => {
  const app = setup(async () => response([entry]));
  await app.view.open(agent); assert.equal(app.tabs[0].attributes['aria-pressed'],'true');
  await app.view.open(agent,'history'); assert.equal(app.tabs[1].attributes['aria-pressed'],'true');
  await app.get('specialist-refresh').click(); assert.equal(app.tabs[1].attributes['aria-pressed'],'true');
  app.tabs[2].click(); assert.equal(app.tabs[2].attributes['aria-pressed'],'true');
  assert.equal(app.get('specialist-statistics').classes.has('hidden'),false);
  assert.equal(app.get('specialist-live').classes.has('hidden'),true);
  assert.match(content(app.get('specialist-statistics')),/Nora · Statistics/);
});

test('statistics preserve unknowns, use valid completed durations and explicit attribution only', () => {
  const {api}=setup(); const now = new Date('2026-09-04T12:00:00Z');
  const stats=api.statistics([
    {...entry,elapsed_ms:1000,group_mode:'solo',outcome:{validation:{used_in_final:true}}},
    {...entry,elapsed_ms:3000,group_mode:'multi'},
    {...entry,elapsed_ms:null},
    {status:'failed',elapsed_ms:99999},
    {status:'active',elapsed_ms:1},
    {status:'other'},
  ],0,now);
  assert.equal(stats.total,6); assert.equal(stats.average,2); assert.equal(stats.median,2);
  assert.equal(stats.timed,2); assert.equal(stats.completion,75);
  assert.equal(stats.attribution[0][1],1); assert.equal(stats.attribution[2][1],5);
  assert.equal(stats.collaboration[2][1],4); assert.equal(stats.statuses[3][1],1);
});

test('statistics period boundaries use UTC; missing/future timestamps are excluded, empty rates stay unknown', () => {
  const {api}=setup(); const now=new Date('2026-09-04T12:00:00Z');
  const stats=api.statistics([
    {...entry,started_at:'2026-08-29T00:00:00Z'},
    {...entry,started_at:'2026-08-28T23:59:59Z'},
    {...entry,started_at:'2026-09-05T00:00:00Z'},
    {...entry,started_at:null},
  ],7,now);
  assert.equal(stats.total,1); assert.equal(stats.activeDays,1); assert.equal(stats.undated,2);
  assert.equal(stats.activity.reduce((n,r)=>n+r[1],0),1);
  const empty=api.statistics([],0,now); assert.equal(empty.average,null); assert.equal(empty.completion,null);
});

test('statistics clear on logout and report failed refresh as unavailable, never zero', async () => {
  let ok=true; const app=setup(async () => ok ? response([entry]) : {ok:false});
  await app.view.open(agent,'statistics'); ok=false; await app.get('specialist-refresh').click();
  assert.match(content(app.get('specialist-statistics')),/Statistics unavailable/);
  app.view.clear(); assert.equal(app.get('specialist-statistics').children.length,0);
});

test('workspace activity updates statistics without switching tabs and ignores other specialists', async () => {
  const app=setup(async()=>response([])); await app.view.open(agent,'statistics');
  app.view.updateRecords('nora',[entry]);
  assert.match(content(app.get('specialist-statistics')),/1 of 1 loaded/);
  assert.equal(app.tabs[2].attributes['aria-pressed'],'true');
  app.view.updateRecords('sofia',[]);
  assert.match(content(app.get('specialist-statistics')),/1 of 1 loaded/);
  app.view.clear(); app.view.updateRecords('nora',[entry]);
  assert.equal(app.get('specialist-statistics').children.length,0);
});

test('a slow Refresh cannot replace newer post-send statistics', async () => {
  let finish; const app=setup(()=>new Promise(resolve=>{finish=resolve;}));
  const pending=app.view.open(agent,'statistics');
  app.view.updateRecords('nora',[entry]);
  finish(response([])); await pending;
  assert.match(content(app.get('specialist-statistics')),/1 of 1 loaded/);
  assert.equal(app.get('specialist-refresh').disabled,false);
});
