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
  function statistics(entries, days = 0, now = new Date()) {
    const end = now.getTime(), start = days ? Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() - days + 1) : -Infinity;
    const dated = e => Number.isFinite(Date.parse(e.started_at)) && Date.parse(e.started_at) <= end;
    const records = days ? entries.filter(e => dated(e) && Date.parse(e.started_at) >= start) : entries;
    const count = fn => records.filter(fn).length;
    const durations = records.filter(e => e.status === 'completed').map(e => e.elapsed_ms).filter(v => Number.isFinite(v) && v >= 0).sort((a,b) => a-b);
    const median = durations.length ? (durations[Math.floor((durations.length - 1)/2)] + durations[Math.floor(durations.length/2)])/2000 : null;
    const completed = count(e => e.status === 'completed'), failed = count(e => e.status === 'failed');
    const groups = (labels, key) => labels.map(([title, value]) => [title, count(e => key(e) === value)]);
    const activity = Array.from({length:14}, (_, i) => {
      const day = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() - 13 + i)).toISOString().slice(0,10);
      return [day, count(e => dated(e) && new Date(e.started_at).toISOString().slice(0,10) === day)];
    });
    return { total: records.length, completed, failed,
      activeDays: new Set(records.filter(dated).map(e => new Date(e.started_at).toISOString().slice(0,10))).size,
      undated: entries.filter(e => !dated(e)).length,
      average: durations.length ? durations.reduce((a,b) => a+b,0)/durations.length/1000 : null,
      median, timed: durations.length, completion: completed + failed ? completed/(completed+failed)*100 : null,
      statuses: groups([['Completed','completed'],['Failed','failed'],['In progress','active']], e => e.status)
        .concat([['Other / unknown', count(e => !['completed','failed','active'].includes(e.status))]]),
      collaboration: groups([['Solo','solo'],['With other specialists','multi']], e => e.group_mode)
        .concat([['Not recorded',count(e => !['solo','multi'].includes(e.group_mode))]]),
      attribution: groups([['Used by Li',true],['Not used by Li',false]], e => e.outcome?.validation?.used_in_final)
        .concat([['Not measured',count(e => typeof e.outcome?.validation?.used_in_final !== 'boolean')]]),
      speed: [['Under 5 seconds',durations.filter(v => v < 5000).length],['5–15 seconds',durations.filter(v => v >= 5000 && v < 15000).length],['15–30 seconds',durations.filter(v => v >= 15000 && v < 30000).length],['30 seconds or longer',durations.filter(v => v >= 30000).length]],
      activity,
    };
  }
  function create({ document, fetch, evidencePanel, onConversation, workspace }) {
    const $ = id => document.querySelector(`#${id}`);
    let entries = [], selected = null, agent = null, generation = 0, statsDays = 0;
    const node = (tag, content, className = '') => {
      const el = document.createElement(tag); el.textContent = content; el.className = className; return el;
    };
    function facts(rows) {
      const dl = node('dl', '', 'evidence-facts');
      rows.forEach(([label, value]) => { const pair = node('div', ''); pair.append(node('dt', label), node('dd', value)); dl.append(pair); });
      return dl;
    }
    function renderStatistics() {
      const target = $('specialist-statistics'); target.replaceChildren();
      const stats = statistics(entries, statsDays);
      target.append(node('h3', `${agent.name} · Statistics`));
      const label = node('label', 'Activity period'); label.htmlFor = 'statistics-period';
      const period = node('select'); period.id = 'statistics-period';
      [['0','All loaded records'],['7','Last 7 days'],['30','Last 30 days']].forEach(([value,title]) => {const option=node('option',title); option.value=value; period.append(option);});
      period.value = String(statsDays); period.addEventListener('change', () => {statsDays = Number(period.value); renderStatistics(); $('statistics-period')?.focus?.();});
      target.append(label, period, node('p', `${stats.total} of ${entries.length} loaded consultations. Maximum 50 records, not all-time totals. Periods use consultation start dates in UTC. ${stats.undated} records have missing or future dates and are excluded from dated charts and period filters.`, 'truth-note'));
      if (!stats.total) { target.append(node('p', 'No recorded consultations in this selection. This is not a measure of the specialist’s quality.', 'truth-note')); return; }
      const metrics = node('div', '', 'specialist-metrics');
      [['Consultations',stats.total],['Active days',stats.activeDays],['Avg response',stats.average === null ? 'Not measured' : `${stats.average.toFixed(1)}s`],['Median response',stats.median === null ? 'Not measured' : `${stats.median.toFixed(1)}s`],['Completion rate',stats.completion === null ? 'Not measured' : `${stats.completion.toFixed(0)}%`]].forEach(([label,value]) => {const card=node('div','','specialist-metric'); card.append(node('strong',String(value)),node('small',label)); metrics.append(card);});
      target.append(metrics, node('p', `Response times use ${stats.timed} completed consultations with valid timings. Completion rate uses only completed + failed records; it does not measure accuracy, usefulness or successful real-world actions.`, 'muted'));
      const grid = node('div', '', 'specialist-charts');
      function chart(title, rows, explanation) {
        const section = node('section', '', 'specialist-chart'); section.append(node('h4', title),node('p',explanation,'muted'));
        const table = node('table'); const caption=node('caption','Consultation counts · bars start at zero'); table.append(caption);
        const max = Math.max(1, ...rows.map(r => r[1]));
        rows.forEach(([title,value]) => {
          const tr=node('tr'), th=node('th',title), td=node('td'), amount=node('td',String(value)); th.scope='row';
          const bar=node('meter'); bar.min=0; bar.max=max; bar.value=value; bar.setAttribute('aria-hidden','true');
          td.append(bar); tr.append(th,td,amount); table.append(tr);
        }); section.append(table); grid.append(section);
      }
      chart('Consultation outcomes',stats.statuses,'Recorded state, including unfinished or unclassified work.');
      chart('Working alone or together',stats.collaboration,'How Li organised the consultation—not a measure of independence.');
      chart('Use in Li’s final answer',stats.attribution,'Only explicit recorded attribution is counted. Missing tracking stays “not measured”.');
      chart('Response-time distribution',stats.speed,'Completed consultations with valid timings; seconds per consultation.');
      chart('Daily activity · last 14 calendar days',stats.activity,'UTC start dates within the selected period. Zero means no matching loaded records, not proof of no activity.');
      target.append(grid,node('p','Not measured yet: answer accuracy, owner satisfaction, money or time saved, token cost, and real-world impact. These need reliable tracking and your feedback—not invented scores. Evidence details remain available in History.','truth-note'));
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
        if (workspace) {
          const chat = node('button', 'Open in Workspace', 'secondary-button'); chat.type = 'button';
          chat.addEventListener('click', () => { tab('live'); workspace.select(entry.conversation_id); }); aside.append(chat);
        }
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
      $('specialist-statistics').classList.toggle('hidden', name !== 'statistics');
      if (name === 'live') workspace?.show?.();
    }
    function renderSnapshot() {
      $('specialist-metrics').replaceChildren();
      const stats = summary(entries);
      [['Loaded', stats.total], ['Completed', stats.completed], ['Failed', stats.failed], ['Active', stats.active], ['Avg completed time', stats.average]].forEach(([label, value]) => {
        const card = node('div', '', 'specialist-metric'); card.append(node('strong', String(value)), node('small', label)); $('specialist-metrics').append(card);
      });
      $('specialist-load-status').textContent = `Checked ${new Date().toLocaleTimeString()}. Up to 50 recorded interactions. Refresh for changes.`;
      renderHistory(); renderStatistics();
    }
    async function refresh(reset = false) {
      const token = ++generation, current = agent;
      entries = []; selected = null;
      $('specialist-refresh').disabled = true;
      $('specialist-load-status').textContent = 'Loading recorded activity…';
      $('specialist-metrics').replaceChildren(); $('specialist-statistics').replaceChildren(node('p','Loading statistics…','muted')); if (!workspace) $('specialist-live').replaceChildren();
      $('specialist-history-list').replaceChildren(); $('specialist-record').replaceChildren(); $('specialist-results').textContent = '';
      try {
        const response = await fetch(`/api/specialists/${encodeURIComponent(current.id)}/interactions`, { cache: 'no-store' });
        if (!response.ok) throw new Error('Unavailable');
        const data = await response.json();
        if (!Array.isArray(data.interactions) || data.interactions.some(e => !e || typeof e !== 'object' || Array.isArray(e))) throw new Error('Invalid response');
        if (token !== generation) return;
        entries = data.interactions;
        renderSnapshot();
        const active = workspace ? [] : entries.filter(e => e.status === 'active');
        if (!workspace && !active.length) $('specialist-live').append(node('p', 'No live specialist interaction in this snapshot.', 'truth-note'));
        active.forEach(entry => { const card = node('div', '', 'specialist-record-layout'); detail(entry, card); $('specialist-live').append(card); });
        if (workspace) { if (reset) await workspace.open(current, entries); else await workspace.refresh(entries); }
      } catch {
        if (token !== generation) return;
        $('specialist-load-status').textContent = 'Activity is unavailable—not evidence of no activity. Try Refresh.';
        $('specialist-statistics').replaceChildren(node('p','Statistics unavailable. Refresh to retry; missing data is not zero activity.','truth-note'));
        if (reset && workspace) await workspace.open(current, []);
      } finally { if (token === generation) $('specialist-refresh').disabled = false; }
    }
    $('specialist-search').addEventListener('input', renderHistory);
    $('specialist-filter').addEventListener('change', renderHistory);
    $('specialist-refresh').addEventListener('click', () => refresh());
    document.querySelectorAll('.detail-tab').forEach(button => button.addEventListener('click', () => tab(button.dataset.specialistTab)));
    return { open(item, initialTab = 'live') { workspace?.clear(); agent = item; statsDays = 0; $('specialist-search').value = ''; $('specialist-filter').value = 'all'; tab(['live','history','statistics'].includes(initialTab) ? initialTab : 'live'); return refresh(true); },
      updateRecords(id, records) {
        if (!agent || agent.id !== id || !Array.isArray(records) || records.some(e => !e || typeof e !== 'object' || Array.isArray(e))) return;
        ++generation; entries = records; $('specialist-refresh').disabled = false; renderSnapshot();
      },
      clear() {
        ++generation; agent = null; entries = []; selected = null; workspace?.clear();
        $('specialist-search').value = ''; $('specialist-filter').value = 'all';
        ['specialist-record', 'specialist-history-list', 'specialist-metrics', 'specialist-load-status', 'specialist-results', 'specialist-statistics', ...(!workspace ? ['specialist-live'] : [])].forEach(id => $(id).replaceChildren());
      } };
  }
  (typeof window === 'undefined' ? globalThis : window).LiSpecialists = { create, summary, filter, statistics };
})();
