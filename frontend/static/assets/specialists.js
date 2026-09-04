/* Recorded specialist activity only. No generated transcripts or persistent browser data. */
(() => {
  const text = (value, fallback = 'Not recorded') => typeof value === 'string' && value.trim() ? value : fallback;
  const date = value => value && Number.isFinite(Date.parse(value)) ? new Date(value).toLocaleString() : 'Not recorded';
  const strings = value => Array.isArray(value) ? value.filter(item => typeof item === 'string') : [];
  function summary(entries) {
    const completed = entries.filter(e => e.status === 'completed');
    const durations = completed.map(e => e.elapsed_ms).filter(v => Number.isFinite(v) && v >= 0);
    return { total: entries.length, active: entries.filter(e => e.status === 'active').length,
      completed: completed.length, failed: entries.filter(e => e.status === 'failed').length,
      average: durations.length ? `${(durations.reduce((a, b) => a + b, 0) / durations.length / 1000).toFixed(1)}s` : 'Not measured' };
  }
  function filter(entries, query = '', status = 'all') {
    const needle = query.trim().toLocaleLowerCase();
    return entries.filter(e => (status === 'all' || e.status === status) &&
      [e.request_text, e.outcome?.recommendation, ...strings(e.outcome?.findings)].some(v => text(v, '').toLocaleLowerCase().includes(needle)));
  }
  function create({ document, fetch, evidencePanel, onConversation }) {
    const $ = id => document.querySelector(`#${id}`);
    let entries = [], selected = null, agent = null, generation = 0;
    const node = (tag, content, className = '') => {
      const el = document.createElement(tag); el.textContent = content; el.className = className; return el;
    };
    function facts(rows) {
      const dl = node('dl', '', 'evidence-facts');
      rows.forEach(([label, value]) => { const pair = node('div', ''); pair.append(node('dt', label), node('dd', value)); dl.append(pair); });
      return dl;
    }
    function detail(entry, target) {
      target.replaceChildren();
      const conversation = node('article', '', 'specialist-exchange');
      conversation.append(node('h3', 'Recorded exchange'), node('p', 'The saved request and structured specialist response—not a verbatim multi-message transcript.', 'muted'));
      conversation.append(node('h4', 'Request routed by Li'), node('p', text(entry.request_text), 'specialist-message'));
      const outcome = entry.outcome || {};
      conversation.append(node('h4', `${agent.name} · recorded response`));
      const missing = outcome.temporary_context?.content_retained === false ? 'Response content was not retained because temporary upload context was used.' : entry.status === 'active' ? 'No response recorded yet. Refresh to check for an update.' : entry.status === 'failed' ? 'This consultation failed. No successful response is available.' : 'No response content was recorded.';
      conversation.append(node('p', text(outcome.recommendation, missing), 'specialist-message'));
      [['Findings', outcome.findings], ['Assumptions to check', outcome.key_assumptions], ['Open questions', outcome.follow_up_questions]].forEach(([label, values]) => {
        const items = strings(values); if (!items.length) return;
        conversation.append(node('h4', label)); const ul = node('ul', ''); items.forEach(v => ul.append(node('li', v))); conversation.append(ul);
      });
      const aside = node('aside', '', 'specialist-insights');
      aside.append(node('h3', 'Task details'), facts([
        ['Recorded status', text(entry.status)], ['Started', date(entry.started_at)],
        ['Completed', date(entry.completed_at)], ['Last event', date(entry.updated_at)],
        ['Why this specialist', text(entry.route_reason)],
        ['Selection', text(entry.selection_mode)], ['Collaboration', text(entry.group_mode)],
        ['Sources still needed', typeof outcome.sources_needed === 'boolean' ? (outcome.sources_needed ? 'Yes' : 'No') : 'Not recorded'],
        ['Used in Li’s final answer', outcome.validation?.used_in_final === true ? 'Recorded as used' : outcome.validation?.used_in_final === false ? 'Recorded as not used' : 'Not measured'],
      ]));
      const evidence = evidencePanel(entry);
      aside.append(evidence || node('p', 'Evidence and freshness were not recorded for this interaction.', 'truth-note'));
      aside.append(node('p', 'A completed consultation is advice, not proof that an action was executed.', 'muted'));
      if (typeof entry.conversation_id === 'string' && /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(entry.conversation_id)) {
        const button = node('button', 'View original conversation', 'secondary-button'); button.type = 'button';
        button.addEventListener('click', () => onConversation(entry.conversation_id)); aside.append(button);
      }
      target.append(conversation, aside);
    }
    function renderHistory() {
      const list = $('specialist-history-list'); list.replaceChildren();
      const matches = filter(entries, $('specialist-search').value, $('specialist-filter').value);
      $('specialist-results').textContent = `${matches.length} of ${entries.length} loaded interactions`;
      if (!matches.includes(selected)) selected = matches[0] || null;
      matches.forEach(entry => {
        const button = node('button', '', 'specialist-history-choice'); button.type = 'button';
        button.setAttribute('aria-pressed', String(entry === selected));
        button.append(node('small', `${date(entry.started_at)} · ${text(entry.status)}`), node('strong', text(entry.request_text, 'Untitled request')));
        button.addEventListener('click', () => {
          selected = entry; renderHistory();
          list.querySelector?.('[aria-pressed="true"]')?.focus();
        }); list.append(button);
      });
      if (selected) detail(selected, $('specialist-record'));
      else $('specialist-record').replaceChildren(node('p', entries.length ? 'No interactions match your filters.' : 'No recorded interactions yet.', 'truth-note'));
    }
    function tab(name) {
      document.querySelectorAll('.detail-tab').forEach(button => {
        const active = button.dataset.specialistTab === name;
        button.classList.toggle('active', active); button.setAttribute('aria-pressed', String(active));
      });
      $('specialist-live').classList.toggle('hidden', name !== 'live');
      $('specialist-interactions').classList.toggle('hidden', name !== 'history');
    }
    async function refresh(reset = false) {
      const token = ++generation, current = agent;
      entries = []; selected = null;
      $('specialist-refresh').disabled = true;
      $('specialist-load-status').textContent = 'Loading recorded activity…';
      $('specialist-metrics').replaceChildren(); $('specialist-live').replaceChildren();
      $('specialist-history-list').replaceChildren(); $('specialist-record').replaceChildren(); $('specialist-results').textContent = '';
      try {
        const response = await fetch(`/api/specialists/${encodeURIComponent(current.id)}/interactions`, { cache: 'no-store' });
        if (!response.ok) throw new Error('Unavailable');
        const data = await response.json();
        if (!Array.isArray(data.interactions) || data.interactions.some(e => !e || typeof e !== 'object' || Array.isArray(e))) throw new Error('Invalid response');
        if (token !== generation) return;
        entries = data.interactions;
        const stats = summary(entries);
        [['Loaded', stats.total], ['Completed', stats.completed], ['Failed', stats.failed], ['Active', stats.active], ['Avg completed time', stats.average]].forEach(([label, value]) => {
          const card = node('div', '', 'specialist-metric'); card.append(node('strong', String(value)), node('small', label)); $('specialist-metrics').append(card);
        });
        $('specialist-load-status').textContent = `Checked ${new Date().toLocaleTimeString()}. Up to 50 recorded interactions. Refresh for changes.`;
        const active = entries.filter(e => e.status === 'active');
        if (!active.length) $('specialist-live').append(node('p', 'No live specialist interaction in this snapshot.', 'truth-note'));
        active.forEach(entry => { const card = node('div', '', 'specialist-record-layout'); detail(entry, card); $('specialist-live').append(card); });
        renderHistory(); if (reset) tab(active.length ? 'live' : 'history');
      } catch {
        if (token !== generation) return;
        $('specialist-load-status').textContent = 'Activity is unavailable—not evidence of no activity. Try Refresh.';
      } finally { if (token === generation) $('specialist-refresh').disabled = false; }
    }
    $('specialist-search').addEventListener('input', renderHistory);
    $('specialist-filter').addEventListener('change', renderHistory);
    $('specialist-refresh').addEventListener('click', () => refresh());
    document.querySelectorAll('.detail-tab').forEach(button => button.addEventListener('click', () => tab(button.dataset.specialistTab)));
    return { open(item) { agent = item; $('specialist-search').value = ''; $('specialist-filter').value = 'all'; tab('history'); return refresh(true); },
      clear() {
        ++generation; entries = []; selected = null;
        $('specialist-search').value = ''; $('specialist-filter').value = 'all';
        ['specialist-live', 'specialist-record', 'specialist-history-list', 'specialist-metrics', 'specialist-load-status', 'specialist-results'].forEach(id => $(id).replaceChildren());
      } };
  }
  (typeof window === 'undefined' ? globalThis : window).LiSpecialists = { create, summary, filter };
})();
