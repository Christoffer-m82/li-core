// Resolve storage lazily: even accessing the browser property can be denied.
const preferenceStorage = {
  getItem(key) { try { return localStorage.getItem(key); } catch { return null; } },
  setItem(key, value) { localStorage.setItem(key, value); },
};
const retryStorage = typeof sessionStorage === 'undefined' ? null : sessionStorage;
function retryFingerprint(value) {
  let hash = 2166136261;
  for (const char of JSON.stringify(value)) {
    hash ^= char.codePointAt(0); hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(16).padStart(8, '0');
}
function storedRetry(key, fingerprint) {
  try { const value = JSON.parse(retryStorage?.getItem(key) || 'null'); return value?.fingerprint === fingerprint ? value : null; }
  catch { return null; }
}
function saveRetry(key, value) { try { retryStorage?.setItem(key, JSON.stringify(value)); } catch { /* Retry remains available for this visit. */ } }
function clearRetry(key) { try { retryStorage?.removeItem(key); } catch { /* Expired metadata is harmless. */ } }
function savePreference(key, value) {
  try { preferenceStorage.setItem(key, value); } catch { /* Controls still work for this visit. */ }
}
const state = { conversationId: null, history: [], signedIn: false, sending: false, specialists: [], capabilities: [], temporaryUploadContext: null, pendingTurn: null, theme: preferenceStorage.getItem('li-theme') || 'dark', voiceOutput: preferenceStorage.getItem('li-voice-output') === 'on', voiceSession: 0, voiceSendTimer: null, displayName: '', currentSpecialist: null, installPrompt: null };
const $ = (selector) => document.querySelector(selector);
const COUNTRY_CODES = `AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW`.split(' ');
const countryNames = new Intl.DisplayNames([navigator.language || 'en'], {type: 'region'});
let placeState = { current_place: {}, most_visited: [] };
function countryName(code) { return countryNames.of(code) || code; }
function createPlaceSettings() { const appearance = $('.theme-setting'); if (!appearance || $('#country-search')) return; const field = document.createElement('fieldset'); field.className = 'theme-setting place-setting'; field.innerHTML = `<legend>Place</legend><p>Share your current country when it can materially improve a decision or search.</p><label for="country-search">Country</label><input id="country-search" type="search" autocomplete="off" placeholder="Search all countries" aria-controls="country-results"><div id="country-results" class="country-results" role="listbox" aria-label="Countries"></div><label for="town-city">Town/City <span class="muted">optional</span></label><input id="town-city" type="text" maxlength="120" autocomplete="address-level2" placeholder="Only when useful"><div class="place-actions"><button id="save-place" type="button" class="primary-button">Set current place</button><button id="pin-country" type="button" class="secondary-button">Add to Most visited</button><button id="confirm-overnight" type="button" class="secondary-button">Confirm this overnight visit</button></div><small id="place-status" class="muted">Loading your private place settings…</small><h3>Most visited</h3><div id="most-visited-list" class="most-visited-list"></div><p class="muted">A country is added after two distinct overnight visits within 12 months. Transit does not count. A removed country stays suppressed until you pin it again.</p><h3>Device location</h3><div id="mobile-provider-status" class="privacy-note">Loading device-location status…</div><p class="privacy-note">Native access is enabled only after an authenticated app installation exists. Each app must request explicit OS permission, resolve location on-device, and send only a coarse country plus optional town/city. Li stores no GPS trail. Deployment readiness is shown in Backend Overview.</p>`; appearance.after(field); $('#country-search').addEventListener('input', (event) => { const code = event.target.dataset.countryCode; if (code && event.target.value !== countryName(code)) event.target.dataset.countryCode = ''; renderCountryResults(); }); $('#save-place').addEventListener('click', savePlace); $('#pin-country').addEventListener('click', () => { const code = $('#country-search').dataset.countryCode; if (code) changeMostVisited(code, 'pin'); else $('#place-status').textContent = 'Choose a country from the list first.'; }); $('#confirm-overnight').addEventListener('click', confirmOvernight); }
function orderedCountries() { const top = placeState.most_visited.map((item) => item.country_code); return [...new Set([...top, ...COUNTRY_CODES])]; }
function renderCountryResults() { const host = $('#country-results'); if (!host) return; const query = $('#country-search').value.trim().toLocaleLowerCase(); host.replaceChildren(); orderedCountries().filter((code) => !query || countryName(code).toLocaleLowerCase().includes(query) || code.toLowerCase().includes(query)).slice(0, query ? 40 : 12).forEach((code) => { const button = document.createElement('button'); button.type = 'button'; button.className = `country-option${placeState.most_visited.some((item) => item.country_code === code) ? ' most-visited' : ''}`; button.dataset.countryCode = code; button.textContent = `${countryName(code)}${placeState.most_visited.some((item) => item.country_code === code) ? ' · Most visited' : ''}`; button.addEventListener('click', () => { $('#country-search').value = countryName(code); $('#country-search').dataset.countryCode = code; renderCountryResults(); }); host.appendChild(button); }); }
function renderMostVisited() { const host = $('#most-visited-list'); host.replaceChildren(); if (!placeState.most_visited.length) { host.textContent = 'No countries added yet.'; return; } placeState.most_visited.forEach((item) => { const chip = document.createElement('span'); chip.className = 'place-chip'; chip.textContent = countryName(item.country_code); const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = 'Remove'; remove.setAttribute('aria-label', `Remove ${countryName(item.country_code)} from Most visited`); remove.addEventListener('click', () => changeMostVisited(item.country_code, 'remove')); chip.appendChild(remove); host.appendChild(chip); }); }
async function loadPlace() { createPlaceSettings(); try { const response = await fetch('/api/settings/place'); if (!response.ok) throw new Error(); placeState = await response.json(); const current = placeState.current_place || {}; $('#country-search').value = current.country_code ? countryName(current.country_code) : ''; $('#country-search').dataset.countryCode = current.country_code || ''; $('#town-city').value = current.town_city || ''; $('#place-status').textContent = current.country_code ? `Current place: ${countryName(current.country_code)}${current.town_city ? ` · ${current.town_city}` : ''}. Private and used only when relevant.` : 'No current country set.'; renderMostVisited(); renderCountryResults(); renderMobileProviderStatus(); } catch { $('#place-status').textContent = 'Place settings are unavailable.'; $('#mobile-provider-status').textContent = 'Device-location status is unavailable.'; } }
function renderMobileProviderStatus() { const provider = placeState.provider || {}; const installs = provider.installations || []; const last = provider.last_accepted_coarse_update ? new Date(provider.last_accepted_coarse_update).toLocaleString() : 'Never'; const summary = document.createElement('p'); summary.textContent = `Web location mode: manual. Connected native providers: ${installs.length ? 'configured' : 'none'}. Permission: ${provider.permission_state || 'not configured'}. Last accepted coarse update: ${last}.`; const target = $('#mobile-provider-status'); target.replaceChildren(summary); installs.forEach((installation) => { const button = document.createElement('button'); button.type = 'button'; button.className = 'secondary-button'; button.textContent = `Revoke ${installation.platform.toUpperCase()} provider`; button.addEventListener('click', () => revokeMobileProvider(installation.installation_id)); target.append(button); }); }
async function revokeMobileProvider(installationId) { const response = await fetch('/api/settings/place/mobile/revoke', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({installation_id:installationId})}); if (response.ok) { placeState = await response.json(); renderMobileProviderStatus(); } else $('#mobile-provider-status').append(' Could not revoke this provider.'); }
async function savePlace() { const code = $('#country-search').dataset.countryCode; if (!code) { $('#place-status').textContent = 'Choose a country from the list.'; return; } const response = await fetch('/api/settings/place', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({current_place:{country_code:code,town_city:$('#town-city').value || null,source:'manual_web',provider_permission:'not_applicable'}})}); if (response.ok) { placeState = await response.json(); $('#place-status').textContent = `Current place set to ${countryName(code)}. Private and used only when relevant.`; renderMostVisited(); } else $('#place-status').textContent = 'Could not update current place.'; }
async function changeMostVisited(code, action) { const response = await fetch('/api/settings/place/most-visited', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({country_code:code,action})}); if (response.ok) { placeState = await response.json(); renderMostVisited(); renderCountryResults(); } }
async function confirmOvernight() { const code = $('#country-search').dataset.countryCode; if (!code) { $('#place-status').textContent = 'Choose a country first.'; return; } const now = new Date(); const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()); const yesterday = new Date(today); yesterday.setDate(today.getDate() - 1); const localDate = (value) => `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`; const response = await fetch('/api/settings/place/visits', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({visit:{country_code:code,first_seen:localDate(yesterday),last_seen:localDate(today),overnight_confirmed:true,source:'manual'}})}); if (response.ok) { placeState = await response.json(); $('#place-status').textContent = 'Last night confirmed. Overlapping or continuous dates count as one trip.'; renderMostVisited(); renderCountryResults(); } else $('#place-status').textContent = 'Could not confirm this visit.'; }
const $$ = (selector) => document.querySelectorAll(selector);
const profilePhoto = window.LiProfilePhoto.create({ document, fetch, URL, FormData, controls: {
  input: $('#profile-photo-input'), choose: $('#profile-photo-choose'), save: $('#profile-photo-save'),
  cancel: $('#profile-photo-cancel'), remove: $('#profile-photo-remove'), status: $('#profile-photo-status'),
  previewImage: $('#profile-photo-preview'), previewFallback: $('#profile-photo-fallback'),
} });
profilePhoto.register($('#account-button'));

function greeting() { const hour = new Date().getHours(); const salutation = `Good ${hour < 12 ? 'morning' : hour < 18 ? 'afternoon' : 'evening'}`; return state.displayName ? `${salutation}, ${state.displayName.split(/\s+/)[0]}` : salutation; }
const VIEW_COPY = Object.freeze({
  home: { title: greeting, context: 'Talk with Li, continue recent work, or open a specialist.' },
  inbox: { title: 'Li Briefs', context: 'Review private proactive briefs and useful suggestions from Li.' },
  agents: { title: 'Agent Status & Analytics', context: 'See specialist roles, measured activity, and recommendations.' },
  backend: { title: 'Backend Overview', context: 'Review Li’s read-only capabilities, permissions, and freshness.' },
  history: { title: 'Conversation history', context: 'Revisit private conversations and saved files.' },
  settings: { title: 'Settings', context: 'Manage appearance, devices, profile, voice, and privacy.' },
  specialist: { title: 'Specialist activity', context: 'Work with Li and this specialist, or review recorded evidence.' },
  'system-agent': { title: 'System agent profile', context: 'Review this system role’s responsibilities and boundaries.' },
});
function setView(view) {
  closeSpecialistPortrait();
  $$('.view').forEach((panel) => panel.classList.toggle('active', panel.dataset.viewPanel === view));
  const navigationView = ['specialist', 'system-agent'].includes(view) ? 'agents' : view;
  $$('.nav-item').forEach((button) => {
    const current = button.dataset.view === navigationView;
    button.classList.toggle('active', current);
    button.setAttribute('aria-current', current ? 'page' : 'false');
  });
  const copy = VIEW_COPY[view] || VIEW_COPY.home;
  $('#page-title').textContent = typeof copy.title === 'function' ? copy.title() : copy.title;
  $('#page-context').textContent = copy.context;
  if (view === 'home') setTimeout(() => $('#message-input').focus(), 100);
  if (view === 'inbox') loadProactiveBriefs();
  if (view === 'agents') loadAgentAnalytics();
  if (view === 'backend') { loadCapabilities(); loadFreshnessPolicies(); loadProviderCoverage(); loadGovernedWorkStatus(); }
  if (view === 'history') loadConversations();
  if (view === 'settings') { loadPrivacy(); loadPlace(); profilePhoto.load(); }
}

function updateConnectivity() { const offline = navigator.onLine === false; $('#offline-status')?.classList.toggle('hidden', !offline); if (offline) $('#connection-label').textContent = 'Offline · private data unavailable'; }

async function loadProactiveBriefs() {
  const host = $('#proactive-brief-list'); if (!host) return; host.replaceChildren();
  try {
    const response = await fetch('/api/proactive-briefs'); if (!response.ok) throw new Error();
    const data = await response.json(); const unread = data.briefs.filter((item) => !item.read_at).length;
    $('#brief-unread').textContent = `${unread} unread`;
    if (!data.briefs.length) { host.textContent = 'No briefs yet. Rhythms remain quiet until you explicitly activate them.'; return; }
    data.briefs.forEach((brief) => {
      const card = document.createElement('article'); card.className = 'panel';
      const title = document.createElement('h3'); title.textContent = brief.title;
      const preview = document.createElement('p'); preview.className = 'muted'; preview.textContent = brief.neutral_preview;
      const button = document.createElement('button'); button.className = 'secondary-button'; button.textContent = brief.read_at ? 'Open' : 'Open privately';
      button.addEventListener('click', async () => {
        await fetch(`/api/proactive-briefs/${encodeURIComponent(brief.id)}/read`, {method: 'POST'}); card.replaceChildren(title);
        Object.values(brief.content.items || {}).forEach((item) => {
          const row = document.createElement('div'); row.className = 'brief-item';
          const kind = document.createElement('small'); kind.className = 'eyebrow'; kind.textContent = String(item.kind || 'commitment').replaceAll('_', ' ');
          const summary = document.createElement('p'); summary.textContent = `${item.title} — ${item.detail}`;
          const why = document.createElement('small'); why.className = 'muted'; why.textContent = `Why now: ${item.why_now}`;
          const controls = document.createElement('span'); controls.className = 'brief-controls';
          [['not_now', 'Not now'], ['leave_it', 'Leave it']].forEach(([action, label]) => {
            const control = document.createElement('button'); control.className = 'text-button'; control.textContent = label;
            control.addEventListener('click', async () => {
              const loopId = String(item.source || '').startsWith('open_loop:') ? String(item.source).slice(10) : null;
              const path = loopId ? `/api/open-loops/${encodeURIComponent(loopId)}/suppression` : `/api/proactivity/categories/${encodeURIComponent(item.category)}/suppression`;
              await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({action})}); row.remove();
            }); controls.appendChild(control);
          });
          row.append(kind, summary, why, controls); card.appendChild(row);
        });
      });
      card.append(title, preview, button); host.appendChild(card);
    });
  } catch { host.textContent = 'Li Briefs are unavailable.'; }
}

function matchesCapability(item) { const query = $('#capability-search').value.trim().toLowerCase(); const category = $('#capability-category').value; const status = $('#capability-status').value; const access = $('#capability-access').value; const haystack = [item.name, item.purpose, item.category, ...item.operations, ...item.access, item.approval].join(' ').toLowerCase(); return (!query || haystack.includes(query)) && (!category || item.category === category) && (!status || item.status === status) && (!access || haystack.includes(access)); }
function renderCapabilities() { const list = $('#capability-list'); list.replaceChildren(); const groups = new Map(); state.capabilities.filter(matchesCapability).forEach((item) => { if (!groups.has(item.category)) groups.set(item.category, []); groups.get(item.category).push(item); }); if (!groups.size) { list.textContent = 'No capabilities match these filters.'; return; } groups.forEach((items, category) => { const section = document.createElement('section'); section.className = 'capability-group'; const heading = document.createElement('h3'); heading.textContent = category; section.appendChild(heading); const grid = document.createElement('div'); grid.className = 'capability-grid'; items.forEach((item) => { const card = document.createElement('article'); card.className = 'panel capability-card'; const head = document.createElement('div'); head.className = 'capability-head'; const name = document.createElement('h4'); name.textContent = item.name; const badge = document.createElement('span'); badge.className = `status-badge ${item.status}`; badge.textContent = item.status; head.append(name, badge); const purpose = document.createElement('p'); purpose.className = 'muted'; purpose.textContent = item.purpose; const access = document.createElement('p'); access.innerHTML = '<strong>Li can use</strong> '; access.append(document.createTextNode(item.access.join(' · '))); const exposed = document.createElement('p'); exposed.innerHTML = '<strong>Li Web exposes</strong> '; exposed.append(document.createTextNode(item.web_exposure.replace('_', ' '))); const facts = document.createElement('dl'); [['Approval', item.approval], ['Persistence', item.persisted ? 'Persisted' : 'Not separately persisted'], ['Retention', item.retention], ['Current state', item.status_detail]].forEach(([label, value]) => { const dt = document.createElement('dt'); dt.textContent = label; const dd = document.createElement('dd'); dd.textContent = value; facts.append(dt, dd); }); card.append(head, purpose, access, exposed, facts); if (item.web_path) { const link = document.createElement('button'); link.className = 'text-button'; link.textContent = 'Open related Li Web page →'; link.addEventListener('click', () => setView(item.web_path === '/' ? 'home' : item.web_path.slice(1))); card.appendChild(link); } grid.appendChild(card); }); section.appendChild(grid); list.appendChild(section); }); }
async function loadCapabilities() { const list = $('#capability-list'); list.textContent = 'Loading live backend capability metadata…'; try { const response = await fetch('/api/capabilities'); if (!response.ok) throw new Error(); const data = await response.json(); state.capabilities = data.capabilities; $('#architecture-flow').replaceChildren(...data.architecture_flow.map((step, index) => { const span = document.createElement('span'); span.textContent = `${index ? '→ ' : ''}${step}`; return span; })); $('#backend-refresh').textContent = `Last refreshed ${new Date(data.last_refreshed).toLocaleString()} · system ${data.system_version} · schema ${data.schema_version}. ${data.source_of_truth}`; const category = $('#capability-category'); if (category.options.length === 1) [...new Set(data.capabilities.map((item) => item.category))].forEach((value) => category.add(new Option(value, value))); $('#permission-list').replaceChildren(...data.permissions.map((item) => { const p = document.createElement('p'); const strong = document.createElement('strong'); strong.textContent = `${item.actor}: `; p.append(strong, document.createTextNode(item.summary)); return p; })); $('#privacy-posture').replaceChildren(...data.privacy_posture.map((item) => { const li = document.createElement('li'); li.textContent = item; return li; })); renderCapabilities(); } catch { list.textContent = 'Backend capability metadata is unavailable right now.'; } }
async function loadGovernedWorkStatus() { let host = $('#governed-work-status'); if (!host) { host = document.createElement('div'); host.id = 'governed-work-status'; host.className = 'backend-notes'; $('#capability-list').before(host); } host.replaceChildren(); const policyCard = document.createElement('article'); policyCard.className = 'panel'; const workCard = document.createElement('article'); workCard.className = 'panel'; host.append(policyCard, workCard); try { const [policyResponse, rhythmResponse, loopResponse] = await Promise.all([fetch('/api/action-policy'), fetch('/api/rhythms'), fetch('/api/open-loops')]); if (!policyResponse.ok || !rhythmResponse.ok || !loopResponse.ok) throw new Error(); const policy = await policyResponse.json(); const rhythms = await rhythmResponse.json(); const loops = await loopResponse.json(); const policyTitle = document.createElement('h3'); policyTitle.textContent = `Effective Action Policy · v${policy.effective_policy.policy_version}`; const policyNote = document.createElement('p'); policyNote.className = 'muted'; policyNote.textContent = 'Identity expresses preferences; this policy grants authority. Read-only.'; policyCard.append(policyTitle, policyNote); policy.effective_policy.categories.forEach((item) => { const row = document.createElement('p'); row.textContent = `${item.category.replaceAll('_', ' ')} · ${item.autonomy_level.replaceAll('_', ' ')} · ${item.approval_required ? 'approval required' : 'approval not required'} · auto-execution ${item.auto_execution_permitted ? 'permitted' : 'blocked'}`; policyCard.appendChild(row); }); policy.identity_policy_mismatches.forEach((item) => { const warning = document.createElement('p'); warning.className = 'policy-warning'; warning.textContent = `Warning: ${item.identity_claim} ${item.enforced_policy}`; policyCard.appendChild(warning); }); const workTitle = document.createElement('h3'); workTitle.textContent = 'Open Loops & Rhythms'; const workNote = document.createElement('p'); workNote.className = 'muted'; workNote.textContent = `${rhythms.definitions.length} governed rhythms · ${loops.open_loops.length} durable open loops`; workCard.append(workTitle, workNote); rhythms.definitions.forEach((item) => { const row = document.createElement('p'); row.textContent = `${item.label} · ${item.cadence} · ${item.mode} · no external mutations`; workCard.appendChild(row); }); } catch { policyCard.textContent = 'Action policy status is unavailable.'; workCard.textContent = 'Open-loop and rhythm status is unavailable.'; } }

async function loadFreshnessPolicies() { const list = $('#freshness-policy-list'); if (!list) return; list.textContent = 'Loading freshness policies…'; try { const response = await fetch('/api/specialists/freshness-evidence'); if (!response.ok) throw new Error(); const data = await response.json(); list.replaceChildren(); data.specialists.forEach((item) => { const card = document.createElement('article'); card.className = 'panel capability-card'; const title = document.createElement('h4'); title.textContent = item.specialist_key[0].toUpperCase() + item.specialist_key.slice(1); const status = document.createElement('span'); status.className = 'status-badge available'; status.textContent = item.freshness_mode.replaceAll('_', ' '); const domain = document.createElement('p'); domain.className = 'muted'; domain.textContent = item.domain; const mandatory = document.createElement('p'); mandatory.textContent = `Live research: ${item.live_verification_triggers.join(', ')}`; const sources = document.createElement('p'); sources.textContent = `Sources: ${item.preferred_source_classes.join(', ')}${item.primary_or_official_required ? ' · primary/official required' : ''}`; const age = document.createElement('p'); age.textContent = `Freshness limits: ${item.maximum_evidence_age.map((x) => `${x.evidence_type} ${x.maximum_age_days}d`).join(' · ')}`; card.append(title, status, domain, mandatory, sources, age); list.appendChild(card); }); } catch { list.textContent = 'Freshness policy metadata is unavailable right now.'; } }
async function loadProviderCoverage() { const list = $('#provider-coverage-list'); if (!list) return; list.textContent = 'Loading provider coverage…'; try { const response = await fetch('/api/providers/coverage'); if (!response.ok) throw new Error(); const data = await response.json(); list.replaceChildren(); data.specialist_status.forEach((item) => { const card = document.createElement('article'); card.className = 'panel capability-card'; const title = document.createElement('h4'); title.textContent = item.specialist; const summary = document.createElement('p'); summary.textContent = item.summary; card.append(title, summary); list.appendChild(card); }); data.providers.forEach((item) => { const card = document.createElement('article'); card.className = 'panel capability-card'; const title = document.createElement('h4'); title.textContent = item.public_name; const status = document.createElement('span'); status.className = `status-badge ${item.configured ? 'available' : 'unavailable'}`; status.textContent = item.status.replaceAll('_', ' '); const summary = document.createElement('p'); summary.textContent = item.public_summary; const detail = document.createElement('p'); detail.className = 'muted'; detail.textContent = `${item.domains.join(', ')} · ${item.freshness_classes.join(', ')} · ${item.authority_level}`; card.append(title, status, summary, detail); list.appendChild(card); }); } catch { list.textContent = 'Provider coverage metadata is unavailable right now.'; } }

function setLiState(mode, intensity = 1) { $$('.li-orb').forEach((orb) => { orb.dataset.liState = mode; orb.style.setProperty('--thinking-intensity', Math.max(0.35, Math.min(intensity, 1))); if (!orb.hasAttribute('aria-hidden')) orb.setAttribute('aria-label', `Li is ${mode}`); }); $('#li-state-label').textContent = { idle: 'Here with you', listening: 'Listening…', transcribing: 'Transcribing…', thinking: 'Thinking…', speaking: 'Speaking…', error: 'Voice needs attention' }[mode] || 'Here with you'; }

function attachmentChip(attachment) { const wrap = document.createElement('span'); wrap.className = 'chat-attachment'; const link = document.createElement(attachment.url ? 'a' : 'span'); link.textContent = `↧ ${attachment.filename}`; if (attachment.url) { link.href = attachment.url; link.download = attachment.filename; } wrap.append(link); if (attachment.artifact_id) { ['keep', 'delete'].forEach((action) => { const button = document.createElement('button'); button.type = 'button'; button.textContent = action === 'keep' ? 'Keep' : 'Delete'; button.addEventListener('click', async () => { const response = await fetch(`/api/artifacts/${attachment.artifact_id}/retention`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action }) }); if (response.ok && action === 'delete') { const parent = wrap.parentElement; if (parent?.classList.contains('artifact-row')) parent.remove(); else wrap.remove(); } if (response.ok && action === 'keep') { button.textContent = 'Kept'; const status = wrap.parentElement?.querySelector('small'); if (status) status.textContent = 'Kept permanently'; } }); wrap.append(button); }); } return wrap; }
function addMessage(role, text, options = {}) { const row = document.createElement('div'); row.className = `message ${role}${options.temporary ? ' typing' : ''}`; if (role === 'assistant') { const avatar = document.createElement('span'); avatar.className = 'mini-avatar'; avatar.textContent = 'Li'; row.appendChild(avatar); } else if (role === 'user') row.appendChild(profilePhoto.avatar('owner-avatar')); const content = document.createElement('div'); if (text) { const body = document.createElement('p'); body.textContent = text; content.appendChild(body); } (options.attachments || []).forEach((item) => content.appendChild(attachmentChip(item))); const time = document.createElement('time'); time.textContent = 'Now'; content.appendChild(time); row.appendChild(content); $('#messages').appendChild(row); $('#messages').scrollTo({ top: $('#messages').scrollHeight, behavior: 'smooth' }); return row; }

function renderActionIntent(intent) { const card = document.createElement('article'); card.className = `action-intent-card ${intent.approval_state}`; card.dataset.intentId = intent.intent_id; const eyebrow = document.createElement('small'); eyebrow.textContent = 'Approval required'; const title = document.createElement('strong'); title.textContent = intent.action_type.replaceAll('.', ' · '); const summary = document.createElement('p'); summary.textContent = intent.summary; const status = document.createElement('span'); status.className = 'intent-status'; status.textContent = intent.approval_state.replaceAll('_', ' '); const controls = document.createElement('div'); controls.className = 'intent-controls'; card.append(eyebrow, title, summary, status, controls); const update = (next) => { card.className = `action-intent-card ${next.approval_state}`; status.textContent = next.approval_state.replaceAll('_', ' '); controls.replaceChildren(); if (next.result?.message || next.result?.confirmation) { const result = document.createElement('p'); result.className = 'intent-result'; result.textContent = next.result.message || next.result.confirmation; card.appendChild(result); } if (['proposed', 'owner_confirmation_required'].includes(next.approval_state)) addControls(next); }; const decide = async (value, current) => { controls.querySelectorAll('button').forEach((button) => { button.disabled = true; }); const body = { decision: value }; if (value === 'approve' && current.owner_confirmation_required) { if (!window.confirm('Owner confirmation: continue to the existing governed execution boundary?')) { addControls(current); return; } body.owner_confirmation = 'confirm_permanent_agent_change'; } const response = await fetch(`/api/action-intents/${encodeURIComponent(current.intent_id)}/decision`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body) }); if (!response.ok) { status.textContent = 'Could not resolve safely'; addControls(current); return; } update(await response.json()); }; const addControls = (current) => { controls.replaceChildren(); [['approve', 'Approve'], ['deny', 'Deny']].forEach(([value, label]) => { const button = document.createElement('button'); button.type = 'button'; button.className = value === 'approve' ? 'primary-button' : 'secondary-button'; button.textContent = current.owner_confirmation_required && value === 'approve' ? 'Continue to owner confirmation' : label; button.addEventListener('click', () => decide(value, current)); controls.appendChild(button); }); }; if (['proposed', 'owner_confirmation_required'].includes(intent.approval_state)) addControls(intent); $('#messages').appendChild(card); }

async function loadSession() { try { const response = await fetch('/api/session'); state.signedIn = response.ok; if (response.ok) { const session = await response.json(); state.displayName = session.display_name || ''; profilePhoto.setName(state.displayName || session.email); $('#page-title').textContent = greeting(); } } catch { state.signedIn = false; } $('#signed-out').classList.toggle('hidden', state.signedIn); $('#workspace').classList.toggle('hidden', !state.signedIn); updateConnectivity(); if (!state.signedIn) { closeSpecialistPortrait(); specialistView?.clear(); profilePhoto.clear(); $('#connection-label').textContent = navigator.onLine === false ? 'Offline · private data unavailable' : 'Sign in required'; return; } await profilePhoto.load(); try { const ready = await fetch('/api/ready'); $('#connection-label').textContent = ready.ok ? 'Li is online' : 'Li needs attention'; } catch { $('#connection-label').textContent = navigator.onLine === false ? 'Offline · private data unavailable' : 'Li is unreachable'; } await Promise.all([loadSpecialists(), loadAgentAnalytics(), loadHomeData()]); }

async function sendMessage(message) {
  if (state.sending) return;
  const retryKey = 'li-home-pending-turn-v1';
  const fingerprint = retryFingerprint({message, conversationId: state.conversationId,
    temporaryUploadContext: state.temporaryUploadContext});
  const recovered = storedRetry(retryKey, fingerprint);
  const turn = state.pendingTurn?.fingerprint === fingerprint
    ? state.pendingTurn
    : { message, fingerprint, turnId: recovered?.turnId || crypto.randomUUID(), rendered: false };
  state.pendingTurn = turn;
  saveRetry(retryKey, {turnId: turn.turnId, fingerprint});
  state.sending = true;
  if (!turn.rendered) {
    addMessage('user', message);
    state.history.push({ role: 'user', text: message });
    turn.rendered = true;
  }
  setLiState('thinking', 0.75);
  const pending = addMessage('assistant', 'Thinking…', { temporary: true });
  const specialistPoll = setInterval(loadSpecialists, 1200);
  $('#message-input').value = '';
  $('.send-button').disabled = true;
  try {
    const response = await fetch('/api/chat', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, turn_id: turn.turnId, conversation_id: state.conversationId,
        temporary_upload_context: state.temporaryUploadContext }),
    });
    if (response.status === 401) {
      await loadSession();
      throw new Error('Your session has expired. Please sign in again.');
    }
    if (!response.ok) {
      const problem = await response.json().catch(() => ({}));
      const detail = typeof problem.detail === 'object' ? problem.detail.message : null;
      throw new Error(detail || 'Li could not confirm this request. Your draft is ready to retry safely.');
    }
    const data = await response.json();
    state.pendingTurn = null;
    clearRetry(retryKey);
    state.temporaryUploadContext = null;
    $('#attachment-tray').replaceChildren();
    state.conversationId = data.conversation_id;
    pending.remove();
    addMessage('assistant', data.response, { attachments: data.artifacts || [] });
    (data.action_intents || []).forEach(renderActionIntent);
    state.history.push({ role: 'assistant', text: data.response });
    renderHistory();
    if (data.turn_state === 'durability_unavailable') {
      addMessage('assistant', 'The reply arrived, but safe replay confirmation is unavailable. Refresh before resending this request.');
    }
    if (state.voiceOutput) speakLiResponse(data.response);
    return data;
  } catch (error) {
    pending.remove();
    $('#message-input').value = message;
    addMessage('assistant', error.message || 'Something went wrong.');
    return null;
  } finally {
    clearInterval(specialistPoll);
    await loadSpecialists();
    state.sending = false;
    $('.send-button').disabled = false;
    if (!window.speechSynthesis?.speaking) setLiState('idle');
    $('#message-input').focus();
  }
}

const voiceTranscription = window.LiVoice?.BrowserVoiceTranscriptionProvider.isSupported() ? new window.LiVoice.BrowserVoiceTranscriptionProvider() : null;
const voiceSynthesis = window.LiVoice?.BrowserVoiceSynthesisProvider.isSupported() ? new window.LiVoice.BrowserVoiceSynthesisProvider() : null;
function voiceStatus(message, visible = true) { $('#voice-status-text').textContent = message; $('#voice-status').classList.toggle('hidden', !visible); }
function updateVoiceOutputControl() { const button = $('#voice-output-toggle'); button.disabled = !voiceSynthesis; button.setAttribute('aria-pressed', String(state.voiceOutput)); button.setAttribute('aria-label', state.voiceOutput ? 'Turn spoken responses off' : 'Turn spoken responses on'); button.title = voiceSynthesis ? `Spoken responses are ${state.voiceOutput ? 'on' : 'off'}` : 'Spoken responses are unsupported in this browser'; button.textContent = state.voiceOutput ? '🔊' : '🔇'; }
function stopSpeaking() { voiceSynthesis?.stop(); $('#stop-speaking').classList.add('hidden'); if (!state.sending) setLiState('idle'); }
function speakLiResponse(text) { if (!voiceSynthesis || !state.voiceOutput) return; const language = window.LiVoice.detectLanguage(text); voiceSynthesis.speak(text, language, { onStart: () => { setLiState('speaking'); $('#stop-speaking').classList.remove('hidden'); }, onEnd: () => { $('#stop-speaking').classList.add('hidden'); setLiState('idle'); }, onError: () => { $('#stop-speaking').classList.add('hidden'); setLiState('error'); voiceStatus('Li could not play this response. The text is still available.'); } }); }
function cancelVoiceInput() { state.voiceSession += 1; clearTimeout(state.voiceSendTimer); voiceTranscription?.cancel(); $('#microphone-button').setAttribute('aria-pressed', 'false'); $('#microphone-button').setAttribute('aria-label', 'Start voice input'); voiceStatus('', false); if (!state.sending) setLiState('idle'); }
function voiceErrorMessage(code) { return { 'not-allowed': 'Microphone permission was denied. You can keep typing.', 'service-not-allowed': 'Speech recognition is blocked by this browser.', 'no-speech': 'No speech was detected. Please try again or type.', 'audio-capture': 'No microphone is available.', network: 'Speech recognition could not reach its browser provider.', timeout: 'Listening timed out. Please try again.' }[code] || 'Voice input was interrupted. Please try again or type.'; }
async function startVoiceInput() { if (!voiceTranscription) { setLiState('error'); voiceStatus('Voice input is unsupported in this browser. Text chat remains available.'); return; } stopSpeaking(); cancelVoiceInput(); const session = ++state.voiceSession; const button = $('#microphone-button'); button.setAttribute('aria-pressed', 'true'); button.setAttribute('aria-label', 'Stop voice input'); voiceStatus('Listening… press Cancel to discard.'); setLiState('listening'); try { const transcript = await voiceTranscription.start({ onInterim: (value) => { if (session !== state.voiceSession) return; $('#message-input').value = value; voiceStatus(value ? `Heard: ${value}` : 'Listening…'); }, onState: (mode) => setLiState(mode) }); if (session !== state.voiceSession || !transcript) return; $('#message-input').value = transcript; button.setAttribute('aria-pressed', 'false'); button.setAttribute('aria-label', 'Start voice input'); setLiState('transcribing'); voiceStatus(`Transcript ready: ${transcript} · sending shortly…`); state.voiceSendTimer = setTimeout(() => { if (session !== state.voiceSession || state.sending) return; voiceStatus('', false); sendMessage(transcript); }, 1200); } catch (error) { if (session !== state.voiceSession) return; button.setAttribute('aria-pressed', 'false'); button.setAttribute('aria-label', 'Start voice input'); setLiState('error'); voiceStatus(voiceErrorMessage(error.message)); } }
function initializeVoice() { const supported = Boolean(voiceTranscription); $('#microphone-button').disabled = !supported; $('#microphone-button').title = supported ? 'Start push-to-talk' : 'Voice input is unsupported; use text chat'; $('#voice-capability-status').textContent = `Speech input: ${supported ? 'browser-native and available' : 'unavailable in this browser'} · speech output: ${voiceSynthesis ? 'browser-native and available' : 'unavailable'} · server provider: not configured · raw-audio retention: none.`; updateVoiceOutputControl(); }

function isInstalledApp() { return matchMedia('(display-mode: standalone)').matches || navigator.standalone === true; }
function updateInstallControl(message = '') { const button = $('#install-app'); const installed = isInstalledApp(); button.classList.toggle('hidden', installed || !state.installPrompt); if (message) { $('#install-status').textContent = message; return; } $('#install-status').textContent = installed ? 'Li is installed on this device.' : state.installPrompt ? 'Li is ready to install from this browser.' : 'On Android or Windows, use your browser menu and choose Install app or Add to Home screen.'; }
async function installApp() { if (!state.installPrompt || isInstalledApp()) { updateInstallControl(); return; } const prompt = state.installPrompt; state.installPrompt = null; $('#install-app').classList.add('hidden'); try { await prompt.prompt(); const choice = await prompt.userChoice; updateInstallControl(choice.outcome === 'accepted' ? 'Li installation started.' : 'Installation was cancelled. You can try again from your browser menu.'); } catch { updateInstallControl('Installation is unavailable right now. You can try again from your browser menu.'); } }

async function uploadFile(file, save = false) { const form = new FormData(); form.append('file', file); form.append('save', String(save)); return fetch('/api/uploads', { method: 'POST', body: form }); }
async function handleFile(file) { const tray = $('#attachment-tray'); tray.classList.remove('hidden'); tray.replaceChildren(); state.temporaryUploadContext = null; const chip = document.createElement('span'); chip.className = 'upload-chip pending'; chip.textContent = `${file.name} · analysing temporarily…`; tray.appendChild(chip); try { const response = await uploadFile(file); const data = await response.json(); const analysed = response.ok && typeof data.analysis_text === 'string' && data.analysis_text.length > 0; state.temporaryUploadContext = analysed ? `File: ${file.name}\n${data.analysis_text}` : null; chip.classList.remove('pending'); chip.classList.add(response.ok ? 'ready' : 'unavailable'); chip.textContent = response.ok ? (analysed ? `${file.name} · ready for your next message · not retained` : `${file.name} · validated but this file type cannot be analysed here · not retained`) : `${file.name} · ${data.detail || 'could not be attached'}`; if (response.ok) { const save = document.createElement('button'); save.type = 'button'; save.textContent = 'Save privately'; save.addEventListener('click', async () => { save.disabled = true; const stored = await uploadFile(file, true); save.textContent = stored.ok ? 'Saved' : 'Save failed'; }); tray.appendChild(save); } } catch { chip.className = 'upload-chip unavailable'; chip.textContent = `${file.name} · upload unavailable`; } }

const SPECIALIST_PORTRAITS = new Set(['sofia', 'marco', 'elena', 'amelia', 'freja', 'oliver', 'james', 'victor', 'nora', 'milo', 'iris', 'clara', 'ada', 'theo', 'heimdall']);
// Public identity definitions from agents/registry.yaml, not live operational status.
const SYSTEM_AGENTS = [
  { id: 'ada', name: 'Ada', role: 'AI Architect & System Evolution Manager', purpose: 'Designs and evaluates improvements to Li OS, AI models, tools and integrations.', boundary: 'System changes are proposals until approved. This profile grants no execution or deployment authority.' },
  { id: 'theo', name: 'Theo', role: 'Personal Memory & Knowledge Curator', purpose: 'Maintains the quality, structure, provenance and continuity of personal memory.', boundary: 'Must preserve sources and confidence, never invent personal facts, and never silently turn an inference into a fact. This profile exposes no private memory.' },
  { id: 'heimdall', name: 'Heimdall', role: 'Security & Privacy Guardian', purpose: 'Protects information and Li OS against inappropriate access, data leakage and unsafe changes.', boundary: 'Reviews security boundaries and can flag excessive permissions and block unsafe system changes. This profile reveals no secrets or security logs.' },
];
function openSystemAgent(item) {
  setView('system-agent');
  const heading = $('#system-agent-heading'); heading.replaceChildren();
  const profile = document.createElement('div'); profile.className = 'specialist-profile';
  const button = document.createElement('button'); button.type = 'button';
  button.className = 'specialist-portrait-button';
  button.setAttribute('aria-label', `View full portrait of ${item.name}`);
  button.setAttribute('aria-haspopup', 'dialog');
  button.appendChild(createSpecialistAvatar(item));
  button.addEventListener('click', () => openSpecialistPortrait(item));
  const copy = document.createElement('div'); const title = document.createElement('h2');
  title.textContent = item.name; const role = document.createElement('p');
  role.className = 'muted'; role.textContent = item.role;
  copy.append(title, role); profile.append(button, copy); heading.appendChild(profile);
  $('#system-agent-purpose').textContent = item.purpose;
  $('#system-agent-boundary').textContent = item.boundary;
  $('#system-agent-back').focus();
}
function renderSystemAgents() {
  for (const selector of ['#directory-system-agents', '#backend-system-agents']) {
    const host = $(selector); host.replaceChildren();
    for (const item of SYSTEM_AGENTS) {
      const card = document.createElement('button'); card.type = 'button';
      card.className = 'system-agent-card'; card.dataset.systemAgentId = item.id;
      const copy = document.createElement('span'); const name = document.createElement('strong');
      name.textContent = item.name; const role = document.createElement('small'); role.textContent = item.role;
      copy.append(name, role); card.append(createSpecialistAvatar(item), copy);
      card.addEventListener('click', () => openSystemAgent(item)); host.appendChild(card);
    }
  }
}
function createSpecialistAvatar(item) {
  const avatar = document.createElement('span');
  avatar.className = 'specialist-avatar';
  avatar.setAttribute('aria-hidden', 'true');
  const initials = typeof item.initials === 'string' ? item.initials : (item.name || '?').slice(0, 2).toUpperCase();
  avatar.textContent = initials;
  if (SPECIALIST_PORTRAITS.has(item.id)) {
    const portrait = document.createElement('img');
    portrait.src = `/assets/portraits/${item.id}.png`;
    portrait.alt = ''; portrait.width = 64; portrait.height = 64;
    portrait.loading = 'lazy'; portrait.decoding = 'async';
    portrait.addEventListener('error', () => avatar.replaceChildren(document.createTextNode(initials)), { once: true });
    avatar.appendChild(portrait);
  }
  return avatar;
}
function closeSpecialistPortrait() {
  const dialog = $('#specialist-portrait-dialog');
  if (dialog.open) dialog.close();
}
function openSpecialistPortrait(item) {
  if (!SPECIALIST_PORTRAITS.has(item.id)) return;
  const dialog = $('#specialist-portrait-dialog');
  const host = $('#specialist-portrait-image');
  const status = $('#specialist-portrait-status');
  $('#specialist-portrait-name').textContent = item.name;
  $('#specialist-portrait-role').textContent = item.role;
  const portrait = document.createElement('img');
  portrait.alt = `Portrait of ${item.name}`;
  portrait.width = 1254; portrait.height = 1254;
  portrait.decoding = 'async';
  status.textContent = 'Loading portrait…';
  portrait.addEventListener('load', () => {
    if (host.contains(portrait)) status.textContent = '';
  });
  portrait.addEventListener('error', () => {
    if (!host.contains(portrait)) return;
    portrait.hidden = true;
    status.textContent = 'This portrait could not be loaded. Close and try again.';
  });
  host.replaceChildren(portrait);
  portrait.src = `/assets/portraits/${item.id}.png`;
  $('#specialist-portrait-original').href = portrait.src;
  if (!dialog.open) dialog.showModal();
}
$('#specialist-portrait-close').addEventListener('click', closeSpecialistPortrait);
$('#specialist-portrait-dialog').addEventListener('close', () => {
  if (!$('#specialist-portrait-dialog').open) $('#specialist-portrait-image').replaceChildren();
});
function renderSpecialists() { const list = $('#specialist-list'); list.replaceChildren(); const sorted = [...state.specialists].sort((a, b) => Number(b.active) - Number(a.active)); sorted.forEach((item) => { const button = document.createElement('button'); button.className = `specialist-card${item.active ? ' active' : ''}`; button.dataset.specialistId = item.id; const avatar = createSpecialistAvatar(item); const copy = document.createElement('span'); const name = document.createElement('strong'); name.textContent = item.name; const role = document.createElement('small'); role.textContent = item.role; copy.append(name, role); const status = document.createElement('span'); status.className = 'specialist-status'; status.textContent = item.status; button.append(avatar, copy, status); button.addEventListener('click', () => openSpecialist(item)); list.appendChild(button); }); $('#specialist-count').textContent = `${sorted.filter((item) => item.active).length} active`; $('#home-specialists-all').textContent = `View all ${sorted.length} specialists`; }
function compactEmpty(host, message) { host.replaceChildren(); const empty = document.createElement('p'); empty.className = 'muted'; empty.textContent = message; host.appendChild(empty); }
function compactRows(host, rows, label, meta) { host.replaceChildren(); rows.slice(0, 3).forEach((item) => { const row = document.createElement('div'); row.className = 'compact-item'; const title = document.createElement('strong'); title.textContent = label(item); const detail = document.createElement('small'); detail.textContent = meta(item); row.append(title, detail); host.appendChild(row); }); }
function renderHomeGlance(results) {
  const values = new Map(results.map((result) => [result.source.metric, result]));
  for (const [metric, result] of values) {
    $(metric).textContent = result.available ? String(result.count) : '—';
  }
  const loaded = results.filter((result) => result.available).length;
  $('#home-glance-status').textContent = loaded === results.length
    ? `All ${loaded} live sections loaded just now.`
    : `${loaded} of ${results.length} live sections loaded; unavailable data remains unknown.`;
}
async function loadHomeData() {
  const sources = [
    { url: '/api/conversations', selector: '#home-conversations', key: 'conversations', metric: '#home-glance-conversations', empty: 'No conversations yet.', label: (item) => item.title, meta: (item) => new Date(item.updated_at).toLocaleString(), count: (rows) => rows.length },
    { url: '/api/open-loops', selector: '#home-open-loops', key: 'open_loops', metric: '#home-glance-open-loops', empty: 'No open loops.', label: (item) => item.commitment_summary || item.title || item.summary || String(item.category || 'Open loop').replaceAll('_', ' '), meta: (item) => item.status?.replaceAll('_', ' ') || 'Open', count: (rows) => rows.length },
    { url: '/api/proactive-briefs', selector: '#home-briefs', key: 'briefs', metric: '#home-glance-briefs', empty: 'No proactive briefs. Rhythms remain quiet until activated.', label: (item) => item.title, meta: (item) => item.read_at ? 'Read' : 'Unread', count: (rows) => rows.filter((item) => !item.read_at).length },
    { url: '/api/artifacts', selector: '#home-artifacts', key: 'artifacts', metric: '#home-glance-artifacts', empty: 'No saved artifacts.', label: (item) => item.safe_filename, meta: (item) => item.retention_state === 'kept' ? 'Kept' : `Expires ${new Date(item.expires_at).toLocaleDateString()}`, count: (rows) => rows.length },
  ];
  $('#home-glance-status').textContent = 'Loading real activity…';
  const results = await Promise.all(sources.map(async (source) => {
    const host = $(source.selector);
    try {
      const response = await fetch(source.url);
      if (!response.ok) throw new Error();
      const rows = (await response.json())[source.key];
      if (!Array.isArray(rows)) throw new Error();
      const count = source.count(rows);
      if (!Number.isInteger(count) || count < 0) throw new Error();
      if (!rows.length) compactEmpty(host, source.empty);
      else compactRows(host, rows, source.label, source.meta);
      return { source, count, available: true };
    } catch {
      compactEmpty(host, 'This data is unavailable right now.');
      return { source, count: null, available: false };
    }
  }));
  renderHomeGlance(results);
}
async function loadSpecialists() { let unavailable = false; try { const response = await fetch('/api/specialists'); if (!response.ok) throw new Error(); state.specialists = (await response.json()).specialists; } catch { state.specialists = []; unavailable = true; } renderSpecialists(); if (unavailable) { $('#specialist-count').textContent = 'Activity unavailable'; $('#specialist-list').textContent = 'Specialist activity could not be loaded. Try again later.'; } }
function evidencePanel(entry) { const metadata = entry.outcome?.validation?.freshness_evidence; if (!metadata) return null; const panel = document.createElement('aside'); panel.className = 'evidence-panel'; const title = document.createElement('h3'); title.textContent = 'Evidence & freshness'; const facts = document.createElement('dl'); facts.className = 'evidence-facts'; const rows = [['Verification', metadata.verification_passed === true ? 'Passed' : metadata.verification_passed === false ? 'Not passed' : metadata.evidence_required === true ? 'Required · not recorded as performed' : metadata.evidence_required === false ? 'Not required' : 'Not recorded'], ['Freshness', typeof metadata.freshness_status === 'string' ? metadata.freshness_status.replaceAll('_', ' ') : 'Not recorded'], ['Source class', (Array.isArray(metadata.selected_source_class) ? metadata.selected_source_class.join(', ') : Object.keys(metadata.source_class_summary || {}).join(', ')) || 'Not recorded'], ['Citations', Number.isFinite(metadata.evidence_count) ? String(metadata.evidence_count) : 'Not measured']]; rows.forEach(([label, value]) => { const wrap = document.createElement('div'); const dt = document.createElement('dt'); dt.textContent = label; const dd = document.createElement('dd'); dd.textContent = value; wrap.append(dt, dd); facts.appendChild(wrap); }); panel.append(title, facts); return panel; }
let specialistView;
async function openSpecialist(item, initialTab = 'live') { state.currentSpecialist = item; setView('specialist'); const heading = $('#specialist-detail-heading'); heading.replaceChildren(); const profile = document.createElement('div'); profile.className = 'specialist-profile'; const avatar = createSpecialistAvatar(item); const copy = document.createElement('div'); const title = document.createElement('h2'); title.textContent = item.name; const role = document.createElement('p'); role.className = 'muted'; role.textContent = `${item.role} · adviser to Li`; copy.append(title, role); profile.append(avatar, copy); heading.appendChild(profile);
  if (SPECIALIST_PORTRAITS.has(item.id)) {
    const portraitButton = document.createElement('button');
    portraitButton.type = 'button'; portraitButton.className = 'specialist-portrait-button';
    portraitButton.setAttribute('aria-label', `View full portrait of ${item.name}`);
    portraitButton.setAttribute('aria-haspopup', 'dialog');
    portraitButton.title = 'View full portrait';
    avatar.replaceWith(portraitButton); portraitButton.appendChild(avatar);
    portraitButton.addEventListener('click', () => openSpecialistPortrait(item));
  }
  specialistView ||= window.LiSpecialists.create({ document, fetch, evidencePanel,
    workspace: window.LiWorkspace?.create({ document, fetch, avatar: createSpecialistAvatar,
      ownerAvatar: () => profilePhoto.avatar('workspace-avatar'),
      owner: () => ({ name: state.displayName || 'You' }), isBusy: () => state.sending,
      onActions: items => items.forEach(renderActionIntent),
      onActivity: (id, records) => specialistView?.updateRecords(id, records),
      confirmDiscard: () => window.confirm('Discard the unsent message and temporary attachment before switching conversations?') }),
    onConversation: async (id) => {
    setView('history');
    $('#history-list').textContent = 'Loading conversation…';
    try { await loadConversation(id); } catch { $('#history-list').textContent = 'Conversation is unavailable.'; }
  } });
  await specialistView.open(item, initialTab);
}
function renderHistory() { const list = $('#history-list'); list.replaceChildren(); state.history.forEach((entry) => { const item = document.createElement('div'); item.className = `history-item ${entry.role}`; const label = document.createElement('strong'); label.textContent = entry.role === 'user' ? 'You' : 'Li'; const text = document.createElement('p'); text.textContent = entry.text; item.append(label, text); list.appendChild(item); }); }
async function loadArtifacts() { const list = $('#artifact-list'); list.replaceChildren(); try { const response = await fetch('/api/artifacts'); if (!response.ok) throw new Error(); const data = await response.json(); if (!data.artifacts.length) { list.textContent = 'No saved files yet.'; return; } data.artifacts.forEach((artifact) => { const row = document.createElement('div'); row.className = 'artifact-row'; row.appendChild(attachmentChip({ ...artifact, filename: artifact.safe_filename, url: `/api/artifacts/${artifact.artifact_id}` })); const status = document.createElement('small'); status.className = 'muted'; status.textContent = artifact.retention_state === 'kept' ? 'Kept permanently' : `Expires ${new Date(artifact.expires_at).toLocaleString()}`; row.appendChild(status); list.appendChild(row); }); } catch { list.textContent = 'Private files are unavailable.'; } }
async function loadConversations() { const list = $('#conversation-list'); list.replaceChildren(); try { const response = await fetch('/api/conversations'); const data = await response.json(); data.conversations.forEach((conversation) => { const row = document.createElement('div'); row.className = 'conversation-row'; const button = document.createElement('button'); button.className = 'history-item conversation-choice'; button.textContent = `${conversation.title} · ${new Date(conversation.updated_at).toLocaleString()}`; button.addEventListener('click', () => loadConversation(conversation.conversation_id)); const remove = document.createElement('button'); remove.className = 'text-button danger'; remove.textContent = 'Delete'; remove.setAttribute('aria-label', `Delete conversation ${conversation.title}`); remove.addEventListener('click', async () => { if (!window.confirm('Delete this private conversation and its linked specialist history? Active data is removed now; encrypted database backups age out under the documented provider schedule.')) return; remove.disabled = true; const deleted = await fetch(`/api/conversations/${encodeURIComponent(conversation.conversation_id)}/delete`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({confirmation: 'delete_private_conversation'}) }); if (deleted.ok) { if (state.conversationId === conversation.conversation_id) { state.conversationId = null; state.history = []; renderHistory(); } row.remove(); } else { remove.disabled = false; remove.textContent = 'Delete failed safely'; } }); row.append(button, remove); list.appendChild(row); }); } catch { list.textContent = 'Conversation history is unavailable.'; } await loadArtifacts(); }
async function loadConversation(id) { const response = await fetch(`/api/conversations/${encodeURIComponent(id)}`); if (!response.ok) { $('#history-list').textContent = 'Conversation is unavailable or no longer retained.'; return; } const data = await response.json(); state.conversationId = id; state.history = data.messages.map((message) => ({ role: message.role, text: message.content })); renderHistory(); }
async function loadPrivacy() { try { const response = await fetch('/api/privacy/settings'); const data = await response.json(); $('#artifact-retention').value = String(data.artifact_retention_days); $('#privacy-status').textContent = 'Private storage is active. Deletion removes active objects promptly; provider backups age out under the documented backup schedule.'; } catch { $('#privacy-status').textContent = 'Privacy settings are unavailable.'; } }

function metric(label, value) { const card = document.createElement('article'); card.className = 'panel metric-card'; const strong = document.createElement('strong'); strong.textContent = value; const small = document.createElement('small'); small.textContent = label; card.append(strong, small); return card; }
async function loadAgentAnalytics() { const period = $('#analytics-period').value; const list = $('#agent-analytics-list'); list.textContent = 'Loading measured activity…'; try { const response = await fetch(`/api/agents/analytics?period=${period}`); if (!response.ok) throw new Error(); const data = await response.json(); $('#relevance-cadence').value = data.settings.relevance_cadence_months == null ? '' : String(data.settings.relevance_cadence_months); $('#analytics-summary').replaceChildren(metric('Requests', data.total_requests), metric('Specialist calls', data.total_agent_calls), metric('Active agents', data.agents.filter((agent) => agent.request_count).length)); $('#agent-summary-value').textContent = `${data.agents.filter((agent) => agent.active).length} working · ${data.total_agent_calls} calls`; list.replaceChildren(); [...data.agents].sort((a, b) => Number(b.active) - Number(a.active) || b.request_count - a.request_count).forEach((agent) => { const card = document.createElement('article'); card.className = `panel analytics-agent${agent.active ? ' active' : ''}`; const heading = document.createElement('div'); heading.className = 'panel-heading'; const title = document.createElement('div'); const name = document.createElement('strong'); name.textContent = agent.name; const role = document.createElement('small'); role.textContent = `${agent.role} · ${agent.active ? 'active' : agent.state}`; title.append(name, role); const detail = document.createElement('button'); detail.className = 'text-button analytics-history'; detail.textContent = 'History'; detail.addEventListener('click', () => openSpecialist({...agent, initials: agent.name.slice(0, 2).toUpperCase()}, 'history')); const identity = document.createElement('div'); identity.className = 'specialist-identity'; identity.append(createSpecialistAvatar(agent), title); heading.append(identity, detail); const values = document.createElement('p'); values.className = 'analytics-values'; values.textContent = `${agent.request_count} requests · ${agent.usage_share_pct}% usage · ${agent.active_days} active days · ${agent.solo_usage} solo / ${agent.multi_agent_usage} multi`; const note = document.createElement('small'); note.className = 'muted'; note.textContent = `Response time: ${agent.average_response_seconds == null ? 'not reliably available' : `${agent.average_response_seconds}s avg`} · Impact and uniqueness are labelled inferred.`; const workspace = document.createElement('button'); workspace.type = 'button'; workspace.className = 'analytics-workspace-link'; workspace.setAttribute('aria-label', `Open ${agent.name} Workspace`); workspace.addEventListener('click', () => openSpecialist(agent)); card.append(heading, values, note, workspace); list.appendChild(card); }); } catch { list.textContent = 'Agent analytics are unavailable right now.'; } }
function renderRecommendations(items) { const list = $('#recommendation-list'); list.replaceChildren(); items.forEach((item) => { const row = document.createElement('article'); row.className = 'recommendation'; const copy = document.createElement('p'); copy.textContent = `${item.action.toUpperCase()} ${item.subject_agent}: ${item.rationale}`; row.append(copy); ['approve', 'reject'].forEach((decision) => { const button = document.createElement('button'); button.className = decision === 'approve' ? 'primary-button' : 'secondary-button'; button.textContent = decision === 'approve' ? 'Approve for controlled execution' : 'Reject'; button.addEventListener('click', async () => { const response = await fetch(`/api/agents/recommendations/${item.recommendation_id}/review`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({decision}) }); if (!response.ok) { button.textContent = 'Could not update'; return; } button.disabled = true; if (decision === 'reject') { button.textContent = 'Rejected'; return; } button.textContent = 'Approved · execution pending'; const execute = document.createElement('button'); execute.className = 'primary-button'; execute.textContent = item.action === 'keep' ? 'Confirm and close recommendation' : 'Confirm permanent registry change'; execute.addEventListener('click', async () => { if (!window.confirm(`Owner confirmation: execute ${item.action} for ${item.subject_agent}?`)) return; execute.disabled = true; const result = await fetch(`/api/agents/recommendations/${item.recommendation_id}/execute`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ confirmation: 'confirm_permanent_agent_change', idempotency_key: crypto.randomUUID() }) }); const data = await result.json(); execute.textContent = result.ok ? (data.outcome === 'failed' ? 'Execution failed safely' : 'Executed and audited') : 'Could not execute safely'; if (!result.ok || data.outcome === 'failed') execute.disabled = false; }); row.append(execute); }); row.append(button); }); list.appendChild(row); }); }

function systemTheme() { return matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'; }
function sunTimes(date, latitude, longitude) { const rad = Math.PI / 180; const day = Math.floor((Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()) - Date.UTC(date.getFullYear(), 0, 0)) / 86400000); const lngHour = longitude / 15; function eventTime(rise) { const t = day + ((rise ? 6 : 18) - lngHour) / 24; const m = 0.9856 * t - 3.289; let l = m + 1.916 * Math.sin(m * rad) + 0.02 * Math.sin(2 * m * rad) + 282.634; l = (l + 360) % 360; let ra = Math.atan(0.91764 * Math.tan(l * rad)) / rad; ra = ((ra + 360) % 360 + (Math.floor(l / 90) * 90 - Math.floor(ra / 90) * 90)) / 15; const sinDec = 0.39782 * Math.sin(l * rad); const cosDec = Math.cos(Math.asin(sinDec)); const cosH = (Math.cos(90.833 * rad) - sinDec * Math.sin(latitude * rad)) / (cosDec * Math.cos(latitude * rad)); if (cosH < -1 || cosH > 1) return null; let h = (rise ? 360 - Math.acos(cosH) / rad : Math.acos(cosH) / rad) / 15; const utc = (h + ra - 0.06571 * t - 6.622 - lngHour + 24) % 24; return new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate(), 0, Math.round(utc * 60))); } return { sunrise: eventTime(true), sunset: eventTime(false) }; }
const themeLibrary = window.LiThemes.library(preferenceStorage);
let themeRequest = 0;
let editingThemeId = null;
let themeImportRequest = 0;
function applyTheme(theme, note = '') {
  window.LiThemes.apply(themeLibrary.find(theme), document.documentElement, document.querySelector('meta[name="theme-color"]'));
  $('#theme-status').textContent = note || 'Appearance applies on this device. Content and permissions are unchanged.';
  $$('#theme-library [data-theme-choice]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.themeChoice === state.theme)));
  $('#theme-edit-selected').disabled = !state.theme.startsWith('custom-');
}
function activateTheme(choice) {
  const request = ++themeRequest;
  state.theme = choice === 'auto' ? choice : themeLibrary.find(choice).id;
  choice = state.theme;
  savePreference('li-theme', choice);
  if (choice !== 'auto') { applyTheme(choice); return; }
  const resolved = (theme, note) => { if (request === themeRequest && state.theme === 'auto') applyTheme(theme, note); };
  resolved(systemTheme(), 'Auto follows Light/Dark. Checking local sunrise and sunset…');
  if (!navigator.geolocation) { resolved(systemTheme(), 'Location is unavailable, so Auto follows your system theme.'); return; }
  navigator.geolocation.getCurrentPosition(({ coords }) => {
    const times = sunTimes(new Date(), coords.latitude, coords.longitude);
    if (!times.sunrise || !times.sunset) { resolved(systemTheme(), 'Sunrise/sunset is unavailable here today, so Auto follows your system theme.'); return; }
    const now = new Date();
    resolved(now >= times.sunrise && now < times.sunset ? 'light' : 'dark', 'Following today’s local sunrise and sunset. Your coordinates were not saved.');
  }, () => resolved(systemTheme(), 'Location was not shared, so Auto follows your system theme.'), { enableHighAccuracy: false, timeout: 8000, maximumAge: 3600000 });
}
function renderThemeLibrary() {
  const host = $('#theme-library'); host.replaceChildren();
  for (const theme of [...themeLibrary.all(), { id: 'auto', name: 'Auto', description: 'Light/Dark by sunrise or system preference' }]) {
    const button = document.createElement('button'); button.type = 'button'; button.className = 'theme-choice';
    button.dataset.themeChoice = theme.id; button.setAttribute('aria-pressed', String(theme.id === state.theme));
    const title = document.createElement('strong'); title.textContent = theme.name;
    const note = document.createElement('small'); note.textContent = theme.description || `${theme.mode === 'dark' ? 'Dark' : 'Light'} palette · ${theme.font}`;
    button.append(title, note); button.addEventListener('click', () => activateTheme(theme.id)); host.appendChild(button);
  }
}
function initializeAppearance() {
  renderThemeLibrary();
  const displayedTheme = () => themeLibrary.find(document.documentElement.dataset.theme);
  const openEditor = (theme, id = null) => {
    ++themeImportRequest;
    editingThemeId = id;
    $('#theme-transfer-status').textContent = '';
    for (const field of ['name', 'mode', ...window.LiThemes.colors, 'font', 'radius']) $(`#theme-${field}`).value = theme[field];
    $('#theme-editor-panel').open = true;
    $('#theme-editor-heading').textContent = id ? `Edit ${theme.name}` : 'Create another theme';
    $('#theme-save').textContent = id ? 'Save changes and use theme' : 'Save and use theme';
    $('#theme-editor-status').textContent = id ? 'Changes replace this custom theme only after you save.' : 'Review these settings, then save as a new theme. Existing themes stay unchanged.';
    $('#theme-name').focus();
  };
  $('#theme-edit-selected').addEventListener('click', () => {
    if (state.theme.startsWith('custom-')) openEditor(themeLibrary.find(state.theme), state.theme);
  });
  $('#theme-copy-selected').addEventListener('click', () => openEditor({ ...displayedTheme(), name: '' }));
  $('#theme-editor-cancel').addEventListener('click', () => {
    openEditor({ ...themeLibrary.find('forest'), name: '' });
    $('#theme-editor-panel').open = false;
    $('#theme-copy-selected').focus();
  });
  $('#theme-export').addEventListener('click', () => {
    let url;
    try {
      const text = window.LiThemes.serialize(displayedTheme());
      url = URL.createObjectURL(new Blob([text], { type: 'application/json' }));
      const link = document.createElement('a'); link.href = url; link.download = 'li-appearance.json';
      document.body.appendChild(link); link.click(); link.remove();
      $('#theme-transfer-status').textContent = 'Download requested. The file contains appearance settings only. You can import it on another device.';
    } catch { $('#theme-transfer-status').textContent = 'This browser could not export the appearance. Please try again.'; }
    finally { if (url) setTimeout(() => URL.revokeObjectURL(url), 1000); }
  });
  $('#theme-import').addEventListener('change', async event => {
    const file = event.target.files?.[0]; event.target.value = '';
    if (!file) return;
    const request = ++themeImportRequest;
    $('#theme-transfer-status').textContent = 'Checking appearance file…';
    try {
      if (file.size > window.LiThemes.transferLimit) throw new Error('Choose a Li appearance JSON file no larger than 16 KB.');
      const text = await file.text();
      if (request !== themeImportRequest) return;
      const draft = window.LiThemes.parseTransfer(text);
      openEditor(draft);
      $('#theme-transfer-status').textContent = 'Imported into the editor only. Review the settings and press Save to add it.';
    } catch (error) {
      if (request === themeImportRequest) $('#theme-transfer-status').textContent = error.message || 'This file could not be read.';
    }
  });
  for (const name of ['input', 'change']) $('#theme-editor').addEventListener(name, () => {
    ++themeImportRequest;
    $('#theme-transfer-status').textContent = '';
  });
  $('#theme-editor').addEventListener('submit', event => {
    event.preventDefault();
    ++themeImportRequest;
    const draft = {};
    for (const field of ['name', 'mode', ...window.LiThemes.colors, 'font', 'radius']) draft[field] = $(`#theme-${field}`).value;
    try {
      const theme = editingThemeId ? themeLibrary.update(draft, editingThemeId) : themeLibrary.save(draft, `custom-${crypto.randomUUID()}`);
      renderThemeLibrary(); activateTheme(theme.id);
      editingThemeId = theme.id;
      $('#theme-editor-heading').textContent = `Edit ${theme.name}`;
      $('#theme-save').textContent = 'Save changes and use theme';
      $('#theme-editor-status').textContent = `Saved "${theme.name}". It is now available in Appearance on this device.`;
    } catch (error) { $('#theme-editor-status').textContent = error.message; }
  });
}

$$('button[data-view]').forEach((button) => button.addEventListener('click', () => setView(button.dataset.view)));
$('#back-home').addEventListener('click', () => setView('home')); $('#handoff-to-li').addEventListener('click', () => { const specialist = state.currentSpecialist; setView('home'); if (specialist) $('#message-input').value = `Continue with Li about my work with ${specialist.name}.`; $('#message-input').focus(); }); $('#composer').addEventListener('submit', (event) => { event.preventDefault(); const value = $('#message-input').value.trim(); if (value) sendMessage(value); }); $('#message-input').addEventListener('keydown', (event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); $('#composer').requestSubmit(); } }); $('#message-input').addEventListener('input', (event) => { event.target.style.height = 'auto'; event.target.style.height = `${Math.min(event.target.scrollHeight, 120)}px`; if (!state.sending && $('#microphone-button').getAttribute('aria-pressed') !== 'true') setLiState('idle'); }); $('#attach-button').addEventListener('click', () => $('#file-input').click()); $('#file-input').addEventListener('change', (event) => { if (event.target.files[0]) handleFile(event.target.files[0]); event.target.value = ''; }); const drop = $('#conversation-panel'); ['dragenter', 'dragover'].forEach((name) => drop.addEventListener(name, (event) => { event.preventDefault(); drop.classList.add('dragging'); })); ['dragleave', 'drop'].forEach((name) => drop.addEventListener(name, (event) => { event.preventDefault(); drop.classList.remove('dragging'); })); drop.addEventListener('drop', (event) => { if (event.dataTransfer.files[0]) handleFile(event.dataTransfer.files[0]); }); $$('[data-theme-choice]').forEach((button) => button.addEventListener('click', () => activateTheme(button.dataset.themeChoice))); $('#logout-button').addEventListener('click', async () => { await fetch('/auth/logout', { method: 'POST' }); await loadSession(); }); $('#account-button').addEventListener('click', () => setView('settings')); matchMedia('(prefers-color-scheme: light)').addEventListener('change', () => { if (state.theme === 'auto') activateTheme('auto'); });
$('#microphone-button').addEventListener('click', () => { if ($('#microphone-button').getAttribute('aria-pressed') === 'true') cancelVoiceInput(); else startVoiceInput(); }); $('#voice-cancel').addEventListener('click', cancelVoiceInput); $('#stop-speaking').addEventListener('click', stopSpeaking); $('#voice-output-toggle').addEventListener('click', () => { state.voiceOutput = !state.voiceOutput; savePreference('li-voice-output', state.voiceOutput ? 'on' : 'off'); if (!state.voiceOutput) stopSpeaking(); updateVoiceOutputControl(); });
$('#install-app').addEventListener('click', installApp); window.addEventListener('beforeinstallprompt', (event) => { event.preventDefault(); state.installPrompt = event; updateInstallControl(); }); window.addEventListener('appinstalled', () => { state.installPrompt = null; updateInstallControl('Li is installed on this device.'); });
window.addEventListener('offline', updateConnectivity); window.addEventListener('online', () => loadSession());
$('#profile-photo-remove').addEventListener('click', () => profilePhoto.remove(window.confirm('Remove your profile photo and return to CM on all devices?')));
window.addEventListener('focus', () => { if (state.signedIn && document.visibilityState !== 'hidden') profilePhoto.load(); });
$('#artifact-retention').addEventListener('change', async (event) => { const response = await fetch('/api/privacy/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ artifact_retention_days: Number(event.target.value) }) }); $('#privacy-status').textContent = response.ok ? `Li-created files now expire after ${event.target.value} days unless kept.` : 'Could not update retention.'; });
$('#analytics-period').addEventListener('change', loadAgentAnalytics); $('#relevance-cadence').addEventListener('change', async (event) => { await fetch('/api/agents/settings', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ relevance_cadence_months: event.target.value ? Number(event.target.value) : null }) }); }); $('#run-relevance').addEventListener('click', async () => { const button = $('#run-relevance'); button.disabled = true; const response = await fetch('/api/agents/relevance-review', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({period: $('#analytics-period').value}) }); if (response.ok) renderRecommendations((await response.json()).recommendations); button.disabled = false; });
['capability-search', 'capability-category', 'capability-status', 'capability-access'].forEach((id) => $(`#${id}`).addEventListener('input', renderCapabilities));
if ('serviceWorker' in navigator) window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js'));
const freshnessPanel = document.createElement('article'); freshnessPanel.className = 'panel'; const freshnessHeading = document.createElement('h3'); freshnessHeading.textContent = 'Freshness & Evidence'; const freshnessNote = document.createElement('p'); freshnessNote.className = 'muted'; freshnessNote.textContent = 'Read-only specialist policy. Stable knowledge stays separate from live world state.'; const freshnessList = document.createElement('div'); freshnessList.id = 'freshness-policy-list'; freshnessList.className = 'capability-grid'; freshnessPanel.append(freshnessHeading, freshnessNote, freshnessList); const backendNotes = $('[data-view-panel="backend"] .backend-notes'); if (backendNotes) backendNotes.before(freshnessPanel);
const providerPanel = document.createElement('article'); providerPanel.className = 'panel'; const providerHeading = document.createElement('h3'); providerHeading.textContent = 'Provider Coverage & Source Authority'; const providerNote = document.createElement('p'); providerNote.className = 'muted'; providerNote.textContent = 'Read-only declared coverage. No credentials, secret identifiers, or invented reliability metrics.'; const providerList = document.createElement('div'); providerList.id = 'provider-coverage-list'; providerList.className = 'capability-grid'; providerPanel.append(providerHeading, providerNote, providerList); if (backendNotes) backendNotes.before(providerPanel);
renderSystemAgents(); $('#system-agent-back').addEventListener('click', () => setView('home')); initializeAppearance(); createPlaceSettings(); $('#page-title').textContent = greeting(); activateTheme(state.theme); initializeVoice(); updateInstallControl(); updateConnectivity(); loadSession();
