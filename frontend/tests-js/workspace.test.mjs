import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFileSync } from 'node:fs';
const source = readFileSync(new URL('../static/assets/workspace.js', import.meta.url), 'utf8');
class Element {
  children = []; textContent = ''; value = ''; handlers = {}; attributes = {}; scrollTop = 0; scrollHeight = 800; clientHeight = 400;
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children = items; this.textContent = ''; }
  setAttribute(k, v) { this.attributes[k] = v; }
  addEventListener(k, fn) { this.handlers[k] = fn; }
}
const id = '00000000-0000-0000-0000-000000000001';
const agent = { id: 'nora', name: 'Nora' };
const reply = data => ({ ok: true, json: async () => data });
const content = el => [el.textContent, ...el.children.map(content)].join(' ');
function setup(fetch = async () => reply({messages:[]}), options = {}) {
  const all = [], root = new Element();
  const document = { querySelector: () => root, createElement(tag) { const el = new Element(); el.tag = tag; all.push(el); return el; } };
  let turn = 0;
  const context = { FormData: class { append() {} },
    crypto: { randomUUID: () => `00000000-0000-0000-0000-${String(++turn).padStart(12,'0')}` } };
  vm.runInNewContext(source, context);
  const api = context.LiWorkspace, view = api.create({document, fetch, ...options});
  return { api, view, root, get: id => all.find(e => e.id === id),
    status: () => all.find(e => e.className === 'workspace-status').textContent,
    log: () => all.find(e => e.className === 'workspace-log'),
    send: () => all.find(e => e.tag === 'form').handlers.submit({preventDefault(){}}) };
}
test('timeline orders actual senders; never invents a Li routing message or repeats owner request', () => {
  const {api} = setup();
  const rows = api.timeline([
    {role:'assistant',content:'Li synthesis',created_at:'2026-09-04T10:02:00Z'},
    {role:'user',content:'Owner request',created_at:'2026-09-04T10:00:00Z'},
  ], [{conversation_id:id, request_text:'Not a Li message', completed_at:'2026-09-04T10:01:00Z', outcome:{recommendation:'Specialist advice'}}], id);
  assert.deepEqual(Array.from(rows, r => r.sender), ['owner','specialist','li']);
  assert.equal(rows.length,3); assert.ok(!JSON.stringify(rows).includes('Not a Li message'));
});
test('other cases and system messages excluded; temporary omissions are events, not fabricated speech', () => {
  const rows = setup().api.timeline([{role:'system',content:'hidden'}], [
    {conversation_id:'other',outcome:{recommendation:'Unrelated'}},
    {conversation_id:id,outcome:{temporary_context:{content_retained:false}}},
  ], id);
  assert.equal(rows.length,1); assert.equal(rows[0].sender,'event'); assert.match(rows[0].body,/not retained/);
});
test('new workspace sends exact message with selected recipient and uses returned saved conversation', async () => {
  const calls = []; const app = setup(async (url, options) => {
    calls.push([url,options]);
    if (url === '/api/chat') return reply({conversation_id:id,response:'Reply'});
    if (url.includes('/interactions')) return reply({interactions:[]});
    return reply({messages:[{role:'user',content:'Hello'},{role:'assistant',content:'Reply'}]});
  });
  await app.view.open(agent, []); app.get('workspace-input').value = 'Hello'; app.get('workspace-recipient').value = 'specialist'; await app.send();
  const body = JSON.parse(calls[0][1].body);
  assert.equal(body.workspace_specialist,'nora'); assert.equal(body.workspace_recipient,'specialist');
  assert.equal(body.message,'Hello'); assert.equal(body.conversation_id,null);
  assert.ok(validIdForTest(body.turn_id));
  assert.equal(app.get('workspace-input').value,''); assert.match(content(app.log()),/Reply/);
  assert.match(app.status(),/saved/);
});

const validIdForTest = value => typeof value === 'string' && /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(value);

test('failed workspace retry reuses the same stable turn identity', async () => {
  const ids=[]; let succeed=false;
  const app=setup(async (url,options) => {
    if(url==='/api/chat') { ids.push(JSON.parse(options.body).turn_id); return succeed
      ? reply({conversation_id:id,response:'Recovered',conversation_history_error:'not saved'}) : {ok:false}; }
    return reply({interactions:[]});
  });
  await app.view.open(agent,[]); app.get('workspace-input').value='Retry me'; await app.send();
  succeed=true; await app.send();
  assert.equal(ids.length,2); assert.equal(ids[0],ids[1]);
});
test('failed send preserves draft and suppresses duplicate concurrent submissions', async () => {
  let finish, requests=0; const app = setup(() => {requests++; return new Promise(resolve => {finish=resolve;});});
  await app.view.open(agent, []); app.get('workspace-input').value='Keep draft';
  const pending=app.send(); await app.send(); assert.equal(requests,1);
  finish({ok:false}); await pending; assert.equal(app.get('workspace-input').value,'Keep draft'); assert.match(app.status(),/duplicate/);
});
test('switching specialists and clearing ignore late reads and replies', async () => {
  let finish; const app=setup(() => new Promise(resolve => {finish=resolve;}));
  const old=app.view.open(agent,[{conversation_id:id}]);
  await app.view.open({id:'sofia',name:'Sofia'},[]);
  finish(reply({messages:[{role:'assistant',content:'Old private reply'}]})); await old;
  assert.ok(!content(app.log()).includes('Old private')); assert.match(content(app.log()),/Sofia/);
  app.get('workspace-input').value='Send'; const pending=app.send(); app.view.clear();
  finish(reply({conversation_id:id,response:'Stale'})); await pending;
  assert.ok(!content(app.log()).includes('Stale')); assert.equal(app.get('workspace-input').value,'');
});
test('unavailable history blocks sending into an unverified case', async () => {
  let requests=0; const app=setup(async () => {requests++;return {ok:false};});
  await app.view.open(agent,[{conversation_id:id}]); app.get('workspace-input').value='No'; await app.send();
  assert.equal(requests,1); assert.match(app.status(),/unavailable/);
});
test('returned reply survives failed refresh and persistence errors', async () => {
  for (const historyError of [null,'not saved']) {
    const app=setup(async url => url === '/api/chat' ? reply({conversation_id:id,response:'Received',conversation_history_error:historyError}) : url.includes('/interactions') ? reply({interactions:[]}) : {ok:false});
    await app.view.open(agent,[]); app.get('workspace-input').value='Hi'; await app.send();
    assert.match(content(app.log()),/Received/); assert.match(app.status(),historyError ? /not fully saved/ : /refresh failed/);
  }
});
test('temporary attachments pass only successful bounded analysis; unsupported images are not falsely attached', async () => {
  let analysis=null, payload; const app=setup(async (url,options) => {
    if(url==='/api/uploads') return reply({analysis_text:analysis});
    if(url==='/api/chat') {payload=JSON.parse(options.body);return reply({conversation_id:id,response:'OK',conversation_history_error:'failed'});}
    return reply({interactions:[]});
  });
  await app.view.open(agent,[]); const file=app.get('workspace-file'); file.files=[{name:'note.txt',size:12}];
  await file.handlers.change(); assert.match(app.status(),/cannot be analysed/);
  analysis='Safe text'; await file.handlers.change(); assert.match(app.status(),/ready/);
  app.get('workspace-input').value='Discuss'; await app.send(); assert.match(payload.temporary_upload_context,/Safe text/);
  analysis='a'.repeat(6001); await file.handlers.change(); assert.match(app.status(),/too long/);
});
test('message content stays text and reading position is retained during refresh', async () => {
  const app=setup(async () => reply({messages:[{role:'user',content:'<img onerror=alert(1)>'}]}));
  await app.view.open(agent,[{conversation_id:id}]); app.log().scrollTop=50;
  await app.view.refresh([{conversation_id:id}]);
  assert.match(content(app.log()),/<img onerror/); assert.equal(app.log().scrollTop,50);
});

test('a conversation loaded in a hidden tab opens at the latest message only once', async () => {
  const app=setup(); app.log().clientHeight=0; app.log().scrollHeight=0;
  await app.view.open(agent,[]);
  app.log().clientHeight=400; app.log().scrollHeight=1200;
  app.view.show(); assert.equal(app.log().scrollTop,1200);
  app.log().scrollTop=100; app.view.show(); assert.equal(app.log().scrollTop,100);
});

test('successful send publishes verified activity for the current specialist', async () => {
  const updates=[];
  const app=setup(async url => url==='/api/chat'
    ? reply({conversation_id:id,response:'Reply',conversation_history_error:'not saved'})
    : reply({interactions:[{conversation_id:id,status:'completed'}]}),
    {onActivity:(agentId,records)=>updates.push([agentId,records])});
  await app.view.open(agent,[]); app.get('workspace-input').value='Hello'; await app.send();
  assert.equal(updates.length,1); assert.equal(updates[0][0],'nora'); assert.equal(updates[0][1][0].status,'completed');
});

test('late post-send activity never publishes after switching specialists', async () => {
  let finish; const updates=[];
  const app=setup(async url=>url==='/api/chat'
    ? reply({conversation_id:id,response:'Reply'})
    : new Promise(resolve=>{finish=resolve;}), {onActivity:(...args)=>updates.push(args)});
  await app.view.open(agent,[]); app.get('workspace-input').value='Hello'; const pending=app.send();
  while (!finish) await Promise.resolve();
  await app.view.open({id:'sofia',name:'Sofia'},[]);
  finish(reply({interactions:[{conversation_id:id,status:'completed'}]})); await pending;
  assert.equal(updates.length,0); assert.match(content(app.log()),/Sofia/);
});
test('owner avatar uses CM and specialist colour scope follows the selected agent', async () => {
  const app = setup(async () => reply({messages:[{role:'user',content:'Hello'}]}), {owner:()=>({name:'Christoffer Melldén'})});
  await app.view.open({id:'marco',name:'Marco'},[{conversation_id:id}]);
  assert.equal(app.root.attributes['data-chat-specialist'],'marco');
  assert.equal(app.log().children[0].children[0].textContent,'CM');
  await app.view.open(agent,[]);
  assert.equal(app.root.attributes['data-chat-specialist'],'nora');
});

test('all specialist tints retain readable dark ink and avoid the owner and Li fills', () => {
  const css = readFileSync(new URL('../static/assets/specialists.css', import.meta.url), 'utf8');
  const themeContext = {};
  vm.runInNewContext(readFileSync(new URL('../static/assets/themes.js', import.meta.url), 'utf8'), themeContext);
  const rows = [...css.matchAll(/data-chat-specialist="([a-z]+)"\]\{--chat-specialist:(#[0-9a-f]{6})\}/g)];
  assert.equal(rows.length,12);
  for(const [,id,color] of rows) {
    assert.ok(themeContext.LiThemes.contrast('#172033',color)>=7, id);
    assert.ok(!['#dcfce7','#ede9fe'].includes(color), id);
  }
});
