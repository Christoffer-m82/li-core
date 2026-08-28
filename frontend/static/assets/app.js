const state = { conversationId: null, history: [], signedIn: false, sending: false };
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => document.querySelectorAll(selector);

function setView(view) {
  $$('.view').forEach((panel) => panel.classList.toggle('active', panel.dataset.viewPanel === view));
  $$('.nav-item').forEach((button) => button.classList.toggle('active', button.dataset.view === view));
  const labels = { home: 'Good evening, Christoffer', chat: 'Talk with Li', history: 'Conversation history', settings: 'Settings' };
  $('#page-title').textContent = labels[view];
  if (view === 'chat') setTimeout(() => $('#message-input').focus(), 100);
}

function addMessage(role, text, temporary = false) {
  const row = document.createElement('div');
  row.className = `message ${role}${temporary ? ' typing' : ''}`;
  if (role === 'assistant') {
    const orb = document.createElement('span'); orb.className = 'li-orb tiny'; orb.textContent = 'Li'; row.appendChild(orb);
  }
  const content = document.createElement('div');
  const body = document.createElement('p'); body.textContent = text;
  const time = document.createElement('time'); time.textContent = 'Now';
  content.append(body, time); row.appendChild(content); $('#messages').appendChild(row);
  row.scrollIntoView({ behavior: 'smooth', block: 'end' });
  return row;
}

async function loadSession() {
  try {
    const response = await fetch('/api/session');
    state.signedIn = response.ok;
  } catch { state.signedIn = false; }
  $('#signed-out').classList.toggle('hidden', state.signedIn);
  $('#workspace').classList.toggle('hidden', !state.signedIn);
  if (!state.signedIn) { $('#connection-label').textContent = 'Sign in required'; return; }
  try {
    const ready = await fetch('/api/ready');
    $('#connection-label').textContent = ready.ok ? 'Li is online' : 'Li needs attention';
  } catch { $('#connection-label').textContent = 'Li is unreachable'; }
}

async function sendMessage(message) {
  if (state.sending) return;
  state.sending = true; addMessage('user', message); state.history.push(message);
  const pending = addMessage('assistant', 'Thinking…', true);
  $('#message-input').value = ''; $('#composer button').disabled = true;
  try {
    const response = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message, conversation_id: state.conversationId }) });
    if (response.status === 401) { await loadSession(); throw new Error('Your session has expired. Please sign in again.'); }
    if (!response.ok) throw new Error('Li could not respond just now. Please try again.');
    const data = await response.json(); state.conversationId = data.conversation_id; pending.remove(); addMessage('assistant', data.response); renderHistory();
  } catch (error) { pending.remove(); addMessage('assistant', error.message || 'Something went wrong.'); }
  finally { state.sending = false; $('#composer button').disabled = false; $('#message-input').focus(); }
}

function renderHistory() {
  const list = $('#history-list'); list.replaceChildren();
  state.history.slice().reverse().forEach((message) => { const p = document.createElement('p'); p.className = 'muted'; p.textContent = message; list.appendChild(p); });
}

$$('.nav-item[data-view]').forEach((button) => button.addEventListener('click', () => setView(button.dataset.view)));
$('#start-chat').addEventListener('click', () => setView('chat'));
$('#composer').addEventListener('submit', (event) => { event.preventDefault(); const value = $('#message-input').value.trim(); if (value) sendMessage(value); });
$('#message-input').addEventListener('keydown', (event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); $('#composer').requestSubmit(); } });
$('#message-input').addEventListener('input', (event) => { event.target.style.height = 'auto'; event.target.style.height = `${Math.min(event.target.scrollHeight, 140)}px`; });
$('#logout-button').addEventListener('click', async () => { await fetch('/auth/logout', { method: 'POST' }); await loadSession(); });
$('#account-button').addEventListener('click', () => setView('settings'));
if ('serviceWorker' in navigator) window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js'));
loadSession();

