(function (global) {
  'use strict';

  function positionMetrics(holding) {
    if (holding.current_unit_price == null || holding.quote_currency !== holding.cost_currency) return null;
    const quantity = Number(holding.quantity); const cost = quantity * Number(holding.average_unit_cost);
    const value = quantity * Number(holding.current_unit_price); const gain = value - cost;
    return { value, cost, gain, percent: cost === 0 ? null : gain / cost * 100 };
  }

  function create({ document, fetch, confirm = global.confirm, onAskJames = () => {} }) {
    const get = id => document.querySelector(`#${id}`);
    const state = { account: 'avanza', holdings: [], totals: [], loaded: false };
    let requestId = 0;
    const formatter = (currency, value) => {
      try { return new Intl.NumberFormat(undefined, { style: 'currency', currency, maximumFractionDigits: 2 }).format(Number(value)); }
      catch { return `${Number(value).toLocaleString()} ${currency}`; }
    };
    const signed = (currency, value) => `${Number(value) >= 0 ? '+' : '−'}${formatter(currency, Math.abs(Number(value)))}`;

    function hideForm() { get('finance-form-panel').classList.add('hidden'); get('finance-form-status').textContent = ''; }
    function openForm(holding = null) {
      const form = get('finance-form'); form.reset();
      get('finance-holding-id').value = holding?.holding_id || '';
      get('finance-symbol').value = holding?.symbol || '';
      get('finance-name').value = holding?.asset_name || '';
      get('finance-quantity').value = holding?.quantity || '';
      get('finance-average-cost').value = holding?.average_unit_cost || '';
      get('finance-cost-currency').value = holding?.cost_currency || (state.account === 'avanza' ? 'SEK' : 'USD');
      get('finance-current-price').value = holding?.current_unit_price ?? '';
      get('finance-quote-currency').value = holding?.quote_currency || '';
      get('finance-form-title').textContent = holding ? `Update ${holding.asset_name}` : `Add ${state.account === 'avanza' ? 'Avanza' : 'crypto'} holding`;
      get('finance-form-panel').classList.remove('hidden'); get('finance-symbol').focus();
    }
    function totalCard(label, total, kind = '') {
      const card = document.createElement('article'); card.className = 'finance-total';
      const heading = document.createElement('span'); heading.textContent = label;
      const value = document.createElement('strong'); value.className = kind;
      value.textContent = label === 'Gain / loss' ? signed(total.currency, total.unrealized_gain) : formatter(total.currency, total[label === 'Current value' ? 'market_value' : 'cost_basis']);
      const note = document.createElement('small');
      note.textContent = label === 'Gain / loss' && total.unrealized_gain_percent != null ? `${Number(total.unrealized_gain_percent).toFixed(2)}% · unrealized` : `${total.priced_holdings} priced holding${total.priced_holdings === 1 ? '' : 's'}`;
      card.append(heading, value, note); return card;
    }
    function renderTotals() {
      const host = get('finance-totals'); host.replaceChildren();
      if (!state.totals.length) {
        const card = document.createElement('article'); card.className = 'finance-total';
        const title = document.createElement('strong'); title.textContent = 'No comparable total yet';
        const note = document.createElement('small'); note.textContent = 'Add a current price in the same currency as the average buy price.';
        card.append(title, note); host.append(card); return;
      }
      state.totals.forEach(total => {
        const kind = Number(total.unrealized_gain) >= 0 ? 'gain' : 'loss';
        host.append(totalCard('Current value', total), totalCard('Cost basis', total), totalCard('Gain / loss', total, kind));
      });
    }
    function valueBlock(label, primary, secondary, kind = '') {
      const div = document.createElement('div'); div.className = `holding-value ${kind}`;
      const strong = document.createElement('strong'); strong.textContent = primary;
      const small = document.createElement('small'); small.textContent = `${label} · ${secondary}`;
      div.append(strong, small); return div;
    }
    function holdingRow(holding) {
      const row = document.createElement('article'); row.className = 'holding-row';
      const identity = document.createElement('div'); identity.className = 'holding-identity';
      const title = document.createElement('strong'); title.textContent = holding.asset_name;
      const symbol = document.createElement('small'); symbol.textContent = `${holding.symbol} · ${Number(holding.quantity).toLocaleString()} units`;
      identity.append(title, symbol);
      const metrics = positionMetrics(holding);
      const price = holding.current_unit_price == null ? valueBlock('Current price', 'Not entered', 'No valuation') : valueBlock('Current price', formatter(holding.quote_currency, holding.current_unit_price), holding.price_as_of ? `as of ${new Date(holding.price_as_of).toLocaleString()}` : 'timestamp unavailable');
      price.classList.add('holding-price');
      const cost = valueBlock('Average buy price', formatter(holding.cost_currency, holding.average_unit_cost), holding.cost_currency); cost.classList.add('holding-cost');
      const gain = metrics ? valueBlock('Unrealized', signed(holding.cost_currency, metrics.gain), metrics.percent == null ? 'percentage unavailable' : `${metrics.percent.toFixed(2)}%`, metrics.gain >= 0 ? 'gain' : 'loss') : valueBlock('Unrealized', 'Not comparable', 'Price missing or different currency');
      const actions = document.createElement('div'); actions.className = 'holding-actions';
      const edit = document.createElement('button'); edit.type = 'button'; edit.textContent = 'Edit'; edit.setAttribute('aria-label', `Edit ${holding.asset_name}`); edit.addEventListener('click', () => openForm(holding));
      const archive = document.createElement('button'); archive.type = 'button'; archive.textContent = 'Hide'; archive.setAttribute('aria-label', `Hide ${holding.asset_name}`); archive.addEventListener('click', () => archiveHolding(holding));
      actions.append(edit, archive); row.append(identity, price, cost, gain, actions); return row;
    }
    function render() {
      get('finance-account-title').textContent = `${state.account === 'avanza' ? 'Avanza' : 'Crypto'} holdings`;
      document.querySelectorAll('[data-finance-account]').forEach(button => { const active = button.dataset.financeAccount === state.account; button.classList.toggle('active', active); button.setAttribute('aria-pressed', active ? 'true' : 'false'); });
      renderTotals(); const host = get('finance-holdings'); host.replaceChildren();
      if (!state.holdings.length) { const empty = document.createElement('div'); empty.className = 'finance-empty'; empty.textContent = `No ${state.account === 'avanza' ? 'Avanza' : 'crypto'} holdings recorded yet.`; host.append(empty); return; }
      state.holdings.forEach(holding => host.append(holdingRow(holding)));
    }
    async function load() {
      const currentRequest = ++requestId; const account = state.account;
      const status = get('finance-status'); status.textContent = 'Loading private holdings…';
      try {
        const response = await fetch(`/api/finances/portfolio?account=${account}`); const payload = await response.json();
        if (currentRequest !== requestId || account !== state.account) return;
        if (!response.ok || !Array.isArray(payload.holdings)) throw new Error(payload.detail || 'Portfolio is unavailable.');
        state.holdings = payload.holdings; state.totals = payload.totals || []; state.loaded = true; render();
        status.textContent = `${state.holdings.length} holding${state.holdings.length === 1 ? '' : 's'} · owner-entered prices, no live market feed.`;
      } catch (error) { if (currentRequest !== requestId) return; state.holdings = []; state.totals = []; state.loaded = false; render(); status.textContent = `Portfolio unavailable: ${error.message}`; }
    }
    async function save(event) {
      event.preventDefault(); const current = get('finance-current-price').value.trim(); let quote = get('finance-quote-currency').value.trim();
      if (current && !quote) quote = get('finance-cost-currency').value.trim();
      if (!current && quote) { get('finance-form-status').textContent = 'Enter a current price or clear its currency.'; return; }
      const payload = {
        holding_id: get('finance-holding-id').value || null, account: state.account,
        symbol: get('finance-symbol').value.trim(), asset_name: get('finance-name').value.trim(),
        quantity: get('finance-quantity').value, average_unit_cost: get('finance-average-cost').value,
        cost_currency: get('finance-cost-currency').value.trim(), current_unit_price: current || null,
        quote_currency: current ? quote : null,
      };
      get('finance-form-status').textContent = 'Saving…';
      const response = await fetch('/api/finances/holdings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      if (!response.ok) { const value = await response.json().catch(() => ({})); get('finance-form-status').textContent = value.detail || 'Holding could not be saved.'; return; }
      hideForm(); await load();
    }
    async function archiveHolding(holding) {
      if (!confirm(`Hide ${holding.asset_name} from this portfolio? Its audit record will be retained.`)) return;
      const response = await fetch(`/api/finances/holdings/${holding.holding_id}/archive`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ confirmation: 'archive_portfolio_holding' }) });
      if (response.ok) await load(); else get('finance-status').textContent = 'The holding could not be hidden.';
    }
    function initialize() {
      document.querySelectorAll('[data-finance-account]').forEach(button => button.addEventListener('click', () => { state.account = button.dataset.financeAccount; hideForm(); load(); }));
      get('finance-add').addEventListener('click', () => openForm()); get('finance-form-close').addEventListener('click', hideForm); get('finance-form-cancel').addEventListener('click', hideForm);
      get('finance-form').addEventListener('submit', save); get('finance-ask-james').addEventListener('click', onAskJames);
      render();
    }
    function clear() { requestId += 1; state.holdings = []; state.totals = []; state.loaded = false; hideForm(); render(); }
    initialize(); return { load, clear, state, openForm };
  }

  global.LiFinances = { create, positionMetrics };
})(typeof window === 'undefined' ? globalThis : window);
