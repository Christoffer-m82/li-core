(function (global) {
  'use strict';

  const DAY = 86400000;
  const cloneDay = value => new Date(value.getFullYear(), value.getMonth(), value.getDate());
  const addDays = (value, days) => new Date(value.getFullYear(), value.getMonth(), value.getDate() + days);
  const dayKey = value => `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`;
  function startOfWeek(value) {
    const date = cloneDay(value); const weekday = date.getDay() || 7;
    return addDays(date, 1 - weekday);
  }
  function monthGridStart(value) { return startOfWeek(new Date(value.getFullYear(), value.getMonth(), 1)); }
  function eventDays(event) {
    if (event.all_day) {
      const start = new Date(`${event.start_date}T00:00:00`);
      const end = new Date(`${event.end_date}T00:00:00`);
      const values = [];
      for (let cursor = start; cursor < end; cursor = addDays(cursor, 1)) values.push(dayKey(cursor));
      return values;
    }
    if (!event.start || !event.end) return [];
    const start = new Date(event.start); const end = new Date(event.end);
    if (Number.isNaN(start.valueOf()) || Number.isNaN(end.valueOf())) return [];
    const values = [];
    for (let cursor = cloneDay(start); cursor < end; cursor = addDays(cursor, 1)) values.push(dayKey(cursor));
    return values;
  }
  function eventsForDay(events, date) {
    const key = dayKey(date);
    return events.filter(event => eventDays(event).includes(key));
  }

  function create({ document, fetch, onAskLi = () => {} }) {
    const get = id => document.querySelector(`#${id}`);
    const state = { anchor: cloneDay(new Date()), events: [], loaded: false, selectedEvent: null };
    let requestId = 0;
    const dateFormat = options => new Intl.DateTimeFormat(undefined, options);

    function eventTime(event) {
      if (event.all_day) return 'All day';
      const start = new Date(event.start); const end = new Date(event.end);
      return `${dateFormat({ hour: '2-digit', minute: '2-digit' }).format(start)}–${dateFormat({ hour: '2-digit', minute: '2-digit' }).format(end)}`;
    }
    function showDetail(event) {
      state.selectedEvent = event; const host = get('calendar-detail'); host.replaceChildren();
      const title = document.createElement('h3'); title.textContent = event.title;
      const facts = document.createElement('dl');
      const values = [
        ['When', event.all_day ? `${event.start_date} · all day` : `${dateFormat({ dateStyle: 'medium' }).format(new Date(event.start))}, ${eventTime(event)}`],
        ['Location', event.location || 'No location recorded'],
        ['Status', event.status || 'Not provided'],
      ];
      values.forEach(([label, value]) => { const dt = document.createElement('dt'); dt.textContent = label; const dd = document.createElement('dd'); dd.textContent = value; facts.append(dt, dd); });
      host.append(title, facts);
    }
    function eventButton(event) {
      const button = document.createElement('button'); button.type = 'button';
      button.className = `calendar-event${event.all_day ? ' all-day' : ''}`;
      const time = document.createElement('small'); time.textContent = eventTime(event);
      const title = document.createElement('strong'); title.textContent = event.title;
      button.append(time, title); button.addEventListener('click', () => showDetail(event));
      return button;
    }
    function renderWeek() {
      const host = get('calendar-week'); host.replaceChildren(); const start = startOfWeek(state.anchor);
      const end = addDays(start, 6);
      get('calendar-range-title').textContent = `${dateFormat({ month: 'short', day: 'numeric' }).format(start)} – ${dateFormat({ month: 'short', day: 'numeric', year: 'numeric' }).format(end)}`;
      const today = dayKey(new Date());
      for (let offset = 0; offset < 7; offset += 1) {
        const date = addDays(start, offset); const day = document.createElement('section');
        day.className = `calendar-day${offset >= 5 ? ' weekend' : ''}${dayKey(date) === today ? ' today' : ''}`;
        const head = document.createElement('header'); head.className = 'calendar-day-head';
        const name = document.createElement('small'); name.textContent = dateFormat({ weekday: 'short' }).format(date);
        const number = document.createElement('strong'); number.textContent = dateFormat({ month: 'short', day: 'numeric' }).format(date);
        head.append(name, number); const list = document.createElement('div'); list.className = 'calendar-day-events';
        const events = eventsForDay(state.events, date);
        if (events.length) events.forEach(event => list.append(eventButton(event)));
        else { const empty = document.createElement('span'); empty.className = 'calendar-empty-day'; empty.textContent = 'No events'; list.append(empty); }
        day.append(head, list); host.append(day);
      }
    }
    function renderMonth() {
      const host = get('calendar-month'); host.replaceChildren();
      ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].forEach(label => { const cell = document.createElement('span'); cell.className = 'calendar-month-label'; cell.textContent = label; host.append(cell); });
      get('calendar-month-title').textContent = dateFormat({ month: 'long', year: 'numeric' }).format(state.anchor);
      const start = monthGridStart(state.anchor); const today = dayKey(new Date());
      for (let offset = 0; offset < 42; offset += 1) {
        const date = addDays(start, offset); const events = eventsForDay(state.events, date);
        const button = document.createElement('button'); button.type = 'button';
        const weekday = date.getDay();
        button.className = `calendar-month-day${weekday === 0 || weekday === 6 ? ' weekend' : ''}${date.getMonth() !== state.anchor.getMonth() ? ' outside' : ''}${dayKey(date) === dayKey(state.anchor) ? ' selected' : ''}${dayKey(date) === today ? ' today' : ''}`;
        const number = document.createElement('span'); number.textContent = String(date.getDate());
        const count = document.createElement('small'); count.textContent = events.length ? `${events.length} event${events.length === 1 ? '' : 's'}` : '';
        button.setAttribute('aria-label', `${dateFormat({ dateStyle: 'full' }).format(date)}, ${events.length} events`);
        button.append(number, count); button.addEventListener('click', () => {
          const monthChanged = date.getMonth() !== state.anchor.getMonth() || date.getFullYear() !== state.anchor.getFullYear();
          state.anchor = date;
          if (monthChanged) { state.loaded = false; load({ force: true }); } else render();
        }); host.append(button);
      }
    }
    function render() { renderWeek(); renderMonth(); }
    async function load({ force = false } = {}) {
      if (state.loaded && !force) { render(); return; }
      const currentRequest = ++requestId;
      const status = get('calendar-status'); status.textContent = 'Loading your calendar…';
      const start = monthGridStart(state.anchor); const end = addDays(start, 42);
      try {
        const query = new URLSearchParams({ time_min: start.toISOString(), time_max: end.toISOString() });
        const response = await fetch(`/api/calendar/events?${query}`);
        const payload = await response.json();
        if (currentRequest !== requestId) return;
        if (!response.ok || payload.status !== 'completed' || !Array.isArray(payload.events)) throw new Error(payload.detail || payload.message || 'Calendar is unavailable.');
        state.events = payload.events; state.loaded = true; render();
        status.textContent = `${payload.events.length} event${payload.events.length === 1 ? '' : 's'} loaded · refreshed ${dateFormat({ hour: '2-digit', minute: '2-digit' }).format(new Date())}.`;
      } catch (error) {
        if (currentRequest !== requestId) return;
        state.events = []; state.loaded = false; render();
        status.textContent = error.message === 'Calendar is unavailable.' ? error.message : `Calendar unavailable: ${error.message}`;
      }
    }
    function navigate(days) { state.anchor = addDays(state.anchor, days); state.loaded = false; load({ force: true }); }
    function initialize() {
      get('calendar-timezone').textContent = `Times shown in ${Intl.DateTimeFormat().resolvedOptions().timeZone || 'your device timezone'}.`;
      get('calendar-previous').addEventListener('click', () => navigate(-7));
      get('calendar-next').addEventListener('click', () => navigate(7));
      get('calendar-today').addEventListener('click', () => { state.anchor = cloneDay(new Date()); state.loaded = false; load({ force: true }); });
      get('calendar-refresh').addEventListener('click', () => load({ force: true }));
      get('calendar-ask-li').addEventListener('click', onAskLi);
      render();
    }
    function clear() { requestId += 1; state.events = []; state.loaded = false; state.selectedEvent = null; render(); }
    initialize();
    return { load, clear, state };
  }

  global.LiCalendar = { create, startOfWeek, monthGridStart, eventDays, eventsForDay };
})(typeof window === 'undefined' ? globalThis : window);
