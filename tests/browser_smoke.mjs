// Optional browser QA: Node 22+ and an installed Chrome/Edge. No npm packages.
import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const browserPath = process.env.LOTTO_TEST_BROWSER || [
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
].find(existsSync);
if (!browserPath) throw new Error('Set LOTTO_TEST_BROWSER to an installed Chromium browser.');
const work = path.join(root, '.browser-check');
mkdirSync(work, { recursive: true });
const profile = mkdtempSync(path.join(work, 'profile-'));
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
let browser, socket, serverUrl;
const server = spawn('python', ['-m', 'lotto', 'serve', '--port', '0'], { cwd: root, windowsHide: true });
server.stdout.on('data', data => { const match = String(data).match(/http:\/\/127\.0\.0\.1:\d+/); if (match) serverUrl = match[0]; });
let serverErrors = '';
server.stderr.on('data', data => { serverErrors += String(data); });
server.on('error', error => { serverErrors += error.message; });
const errors = [];
const pending = new Map();
let nextId = 0;
function cdp(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++nextId;
    const timeout = setTimeout(() => { pending.delete(id); reject(new Error(`CDP timeout: ${method}`)); }, 15000);
    pending.set(id, { resolve, reject, timeout });
    socket.send(JSON.stringify({ id, method, params }));
  });
}
async function evaluate(expression) {
  const result = await cdp('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result.value;
}
async function until(expression, label) {
  for (let n = 0; n < 100; n++) {
    if (await evaluate(expression)) return;
    await delay(100);
  }
  throw new Error(`Timed out: ${label}`);
}

try {
  for (let n = 0; n < 100 && !serverUrl; n++) await delay(100);
  assert.ok(serverUrl, `Server did not start: ${serverErrors}`);
  const draws = await (await fetch(`${serverUrl}/api/draws`)).json();
  assert.equal(draws.length, 1244);
  assert.deepEqual(draws.at(-1).numbers, [1, 13, 18, 26, 34, 38]);
  assert.equal((await fetch(`${serverUrl}/api/analysis?window=0`)).status, 400);
  assert.equal((await fetch(`${serverUrl}/data/draws.json`)).status, 404);
  assert.equal((await fetch(`${serverUrl}/api/export.csv`)).status, 200);

  browser = spawn(browserPath, ['--headless=new', '--remote-debugging-port=0', `--user-data-dir=${profile}`,
    '--no-first-run', '--no-default-browser-check', '--disable-background-networking', '--disable-extensions',
    '--disable-sync', 'about:blank'], { windowsHide: true, stdio: 'ignore' });
  browser.on('error', error => errors.push(error.message));
  const portFile = path.join(profile, 'DevToolsActivePort');
  for (let n = 0; n < 100 && !existsSync(portFile); n++) await delay(100);
  assert.ok(existsSync(portFile), 'Browser debugging endpoint did not start.');
  const debugPort = readFileSync(portFile, 'utf8').split('\n')[0].trim();
  const targets = await (await fetch(`http://127.0.0.1:${debugPort}/json/list`)).json();
  const target = targets.find(item => item.type === 'page');
  socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
  socket.onmessage = event => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      const request = pending.get(message.id);
      pending.delete(message.id); clearTimeout(request.timeout);
      if (message.error) request.reject(new Error(JSON.stringify(message.error))); else request.resolve(message.result);
    }
    if (message.method === 'Runtime.exceptionThrown') errors.push(JSON.stringify(message.params.exceptionDetails));
    if (message.method === 'Runtime.consoleAPICalled' && message.params.type === 'error') errors.push(JSON.stringify(message.params.args));
  };
  await cdp('Runtime.enable');
  await cdp('Page.enable');
  await cdp('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1100, deviceScaleFactor: 1, mobile: false });
  await cdp('Page.navigate', { url: serverUrl });
  await until("document.body && /1[,.]?244/.test(document.body.innerText)", 'draw data on dashboard');
  await until("document.querySelectorAll('.number-cell').length === 45", '45 frequency cells');
  assert.equal(await evaluate("document.querySelector('#hot-list .ball').textContent"), '31');
  assert.equal(await evaluate("document.querySelector('#frequent-list .ball').textContent"), '34');

  await evaluate("document.querySelector('[data-view=history]').click(); document.getElementById('search').value='1244'; document.getElementById('search').dispatchEvent(new Event('input'))");
  assert.equal(await evaluate("document.querySelectorAll('#history-rows tr').length"), 1);
  assert.equal(await evaluate("document.querySelector('#history-rows strong').textContent"), '#1,244');
  await evaluate("document.getElementById('search').value='1,13,18'; document.getElementById('search').dispatchEvent(new Event('input'))");
  assert.ok(await evaluate("[...document.querySelectorAll('#history-rows tr')].every(row=>[1,13,18].every(n=>[...row.querySelectorAll('.ball:not(.bonus)')].some(b=>Number(b.textContent)===n)))"));
  await evaluate("document.getElementById('search').value=''; document.getElementById('search').dispatchEvent(new Event('input')); document.getElementById('next').click()");
  assert.equal(await evaluate("document.querySelector('#history-rows strong').textContent"), '#1,219');

  await evaluate("document.querySelector('[data-view=experiments]').click(); document.getElementById('generator').requestSubmit()");
  await until("document.querySelectorAll('.generated-row').length === 5", 'example tickets');
  assert.deepEqual(await evaluate("[...document.querySelector('.generated-row').querySelectorAll('.ball')].map(b=>Number(b.textContent))"), [7,10,13,19,27,40]);
  await evaluate("document.getElementById('run-backtest').click()");
  await until("document.querySelector('#backtest-results table') !== null", 'backtest scores');
  assert.ok(await evaluate("document.getElementById('backtest-results').textContent.includes('1,194 evaluated draws')"));
  assert.ok(await evaluate("document.getElementById('backtest-results').textContent.includes('0.7956')"));

  await evaluate("document.getElementById('end').value='50'; document.getElementById('filters').requestSubmit()");
  await until("document.getElementById('draw-count').textContent === '50'", 'historical cutoff');
  assert.equal(await evaluate("document.querySelectorAll('.generated-row').length"), 0);
  await evaluate("document.getElementById('run-backtest').click()");
  await until("document.getElementById('backtest-results').textContent.includes('not enough prior draws')", 'insufficient history');
  await evaluate("document.getElementById('start').value='1000'; document.getElementById('end').value='1244'; document.getElementById('filters').requestSubmit()");
  await until("document.getElementById('draw-count').textContent === '245'", 'selected range');
  await evaluate("document.getElementById('run-backtest').click()");
  await until("document.getElementById('backtest-results').textContent.includes('245 evaluated draws')", 'backtest retains earlier training');
  await evaluate("document.querySelector('[data-view=sources]').click()");
  await until("document.getElementById('verification-title').textContent.includes('All 1,244 draws verified')", 'source verification');
  await evaluate("document.getElementById('start').value='1'; document.getElementById('filters').requestSubmit(); document.querySelector('[data-view=overview]').click()");
  await until("document.getElementById('draw-count').textContent === '1,244'", 'reset overview');
  const state = await evaluate("({title:document.title,headings:[...document.querySelectorAll('h1,h2')].map(e=>e.innerText),buttons:[...document.querySelectorAll('button')].map(e=>({id:e.id,text:e.innerText})),inputs:[...document.querySelectorAll('input,select')].map(e=>({id:e.id,value:e.value})),overflow:document.documentElement.scrollWidth>innerWidth})");
  assert.equal(state.overflow, false, 'Desktop page overflows horizontally.');
  mkdirSync(path.join(root, 'reports'), { recursive: true });
  const screenshot = await cdp('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  writeFileSync(path.join(root, 'reports', 'dashboard.png'), Buffer.from(screenshot.data, 'base64'));
  await cdp('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  await delay(150);
  for (const view of ['overview', 'history', 'experiments', 'sources']) {
    await evaluate(`document.querySelector('[data-view=${view}]').click()`);
    assert.equal(await evaluate('document.documentElement.scrollWidth > innerWidth'), false, `Mobile ${view} overflows horizontally.`);
  }
  assert.deepEqual(errors, [], 'Browser runtime errors');
  console.log(JSON.stringify({ result: 'PASS', checks: ['HTTP APIs', 'invalid input', 'file isolation', 'CSV', '45-number chart', 'draw search', 'combination search', 'pagination', 'seeded generation', 'backtest scores', 'historical cutoff', 'insufficient history', 'range retains prior training', 'source verification', 'desktop layout', 'all four mobile views', 'no runtime errors'], state }, null, 2));
} finally {
  if (socket?.readyState === WebSocket.OPEN) {
    try { await cdp('Browser.close'); } catch { /* browser may close before replying */ }
    socket.close();
  }
  browser?.kill();
  server.kill();
  await delay(500);
  // Delete only this run's generated profile after checking the absolute path.
  const resolved = path.resolve(profile);
  if (path.dirname(resolved) === path.resolve(work) && path.basename(resolved).startsWith('profile-')) {
    try { rmSync(resolved, { recursive: true, force: true }); } catch { /* locked browser files can be cleaned later */ }
  }
}
