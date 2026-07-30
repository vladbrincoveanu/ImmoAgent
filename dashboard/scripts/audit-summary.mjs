#!/usr/bin/env node
// Reads `npm audit --json` on stdin and prints a compact severity summary.
// Exists because the human-readable `npm audit` output is filtered by rtk and
// cannot be trusted; the JSON form is the only reliable source.
let raw = '';
process.stdin.on('data', (d) => (raw += d));
process.stdin.on('end', () => {
  const j = JSON.parse(raw);
  console.log('TOTALS: ' + JSON.stringify(j.metadata.vulnerabilities));
  for (const [name, v] of Object.entries(j.vulnerabilities || {})) {
    const fa = v.fixAvailable;
    const fix =
      fa && typeof fa === 'object'
        ? `${fa.name}@${fa.version}${fa.isSemVerMajor ? ' MAJOR' : ''}`
        : String(fa);
    const via = (v.via || [])
      .map((y) => (typeof y === 'string' ? y : y.title))
      .join('; ');
    console.log(`${v.severity} | ${name} | ${v.range} | fix=${fix} | via=${via}`);
  }
});
