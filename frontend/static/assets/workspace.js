/* Shared, bounded conversation view. All private content stays in memory, never browser storage. */
(() => {
  const validId = value => typeof value === 'string' && /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(value);
  const stamp = value => Number.isFinite(Date.parse(value)) ? Date.parse(value) : 0;
  const retryStore = typeof sessionStorage === 'undefined' ? null : sessionStorage;
  const fingerprint = value => {
    let hash = 2166136261;
    for (const char of JSON.stringify(value)) { hash ^= char.codePointAt(0); hash = Math.imul(hash, 16777619); }
    return (hash >>> 0).toString(16).padStart(8, '0');
  };
  const retryKey = specialist => `li-workspace-pending-v1:${specialist}`;
  const readRetry = (key, expected) => { try { const row = JSON.parse(retryStore?.getItem(key) || 'null'); return row?.fingerprint === expected ? row : null; } catch { return null; } };
  const writeRetry = (key, row) => { try { retryStore?.setItem(key, JSON.stringify(row)); } catch { /* In-memory retry still works. */ } };
  const removeRetry = key => { try { retryStore?.removeItem(key); } catch { /* Stale metadata contains no message content. */ } };
  function timeline(messages, interactions, conversationId) {
    const rows = messages.filter(m => ['user', 'assistant'].includes(m.role) && typeof m.content === 'string')
      .map(m => ({ id: m.message_id, sender: m.role === 'user' ? 'owner' : 'li', body: m.content, at: m.created_at }));
    interactions.filter(e => e.conversation_id === conversationId).forEach(e => {
      const outcome = e.outcome || {};
      // A routing record contains the owner's request, NOT a Li-authored message.
      if (typeof outcome.recommendation === 'string' && outcome.recommendation.trim()) {
        rows.push({ id: e.interaction_id, sender: 'specialist', body: outcome.recommendation,
          at: e.completed_at || e.updated_at, recorded: true,
          findings: outcome.findings, questions: outcome.follow_up_questions });
      } else {
        rows.push({ id: e.interaction_id, sender: 'event', at: e.updated_at || e.started_at,
          body: outcome.temporary_context?.content_retained === false ? 'Specialist response not retained: temporary file context was used.'
            : e.status === 'active' ? 'Consultation in progress. Refresh to check for a response.'
              : e.status === 'failed' ? 'Specialist consultation failed; no successful response is recorded.' : 'No specialist response content was recorded.' });
      }
    });
    return rows.sort((a, b) => stamp(a.at) - stamp(b.at) || String(a.id || '').localeCompare(String(b.id || '')));
  }
  function create({ document, fetch, avatar, ownerAvatar, owner = () => ({ name: 'You' }), isBusy = () => false,
    onActions = () => {}, onActivity = () => {}, confirmDiscard = () => true }) {
    let agent = null, entries = [], messages = [], conversationId = null, version = 0;
    let sending = false, uploading = false, ready = false, attachment = null, pendingSend = null, pendingBottom = false;
    let pendingTurnId = null, pendingTurnFingerprint = null;
    const root = document.querySelector('#specialist-live');
    const node = (tag, content = '', className = '') => {
      const el = document.createElement(tag); el.textContent = content; el.className = className; return el;
    };
    const label = (name, id) => { const el = node('label', name); el.htmlFor = id; return el; };
    const header = node('div', '', 'workspace-controls');
    const cases = node('select'); cases.id = 'workspace-case';
    const fresh = node('button', 'New conversation', 'secondary-button'); fresh.type = 'button';
    header.append(label('Conversation', cases.id), cases, fresh);
    const note = node('p', 'Shared with Li and this specialist. Direct messages are not private. Recent context from the selected conversation is shared for follow-ups.', 'truth-note');
    const log = node('div', '', 'workspace-log'); log.tabIndex = 0;
    log.setAttribute('role', 'region'); log.setAttribute('aria-label', 'Shared conversation history');
    const latest = node('button', 'Jump to latest', 'text-button'); latest.type = 'button';
    latest.addEventListener('click', () => { log.scrollTop = log.scrollHeight; });
    const limits = node('p', 'Latest 40 saved chat messages and up to 50 loaded specialist records. Older history may not be shown. Specialist bubbles are recorded recommendations, not a verbatim internal transcript.', 'muted workspace-limits');
    const status = node('p', '', 'workspace-status'); status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
    const form = node('form', '', 'workspace-composer');
    const recipient = node('select'); recipient.id = 'workspace-recipient';
    const input = node('textarea'); input.id = 'workspace-input'; input.rows = 3; input.maxLength = 10000;
    input.placeholder = 'Write to Li and your specialist…';
    const file = node('input'); file.id = 'workspace-file'; file.type = 'file';
    file.accept = '.txt,.md,.csv,.json,.pdf,.png,.jpg,.jpeg,.webp';
    const files = node('div', '', 'workspace-attachment');
    const remove = node('button', 'Remove attachment', 'text-button'); remove.type = 'button'; remove.hidden = true;
    const send = node('button', 'Send', 'primary-button'); send.type = 'submit';
    form.append(label('Address message to', recipient.id), recipient, label('Message', input.id), input,
      label('Attach a file · up to 10 MB · temporary analysis only', file.id), file, files, remove, send);
    root.append(header, note, limits, log, latest, status, form);
    function controls() {
      send.disabled = !ready || sending || uploading;
      [input, recipient, file, remove, cases, fresh].forEach(el => { el.disabled = !agent || sending || uploading; });
      send.textContent = sending ? 'Waiting for Li and specialist…' : 'Send';
    }
    function resetDraft() { input.value = ''; attachment = null; pendingTurnId = null; pendingTurnFingerprint = null; file.value = ''; files.replaceChildren(); remove.hidden = true; }
    function forgetPending() { if (agent) removeRetry(retryKey(agent.id)); pendingTurnId = null; pendingTurnFingerprint = null; }
    function choices() {
      const option = (value, title) => { const el = node('option', title); el.value = value; return el; };
      cases.replaceChildren(option('', 'New conversation'));
      const unique = new Map();
      entries.filter(e => validId(e.conversation_id)).forEach(e => { if (!unique.has(e.conversation_id)) unique.set(e.conversation_id, e); });
      for (const [id, entry] of unique) cases.append(option(id, (entry.request_text || 'Saved conversation').slice(0, 95)));
      if (conversationId && !unique.has(conversationId)) cases.append(option(conversationId, 'Current conversation'));
      cases.value = conversationId || '';
    }
    function render(bottom = false) {
      const nearBottom = log.scrollHeight - log.scrollTop - log.clientHeight < 80;
      const position = log.scrollTop;
      log.replaceChildren();
      const rows = timeline(messages, entries, conversationId);
      if (!rows.length) log.append(node('p', conversationId ? 'No retained messages in this loaded window.' : `Start a conversation with Li and ${agent.name}.`, 'truth-note'));
      rows.forEach(row => {
        if (row.sender === 'event') {
          const event = node('p', row.body, 'workspace-event');
          event.append(node('time', stamp(row.at) ? new Date(row.at).toLocaleString() : 'Time not recorded')); log.append(event); return;
        }
        const line = node('article', '', `workspace-message workspace-${row.sender}`);
        const person = row.sender === 'owner' ? owner() : row.sender === 'li' ? { name: 'Li' } : agent;
        const initials = person.initials || (person.name || '').trim().split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0].toUpperCase()).join('') || 'CM';
        const pic = row.sender === 'specialist' && avatar ? avatar(agent) : row.sender === 'owner' && ownerAvatar ? ownerAvatar() : node('span', row.sender === 'li' ? 'Li' : (person.name === 'You' ? 'CM' : initials), 'workspace-avatar');
        pic.setAttribute('aria-hidden', 'true');
        const bubble = node('div', '', 'workspace-bubble');
        bubble.append(node('strong', row.sender === 'owner' ? (person.name || 'You') : person.name), node('p', row.body));
        if (row.recorded) {
          const details = node('details'); details.append(node('summary', 'Recorded recommendation · supporting details'));
          [['Findings', row.findings], ['Questions', row.questions]].forEach(([title, values]) => {
            if (!Array.isArray(values)) return;
            const items = values.filter(v => typeof v === 'string'); if (!items.length) return;
            details.append(node('strong', title)); const list = node('ul'); items.forEach(v => list.append(node('li', v))); details.append(list);
          }); bubble.append(details);
        }
        const time = node('time', stamp(row.at) ? new Date(row.at).toLocaleString() : 'Time not recorded');
        if (stamp(row.at)) time.dateTime = row.at;
        bubble.append(time); line.append(pic, bubble); log.append(line);
      });
      if (log.clientHeight === 0) { pendingBottom ||= bottom; return; }
      log.scrollTop = bottom || nearBottom ? log.scrollHeight : position;
    }
    async function load(id, bottom = true) {
      const token = ++version; conversationId = id; messages = []; ready = !id; choices(); render(bottom); controls();
      if (!id) { status.textContent = 'New shared conversation.'; return; }
      status.textContent = 'Loading saved messages…';
      try {
        const response = await fetch(`/api/conversations/${encodeURIComponent(id)}`, { cache: 'no-store' });
        if (!response.ok) throw new Error();
        const data = await response.json();
        if (!Array.isArray(data.messages) || data.messages.some(m => !m || typeof m.content !== 'string')) throw new Error();
        if (token !== version) return;
        messages = data.messages; ready = true; render(bottom); status.textContent = 'Saved conversation loaded.';
      } catch { if (token === version) status.textContent = 'Conversation unavailable. Refresh to retry or start a new conversation; nothing has been sent.'; }
      finally { if (token === version) controls(); }
    }
    const canDiscard = () => !(input.value.trim() || attachment) || confirmDiscard();
    cases.addEventListener('change', () => { if (!canDiscard()) { cases.value = conversationId || ''; return; } forgetPending(); resetDraft(); return load(cases.value || null); });
    fresh.addEventListener('click', () => { if (!canDiscard()) return; forgetPending(); resetDraft(); return load(null); });
    remove.addEventListener('click', () => { attachment = null; file.value = ''; files.replaceChildren(); remove.hidden = true; });
    file.addEventListener('change', async () => {
      const item = file.files?.[0]; if (!item || sending || uploading) return;
      attachment = null; remove.hidden = true; files.textContent = '';
      if (item.size > 10 * 1024 * 1024) { status.textContent = 'Files must be 10 MB or smaller.'; file.value = ''; return; }
      const token = version; uploading = true; controls(); status.textContent = 'Analysing attachment temporarily…';
      try {
        const body = new FormData(); body.append('file', item); body.append('save', 'false');
        const response = await fetch('/api/uploads', { method: 'POST', body }); const data = await response.json();
        if (token !== version) return;
        if (!response.ok || typeof data.analysis_text !== 'string' || !data.analysis_text.trim()) {
          status.textContent = response.ok ? 'This file type cannot be analysed here yet. It has not been attached or retained. Try text, Markdown, CSV or JSON.' : 'Attachment could not be analysed. It has not been attached.';
          file.value = ''; return;
        }
        const context = `File: ${item.name}\n${data.analysis_text}`;
        if (context.length > 6000) { status.textContent = 'Extracted file content is too long. Attach a shorter excerpt (up to 6,000 characters).'; file.value = ''; return; }
        attachment = context; files.textContent = `${item.name} · ready for next message · not retained`; remove.hidden = false;
        status.textContent = 'Attachment ready. Li and the selected specialist receive it for this request only.';
      } catch { if (token === version) status.textContent = 'Upload unavailable. No attachment was added.'; }
      finally { if (token === version) { uploading = false; controls(); } }
    });
    form.addEventListener('submit', async event => {
      event.preventDefault(); const message = input.value.trim();
      if (!message || !ready || sending || uploading) return;
      if (isBusy()) { status.textContent = 'Wait for your current Li request to finish before sending here.'; return; }
      const token = version, operation = {}; pendingSend = operation;
      const envelopeFingerprint = fingerprint({message, conversationId, specialist: agent.id,
        recipient: recipient.value, attachment});
      if (pendingTurnFingerprint !== envelopeFingerprint) {
        const recovered = readRetry(retryKey(agent.id), envelopeFingerprint);
        pendingTurnId = recovered?.turnId || crypto.randomUUID();
        pendingTurnFingerprint = envelopeFingerprint;
      }
      writeRetry(retryKey(agent.id), {turnId: pendingTurnId, fingerprint: envelopeFingerprint});
      let received = false;
      sending = true; controls(); status.textContent = 'Sending in the shared conversation…';
      try {
        const response = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message, turn_id: pendingTurnId, conversation_id: conversationId, workspace_specialist: agent.id,
            workspace_recipient: recipient.value, temporary_upload_context: attachment }) });
        if (!response.ok) throw new Error(); const data = await response.json();
        if (token !== version) return;
        if (!validId(data.conversation_id) || typeof data.response !== 'string') throw new Error();
        received = true;
        onActions(data.action_intents || []);
        conversationId = data.conversation_id; forgetPending(); resetDraft();
        // Show the returned reply even if persistence is degraded. Do not manufacture specialist speech.
        const at = new Date().toISOString();
        messages.push({ role: 'user', content: message, created_at: at }, { role: 'assistant', content: data.response, created_at: at });
        choices(); render(true);
        const activity = await fetch(`/api/specialists/${encodeURIComponent(agent.id)}/interactions`, { cache: 'no-store' });
        if (token !== version) return;
        if (activity.ok) {
          const record = await activity.json();
          if (token !== version) return;
          if (!Array.isArray(record.interactions) || record.interactions.some(e => !e || typeof e !== 'object' || Array.isArray(e))) throw new Error('Invalid activity');
          entries = record.interactions;
          onActivity(agent.id, entries);
        }
        if (!data.conversation_history_error) {
          const saved = await fetch(`/api/conversations/${encodeURIComponent(conversationId)}`, { cache: 'no-store' });
          if (!saved.ok) throw new Error();
          const history = await saved.json(); if (token !== version) return;
          if (!Array.isArray(history.messages) || history.messages.some(m => !m || typeof m.content !== 'string')) throw new Error();
          messages = history.messages; render(true);
          status.textContent = activity.ok ? 'Reply received and saved. Li remains included.' : 'Reply saved; specialist activity could not be refreshed. Use Refresh to retry.';
        } else { render(true); status.textContent = 'Reply received, but this exchange was not fully saved. Visible messages may disappear after refresh.'; }
        if (data.turn_state === 'durability_unavailable') status.textContent += ' Safe replay confirmation is unavailable; refresh before resending.';
        if (data.action_intents?.length) status.textContent += ' Any proposed action still requires its normal approval in Li’s main chat.';
      } catch {
        if (token === version) status.textContent = received ? 'Reply received. History refresh failed; the returned reply is still shown. Refresh before sending again.' : 'The request could not be confirmed. Your draft is kept. Check Refresh before retrying to avoid a duplicate.';
      } finally { if (pendingSend === operation) { sending = false; pendingSend = null; controls(); } }
    });
    return {
      show() { if (pendingBottom && log.clientHeight > 0) { log.scrollTop = log.scrollHeight; pendingBottom = false; } },
      async open(item, records) {
        ++version; pendingSend = null; pendingBottom = false; agent = item; entries = records; sending = false; uploading = false; resetDraft();
        root.setAttribute('data-chat-specialist', item.id);
        const option = (value, text) => { const el = node('option', text); el.value = value; return el; };
        recipient.replaceChildren(option('group', `Li + ${agent.name}`), option('specialist', `${agent.name} directly · Li included`)); recipient.value = 'group';
        return load(entries.find(e => validId(e.conversation_id))?.conversation_id || null);
      },
      async refresh(records) { entries = records; if (!sending && !uploading) return load(conversationId, false); },
      async select(id) { if (sending || uploading) { status.textContent = 'Wait for the current request to finish.'; return; } if (!canDiscard()) return; resetDraft(); return load(id); },
      clear() { ++version; pendingSend = null; pendingBottom = false; sending = false; uploading = false; agent = null; entries = []; messages = []; conversationId = null; ready = false; resetDraft(); cases.replaceChildren(); recipient.replaceChildren(); log.replaceChildren(); status.textContent = ''; controls(); },
    };
  }
  (typeof window === 'undefined' ? globalThis : window).LiWorkspace = { create, timeline };
})();
