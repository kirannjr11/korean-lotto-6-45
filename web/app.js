'use strict';

const $ = id => document.getElementById(id);
const state = { analysis: null, page: 0, perPage: 25, request: 0, range: null, view: 'overview' };
const number = value => Number(value).toLocaleString('en-US');
const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const ball = (n, bonus = false) => `<span class="ball b${Math.ceil(n / 10)}${bonus ? ' bonus' : ''}" title="${bonus ? 'Bonus ' : 'Number '}${n}">${n}</span>`;
const balls = (values, bonus) => values.map(n => ball(n)).join('') + (bonus == null ? '' : `<span class="plus" aria-label="Bonus">+</span>${ball(bonus, true)}`);
const prettyDate = date => new Intl.DateTimeFormat('en-US', { month: 'long', day: 'numeric', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${date}T00:00:00Z`));

function status(message, error = false) {
  $('status').textContent = message;
  $('status').classList.toggle('error', error);
}
async function api(path, params = {}) {
  const response = await fetch(`${path}?${new URLSearchParams(params)}`);
  let body;
  try { body = await response.json(); } catch { throw new Error('The local server returned an unreadable response.'); }
  if (!response.ok) throw new Error(body.error || `Request failed (${response.status}).`);
  return body;
}
function setBusy(busy) {
  $('apply').disabled = busy;
  $('generate-button').disabled = busy;
  $('run-backtest').disabled = busy;
}
function activate(view) {
  state.view = view;
  document.querySelectorAll('.view').forEach(panel => { panel.hidden = panel.id !== view; });
  document.querySelectorAll('.tab').forEach(tab => {
    const active = tab.dataset.view === view;
    tab.classList.toggle('active', active);
    if (active) tab.setAttribute('aria-current', 'page'); else tab.removeAttribute('aria-current');
  });
}
document.querySelectorAll('.tab').forEach(tab => tab.addEventListener('click', () => activate(tab.dataset.view)));

function rankings(id, rows, field) {
  const visible = rows.slice(0, 6);
  const max = Math.max(1, ...visible.map(row => row[field]));
  $(id).innerHTML = visible.map((row, index) => `<div class="rank-row"><span class="rank-position">${index + 1}</span>${ball(row.number)}<div class="rank-track"><div class="rank-fill" style="width:${row[field] / max * 100}%"></div></div><span class="rank-count">${row[field]} <small>times</small></span></div>`).join('');
}
function renderFrequency() {
  if (!state.analysis) return;
  const field = $('frequency-mode').value;
  const rows = state.analysis.numbers;
  const max = Math.max(1, ...rows.map(row => row[field]));
  $('frequency-chart').innerHTML = rows.map(row => `<div class="number-cell" title="Number ${row.number}: ${row.count} main appearances; ${row.recent_count} recent; ${row.bonus_count} bonuses; last seen ${row.last_seen ?? 'never in range'}">${ball(row.number)}<div class="mini-track"><div class="mini-fill" style="height:${row[field] / max * 100}%"></div></div><strong>${row[field]}</strong></div>`).join('');
  const notes = {
    count: 'Counts include the six main numbers only. For a fair draw, each number has a 6/45 chance of appearing.',
    recent_count: `Using the most recent ${state.analysis.summary.recent_draw_count} draws within the selected range. Past frequency does not change the next-draw odds.`,
    bonus_count: 'Only bonus appearances are shown here. They are excluded from main-number frequency and combination counts.',
    draws_since: 'Zero means present in the latest selected draw. Numbers never seen in this range show the range length; absence does not make them due.',
  };
  $('frequency-note').textContent = notes[field];
}
$('frequency-mode').addEventListener('change', renderFrequency);
function combinations(id, values) {
  $(id).innerHTML = values.top.slice(0, 8).map(row => `<div class="combination-row"><div class="balls">${balls(row.numbers)}</div><span><strong>${row.count}</strong> draws</span></div>`).join('');
}
function distribution(id, rows, balance = false) {
  const max = Math.max(1, ...rows.map(row => row.count));
  $(id).innerHTML = rows.map(row => `<div class="distribution-row"><span>${balance ? `${row.value} : ${6 - row.value}` : row.value}</span><div class="rank-track"><div class="rank-fill" style="width:${row.count / max * 100}%"></div></div><span title="${row.count} draws">${(row.rate * 100).toFixed(1)}%</span></div>`).join('');
}
function renderOverview() {
  const a = state.analysis, summary = a.summary;
  $('latest-round').textContent = `ROUND ${number(summary.last_round)}`;
  $('latest-balls').innerHTML = balls(summary.last_numbers, summary.last_bonus);
  $('latest-date').textContent = `${prettyDate(summary.last_date)} · Dashed circle: bonus number`;
  $('draw-count').textContent = number(summary.draw_count);
  $('draw-range').textContent = `Rounds ${number(summary.first_round)}–${number(summary.last_round)}`;
  $('average-sum').textContent = summary.average_sum.toFixed(2);
  $('hot-caption').textContent = `Most appearances in the latest ${summary.recent_draw_count} draws`;
  rankings('hot-list', a.top_hot, 'recent_count');
  rankings('frequent-list', a.top_frequent, 'count');
  rankings('cold-list', a.top_cold, 'recent_count');
  renderFrequency();
  combinations('pairs', a.pairs);
  combinations('triples', a.triples);
  $('pair-expectation').textContent = `Fair-draw expectation per fixed pair: ${a.pairs.expected_count.toFixed(2)} appearances.`;
  $('triple-expectation').textContent = `Fair-draw expectation per fixed triple: ${a.triples.expected_count.toFixed(2)} appearances.`;
  distribution('odd-distribution', a.distributions.odd, true);
  distribution('low-distribution', a.distributions.low, true);
  distribution('consecutive-distribution', a.distributions.consecutive_pairs);
}
function renderHistory() {
  if (!state.analysis) return;
  let rows = [...state.analysis.per_draw].reverse();
  const search = $('search').value.trim();
  if (search) {
    const parts = search.split(/[\s,]+/).filter(Boolean);
    if (parts.some(part => !/^\d+$/.test(part))) rows = [];
    else if (parts.length === 1) rows = rows.filter(row => row.round === Number(parts[0]));
    else rows = rows.filter(row => parts.every(part => row.numbers.includes(Number(part))));
  }
  const pages = Math.max(1, Math.ceil(rows.length / state.perPage));
  state.page = Math.max(0, Math.min(state.page, pages - 1));
  const page = rows.slice(state.page * state.perPage, (state.page + 1) * state.perPage);
  $('history-rows').innerHTML = page.length ? page.map(row => `<tr><td><strong>#${number(row.round)}</strong><small>${escape(row.date)}</small></td><td><div class="balls">${balls(row.numbers, row.bonus)}</div></td><td>${row.sum}</td><td>${row.odd} : ${row.even}</td><td>${row.low} : ${row.high}</td><td>${row.consecutive_pairs}</td><td>${row.span}</td><td>${row.repeated_from_previous ?? '—'}</td></tr>`).join('') : '<tr><td colspan="8" class="empty">No draws match this search.</td></tr>';
  $('page-info').textContent = `${number(rows.length)} matching draws · Page ${state.page + 1} of ${pages}`;
  $('previous').disabled = state.page === 0;
  $('next').disabled = state.page >= pages - 1;
}
$('search').addEventListener('input', () => { state.page = 0; renderHistory(); });
$('previous').addEventListener('click', () => { state.page--; renderHistory(); });
$('next').addEventListener('click', () => { state.page++; renderHistory(); });

async function loadAnalysis(range) {
  const request = ++state.request;
  setBusy(true);
  status('Calculating frequencies and combination patterns…');
  try {
    const analysis = await api('/api/analysis', range);
    if (request !== state.request) return;
    state.analysis = analysis;
    state.range = { ...range };
    state.page = 0;
    $('generated-sets').innerHTML = '';
    $('generated-note').textContent = '';
    $('backtest-results').innerHTML = '<p class="empty">Run a walk-forward comparison for your selected range.</p>';
    $('export').href = `/api/export.csv?${new URLSearchParams(range)}`;
    renderOverview();
    renderHistory();
    status(`${number(analysis.summary.draw_count)} draws loaded · Main and bonus numbers are analyzed separately.`);
  } catch (error) { status(error.message, true); }
  finally { if (request === state.request) setBusy(!state.analysis); }
}
$('filters').addEventListener('submit', event => {
  event.preventDefault();
  const start = Number($('start').value), end = Number($('end').value);
  if (start > end) { status('The starting round must be at or before the ending round.', true); return; }
  loadAnalysis({ start, end, window: Number($('window').value) });
});

$('generator').addEventListener('submit', async event => {
  event.preventDefault();
  if (!state.range) return;
  const request = state.request;
  $('generate-button').disabled = true;
  $('generated-note').textContent = 'Sampling sets…';
  try {
    const result = await api('/api/generate', { ...state.range, strategy: $('strategy').value, count: $('set-count').value, seed: $('seed').value });
    if (request !== state.request) return;
    $('generated-sets').innerHTML = result.sets.map((set, index) => `<div class="generated-row"><span>${String(index + 1).padStart(2, '0')}</span><div class="balls">${balls(set)}</div><span>Σ ${set.reduce((a,b) => a+b, 0)}</span></div>`).join('');
    $('generated-note').textContent = `${result.strategy} · Seed ${result.seed} · Through round ${number(result.through_round)}. ${result.note}`;
  } catch (error) { $('generated-note').textContent = error.message; }
  finally { if (request === state.request) $('generate-button').disabled = false; }
});
$('run-backtest').addEventListener('click', async () => {
  if (!state.range) return;
  const request = state.request;
  $('run-backtest').disabled = true;
  $('backtest-results').innerHTML = '<p class="empty">Evaluating predictions using earlier draws only…</p>';
  try {
    const result = await api('/api/backtest', state.range);
    if (request !== state.request) return;
    if (!result.draw_count) {
      $('backtest-results').innerHTML = '<p class="empty">There are not enough prior draws for this window. Choose a later ending round or a shorter recent window.</p>';
      return;
    }
    const names = { uniform: 'Uniform random', hot: 'Recent top six', frequent: 'Lifetime top six' };
    const rows = Object.entries(result.strategies).map(([name, row]) => `<tr><td><strong>${names[name] || escape(name)}</strong></td><td>${row.avg_matches.toFixed(4)}</td><td>${row.hits_at_least_3}</td><td>${(row.hit_rate_at_least_3 * 100).toFixed(2)}%</td><td>${Array.from({length:7}, (_,i) => `${i}: ${row.match_histogram[String(i)]}`).join(' · ')}</td></tr>`).join('');
    $('backtest-results').innerHTML = `<p class="backtest-summary">${number(result.draw_count)} evaluated draws · Rounds ${number(result.start_round)}–${number(result.end_round)} · ${result.window} prior draws required · Expected average matches: ${result.expected_matches}</p><div class="table-scroll"><table><thead><tr><th>Selection rule</th><th>Average matches</th><th>3+ main matches</th><th>3+ match rate</th><th>Match count distribution (matches: tickets)</th></tr></thead><tbody>${rows}</tbody></table></div><p class="small muted">${escape(result.methodology.limitation)} Bonus-dependent prize ranks and payouts are not evaluated.</p>`;
  } catch (error) { $('backtest-results').innerHTML = `<p class="empty">${escape(error.message)}</p>`; }
  finally { if (request === state.request) $('run-backtest').disabled = false; }
});

function safeUrl(value) {
  try { const url = new URL(value); return ['https:', 'http:'].includes(url.protocol) ? url.href : '#'; } catch { return '#'; }
}
async function loadSources() {
  try {
    const manifest = await api('/api/sources');
    $('verification-title').textContent = manifest.all_official_verified ? `All ${number(manifest.draw_count)} draws verified with the official source.` : `${number(manifest.official_verified_count || 0)} draws officially verified.`;
    $('verification-note').textContent = manifest.coverage_note || 'No verification information is available.';
    $('retrieved-at').textContent = manifest.generated_at ? `Snapshot recorded: ${new Date(manifest.generated_at).toLocaleString('en-US', { timeZone: 'Asia/Seoul' })} KST` : '';
    $('source-list').innerHTML = (manifest.sources || []).map(source => `<div class="source-item"><a href="${escape(safeUrl(source.url))}" target="_blank" rel="noopener noreferrer">${escape(source.name)} ↗</a><p>${escape(source.role)}</p><small>${escape(source.reliability)}</small></div>`).join('');
    $('source-warnings').innerHTML = (manifest.warnings || []).map(warning => `<p>${escape(warning)}</p>`).join('');
  } catch (error) {
    $('verification-title').textContent = 'Source information unavailable';
    $('verification-note').textContent = error.message;
  }
}
async function initialize() {
  setBusy(true);
  loadSources();
  try {
    const response = await api('/api/draws');
    const draws = Array.isArray(response) ? response : response.draws;
    if (!draws?.length) throw new Error('No saved draws found. Run python -m lotto sync --end 1244.');
    const first = draws[0], last = draws.at(-1);
    for (const id of ['start', 'end']) { $(id).min = first.round; $(id).max = last.round; }
    $('start').value = first.round;
    $('end').value = last.round;
    $('coverage').textContent = `${number(draws.length)} recorded draws · Through ${prettyDate(last.date)}`;
    await loadAnalysis({ start: first.round, end: last.round, window: Number($('window').value) });
  } catch (error) { status(error.message, true); }
}
initialize();
