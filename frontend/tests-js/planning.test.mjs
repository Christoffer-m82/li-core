import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFileSync } from 'node:fs';

function moduleApi(name, file) {
  const context = { console, Intl, URLSearchParams };
  vm.runInNewContext(readFileSync(new URL(file, import.meta.url), 'utf8'), context);
  return context[name];
}

const calendar = moduleApi('LiCalendar', '../static/assets/calendar.js');
const finances = moduleApi('LiFinances', '../static/assets/finances.js');

test('calendar weeks always start Monday and month grid contains 42 days', () => {
  const sunday = new Date(2030, 5, 9, 12);
  assert.equal(calendar.startOfWeek(sunday).getDay(), 1);
  assert.equal(calendar.startOfWeek(sunday).getDate(), 3);
  const monthStart = calendar.monthGridStart(new Date(2030, 5, 15));
  assert.equal(monthStart.getDay(), 1);
  assert.ok(monthStart <= new Date(2030, 5, 1));
});

test('all-day ranges preserve Google exclusive end dates', () => {
  const days = calendar.eventDays({
    all_day: true, start_date: '2030-06-03', end_date: '2030-06-05',
  });
  assert.deepEqual(Array.from(days), ['2030-06-03', '2030-06-04']);
});

test('finance metrics calculate per-position unrealized gain without FX guesses', () => {
  const value = finances.positionMetrics({
    quantity: '10', average_unit_cost: '250', current_unit_price: '275',
    cost_currency: 'SEK', quote_currency: 'SEK',
  });
  assert.deepEqual({ ...value }, { value: 2750, cost: 2500, gain: 250, percent: 10 });
  assert.equal(finances.positionMetrics({
    quantity: '1', average_unit_cost: '10', current_unit_price: '11',
    cost_currency: 'SEK', quote_currency: 'USD',
  }), null);
  assert.equal(finances.positionMetrics({
    quantity: '1', average_unit_cost: '10', current_unit_price: null,
    cost_currency: 'SEK', quote_currency: null,
  }), null);
});
