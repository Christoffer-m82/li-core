import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const source = readFileSync(new URL('../static/assets/profile-photo.js', import.meta.url), 'utf8');
class Element {
  children=[]; textContent=''; handlers={}; hidden=false; disabled=false; value=''; files=[]; src='';
  replaceChildren(...children) { this.children=children; this.textContent=children.map(item=>item.textContent||'').join(''); }
  addEventListener(name, handler) { this.handlers[name]=handler; }
  setAttribute() {}
  click() { this.clicked=true; }
}
class FakeFormData { entries=[]; append(...entry) { this.entries.push(entry); } }
const response = (data, ok=true) => ({ok, json:async()=>data, blob:async()=>data});
function setup(fetch=async()=>response({state:'empty',revision:'absent'})) {
  const controls={input:new Element(),choose:new Element(),save:new Element(),cancel:new Element(),remove:new Element(),status:new Element(),previewImage:new Element(),previewFallback:new Element()};
  const created=[], revoked=[]; let serial=0;
  const document={createElement(tag){const item=new Element();item.tag=tag;created.push(item);return item;},createTextNode(text){return {textContent:text};}};
  const URL={createObjectURL(){return `blob:synthetic-${++serial}`;},revokeObjectURL(value){revoked.push(value);}};
  const context={}; vm.runInNewContext(source,context);
  const manager=context.LiProfilePhoto.create({document,fetch,URL,FormData:FakeFormData,controls});
  return {api:context.LiProfilePhoto,manager,controls,created,revoked};
}

test('initials and empty profile use CM fallback without browser persistence', async()=>{
  const app=setup(); const account=new Element(); app.manager.register(account); app.manager.setName('Christoffer Melldén');
  await app.manager.load();
  assert.equal(account.textContent,'CM'); assert.equal(app.controls.previewFallback.textContent,'CM');
  assert.equal(app.manager.state(),'empty'); assert.equal(app.controls.choose.disabled,false);
  assert.match(app.controls.status.textContent,/CM is shown/);
  assert.equal(app.api.initials('Any account name'),'CM'); assert.equal(app.api.initials(''),'CM');
});

test('saved JPEG is shared by registered avatars and removed from memory on clear', async()=>{
  const blob={type:'image/jpeg',size:100};
  let calls=0; const app=setup(async url=>++calls===1?response({state:'available',revision:'00000000-0000-0000-0000-000000000001'}):response(blob));
  const first=new Element(), second=app.manager.avatar(); app.manager.register(first); await app.manager.load();
  assert.equal(first.children[0].src,'blob:synthetic-1'); assert.equal(second.children[0].src,'blob:synthetic-1');
  assert.equal(app.controls.previewImage.src,'blob:synthetic-1'); assert.equal(app.controls.previewImage.hidden,false);
  assert.equal(app.controls.remove.disabled,false); app.manager.clear();
  assert.equal(first.textContent,'CM'); assert.deepEqual(app.revoked,['blob:synthetic-1']);
});

test('invalid server image fails closed and never replaces fallback', async()=>{
  let calls=0; const app=setup(async()=>++calls===1?response({state:'available',revision:'opaque'}):response({type:'image/png',size:10}));
  const avatar=new Element(); app.manager.register(avatar); await app.manager.load();
  assert.equal(app.manager.state(),'unavailable'); assert.equal(avatar.textContent,'CM');
  assert.equal(app.controls.choose.disabled,true); assert.match(app.controls.status.textContent,/not available/);
});

test('selection is local until explicit save and exact mutation headers are sent', async()=>{
  const calls=[]; const replies=[response({state:'empty',revision:'absent'}),response({}),response({state:'empty',revision:'new'})];
  const app=setup(async(url,options={})=>{calls.push([url,options]);return replies.shift();}); await app.manager.load();
  const file={type:'image/png',size:200}; assert.equal(app.manager.select(file),true);
  assert.equal(calls.length,1); assert.equal(app.controls.previewImage.src,'blob:synthetic-1'); assert.equal(app.controls.save.disabled,false);
  await app.manager.save();
  assert.equal(calls[1][0],'/api/profile/photo'); assert.equal(calls[1][1].method,'PUT');
  assert.equal(calls[1][1].headers['If-Match'],'absent'); assert.equal(calls[1][1].headers['X-Li-Profile-Mutation'],'1');
  assert.equal(calls[1][1].body.entries[0][1],file); assert.deepEqual(app.revoked,['blob:synthetic-1']);
});

test('invalid selection and failed save preserve the current avatar and draft status', async()=>{
  const app=setup(async(url,options={})=>options.method?response({},false):response({state:'empty',revision:'absent'})); await app.manager.load();
  for(const file of [null,{type:'image/gif',size:10},{type:'image/jpeg',size:0},{type:'image/jpeg',size:app.api.MAX_INPUT+1}]) assert.equal(app.manager.select(file),false);
  app.manager.select({type:'image/jpeg',size:10}); await app.manager.save();
  assert.match(app.controls.status.textContent,/not saved/); assert.equal(app.controls.save.disabled,false);
});

test('remove requires confirmation and reloads CM only after server success', async()=>{
  const calls=[]; const replies=[response({state:'available',revision:'00000000-0000-0000-0000-000000000001'}),response({type:'image/jpeg',size:20}),response({}),response({state:'empty',revision:'next'})];
  const app=setup(async(url,options={})=>{calls.push([url,options]);return replies.shift();}); const avatar=new Element();app.manager.register(avatar);await app.manager.load();
  await app.manager.remove(false); assert.equal(calls.length,2); assert.equal(avatar.children[0].tag,'img');
  await app.manager.remove(true); assert.equal(calls[2][1].method,'DELETE'); assert.equal(avatar.textContent,'CM'); assert.equal(app.controls.remove.disabled,true);
});

test('late image response is discarded after clear', async()=>{
  let release; const pending=new Promise(resolve=>{release=resolve;}); let calls=0;
  const app=setup(async()=>++calls===1?response({state:'available',revision:'rev'}):pending);
  const load=app.manager.load(); await Promise.resolve(); await Promise.resolve(); app.manager.clear();
  release(response({type:'image/jpeg',size:20})); await load;
  assert.equal(app.manager.state(),'unknown'); assert.deepEqual(app.revoked,['blob:synthetic-1']);
});
