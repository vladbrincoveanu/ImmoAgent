// Ad-hoc API probe: hits every dashboard route + API endpoint and reports
// status, content-type and the first slice of any error body. Not part of the
// test suite — a triage tool for "which endpoints are actually broken".
const BASE = process.env.PROBE_BASE || 'http://localhost:3010';

const TARGETS = [
  '/',
  '/dashboard',
  '/dashboard/map',
  '/coop',
  '/api/listings/top?limit=5',
  '/api/listings/top?limit=5&genossenschaft=true',
  '/api/listings/map?limit=5',
  '/api/listings/map?limit=5&genossenschaft=true',
  '/api/listings/stream?limit=5',
  '/api/stats/taken',
  '/api/stats/taken-listings',
  '/api/stats/timeline',
  '/api/district-heatmap',
  '/api/insights',
  '/api/destinations',
  '/api/me',
  '/api/saved-searches',
  '/api/geo/infrastructure?bbox=16.2,48.1,16.5,48.3',
  '/api/rent-estimate?bezirk=1010&area=60&rooms=2',
];

// Per-request ceiling. A dev-server route that never answers must show up as a
// timed-out row, not as a probe that hangs forever with no output.
const TIMEOUT_MS = Number(process.env.PROBE_TIMEOUT_MS || 45000);

const results = [];
for (const path of TARGETS) {
  const url = BASE + path;
  const started = Date.now();
  let r;
  try {
    const res = await fetch(url, {
      headers: { accept: 'application/json,text/html' },
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    const body = await res.text();
    r = {
      path,
      status: res.status,
      ms: Date.now() - started,
      type: (res.headers.get('content-type') || '').split(';')[0],
      bytes: body.length,
      snippet: res.ok ? '' : body.slice(0, 300).replace(/\s+/g, ' '),
    };
  } catch (err) {
    r = { path, status: 'THREW', ms: Date.now() - started, snippet: String(err) };
  }
  results.push(r);
  const flag = r.status === 200 ? 'ok  ' : 'FAIL';
  console.log(`${flag} ${String(r.status).padEnd(6)} ${String(r.ms + 'ms').padEnd(8)} ${String(r.type || '').padEnd(18)} ${r.path}`);
  if (r.snippet) console.log(`       ↳ ${r.snippet}`);
}
const bad = results.filter((r) => r.status !== 200);
console.log(`\n${results.length - bad.length}/${results.length} ok, ${bad.length} failing`);
