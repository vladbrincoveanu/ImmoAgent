// dashboard/scripts/build-districts-geojson.mjs
// Fetch Vienna Bezirksgrenzen (district boundaries) from the City of Vienna
// open-data WFS, remap to 4-digit postal 'bezirk' codes ('1010'..'1230'),
// simplify + round the geometry to shrink the file, and write
// public/vienna-districts.geojson.
import { writeFileSync } from 'node:fs';

const WFS =
  'https://data.wien.gv.at/daten/geo?service=WFS&request=GetFeature&version=1.1.0' +
  '&typeName=ogdwien:BEZIRKSGRENZEOGD&srsName=EPSG:4326&outputFormat=json';

const EPSILON = 0.0004; // ~44 m simplification tolerance (choropleth-scale)
const round = (n) => Math.round(n * 1e4) / 1e4; // ~11 m precision

// --- Ramer–Douglas–Peucker on a ring of [lon,lat] points ---
function perpDist(p, a, b) {
  const [x, y] = p;
  const [x1, y1] = a;
  const [x2, y2] = b;
  const dx = x2 - x1;
  const dy = y2 - y1;
  const len2 = dx * dx + dy * dy;
  if (len2 === 0) return Math.hypot(x - x1, y - y1);
  const t = ((x - x1) * dx + (y - y1) * dy) / len2;
  const px = x1 + t * dx;
  const py = y1 + t * dy;
  return Math.hypot(x - px, y - py);
}

function rdp(points, eps) {
  if (points.length < 3) return points;
  let maxD = 0;
  let idx = 0;
  for (let i = 1; i < points.length - 1; i++) {
    const d = perpDist(points[i], points[0], points[points.length - 1]);
    if (d > maxD) {
      maxD = d;
      idx = i;
    }
  }
  if (maxD > eps) {
    const left = rdp(points.slice(0, idx + 1), eps);
    const right = rdp(points.slice(idx), eps);
    return left.slice(0, -1).concat(right);
  }
  return [points[0], points[points.length - 1]];
}

function simplifyRing(ring) {
  const simplified = rdp(ring, EPSILON).map(([lon, lat]) => [round(lon), round(lat)]);
  // A ring must be closed and have >= 4 positions; fall back to a rounded
  // original if simplification collapsed it.
  if (simplified.length < 4) return ring.map(([lon, lat]) => [round(lon), round(lat)]);
  const first = simplified[0];
  const last = simplified[simplified.length - 1];
  if (first[0] !== last[0] || first[1] !== last[1]) simplified.push([first[0], first[1]]);
  return simplified;
}

function simplifyGeometry(geom) {
  if (geom.type === 'Polygon') {
    return { type: 'Polygon', coordinates: geom.coordinates.map(simplifyRing) };
  }
  if (geom.type === 'MultiPolygon') {
    return { type: 'MultiPolygon', coordinates: geom.coordinates.map((poly) => poly.map(simplifyRing)) };
  }
  throw new Error(`Unexpected geometry type: ${geom.type}`);
}

const res = await fetch(WFS);
if (!res.ok) throw new Error(`WFS fetch failed: ${res.status}`);
const raw = await res.json();

const features = raw.features.map((f) => {
  const p = f.properties;
  const bezNr = Number(p.BEZNR ?? p.BEZ ?? p.DISTRICT_CODE);
  const bezirk = `1${String(bezNr).padStart(2, '0')}0`;
  return {
    type: 'Feature',
    properties: { bezirk, name: p.NAMEG ?? p.NAME ?? bezirk },
    geometry: simplifyGeometry(f.geometry),
  };
});

const bad = features.filter((f) => f.properties.bezirk.includes('NaN'));
if (bad.length) {
  throw new Error(
    `Unmapped district code — inspect property keys: ${Object.keys(raw.features[0].properties).join(', ')}`,
  );
}
if (features.length !== 23) {
  throw new Error(`Expected 23 districts, got ${features.length}`);
}

const out = { type: 'FeatureCollection', features };
writeFileSync(new URL('../public/vienna-districts.geojson', import.meta.url), JSON.stringify(out));
console.log(`Wrote ${features.length} districts, ${(JSON.stringify(out).length / 1024).toFixed(0)}KB`);
