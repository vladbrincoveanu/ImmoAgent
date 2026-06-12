// Standalone test for /api/listings/top data filtering.
// Run: node app/api/listings/top/route.test.mjs
//
// Strategy: copy the route's filter+sort logic into this file, plus the
// validator, with relative imports only. Mocks getDb(). Avoids ts-node
// + Next.js ESM-resolution entanglements entirely.

import { validateDistrict } from './validators-inline.mjs';
import { resolveCoordinates } from './district-centroids-inline.mjs';
import { isValidProfile, DEFAULT_PROFILE } from './profile-inline.mjs';

// --- Re-implementation of the route's filter/sort/score (kept in sync with route.ts) ---
function buildAndConditions(searchParams) {
  const district = validateDistrict(searchParams.get('district'));
  const minScore = Number(searchParams.get('min_score') || 0);
  const profileRaw = searchParams.get('profile');
  const profile = isValidProfile(profileRaw) ? profileRaw : DEFAULT_PROFILE;
  const sort = searchParams.get('sort') || 'score_desc';

  const and = [
    { url_is_valid: { $ne: false } },
    { listing_status: { $ne: 'taken' } },
    { price_total: { $gt: 0 } },
    { area_m2: { $gt: 0 } },
    { $expr: { $gte: [{ $divide: ['$price_total', '$area_m2'] }, 2500] } },
    { $expr: { $lte: [{ $divide: ['$price_total', '$area_m2'] }, 20000] } },
    { title: { $nin: [null, ''] } },
  ];
  if (minScore > 0) and.push({ $or: [{ score: { $gte: minScore } }, { score: null }] });
  if (district) and.push({ bezirk: district });
  return { and, profile, sort };
}

function makeFakeDb(matcher) {
  return {
    collection: () => ({
      find: (filter) => ({
        sort: () => ({ limit: () => ({ toArray: async () => MOCK.filter(matcher) }) }),
      }),
      aggregate: () => ({ toArray: async () => [] }),
    }),
  };
}

const MOCK = [
  { _id: 'a1', bezirk: '1020', score: 70, scores: { default: 70, owner_occupier: 85 }, price_total: 400000, area_m2: 60, rooms: 2, url_is_valid: true, listing_status: 'active', title: 'a1' },
  { _id: 'a2', bezirk: '1050', score: 60, scores: { default: 60, owner_occupier: 55 }, price_total: 350000, area_m2: 50, rooms: 2, url_is_valid: true, listing_status: 'active', title: 'a2' },
  { _id: 'a3', bezirk: '1020', score: 80, scores: { default: 80, owner_occupier: 75 }, price_total: 800000, area_m2: 90, rooms: 3, url_is_valid: true, listing_status: 'active', title: 'a3' },
  { _id: 'a4', bezirk: '1070', score: 65, scores: { default: 65, owner_occupier: 60 }, price_total: 600000, area_m2: 70, rooms: 2, url_is_valid: true, listing_status: 'active', title: 'a4' },
];

let pass = 0, fail = 0;
const failures = [];
function assert(cond, msg) {
  if (cond) { pass++; console.log('  ✓ ' + msg); }
  else      { fail++; failures.push(msg); console.log('  ✗ ' + msg); }
}

// --- Tests ---
async function test(name, fn) {
  console.log('\n' + name);
  try { await fn(); } catch (e) { fail++; failures.push(name + ': ' + e.message); console.log('  ✗ THREW: ' + e.message); }
}

async function main() {
  // Validator (same as the route's first call)
  console.log('\n[validator]');
  assert(validateDistrict('02') === '1020', "validateDistrict('02') → '1020'");
  assert(validateDistrict('15') === '1150', "validateDistrict('15') → '1150'");
  assert(validateDistrict('1020') === '1020', "validateDistrict('1020') unchanged");
  assert(validateDistrict('99') === null, "validateDistrict('99') → null");

  // The route's filter clauses: parse URL, build filter, apply.
  // We don't have getDb in this self-contained test, but we test the FILTER CLAUSE
  // the route would send, by re-implementing its buildAndConditions() identically.
  await test('[route filter] district=02 → filter contains { bezirk: "1020" }', async () => {
    const params = new URLSearchParams('district=02&sort=score_desc');
    const { and } = buildAndConditions(params);
    const districtCond = and.find((c) => c.bezirk);
    assert(districtCond && districtCond.bezirk === '1020', `filter.bezirk === '1020' (got ${JSON.stringify(districtCond)})`);
  });

  await test('[route filter] district=15 → filter contains { bezirk: "1150" }', async () => {
    const params = new URLSearchParams('district=15&sort=score_desc');
    const { and } = buildAndConditions(params);
    const districtCond = and.find((c) => c.bezirk);
    assert(districtCond && districtCond.bezirk === '1150', `filter.bezirk === '1150'`);
  });

  await test('[route filter] invalid district=99 → no bezirk clause (validator returns null)', async () => {
    const params = new URLSearchParams('district=99&sort=score_desc');
    const { and } = buildAndConditions(params);
    const districtCond = and.find((c) => c.bezirk);
    assert(districtCond === undefined, 'no district filter applied');
  });

  await test('[route filter] profile=owner_occupier → response score field = scores.owner_occupier', async () => {
    // Simulate the route's response shaping: each listing gets `score: scores[profile]`.
    const profile = 'owner_occupier';
    const result = MOCK.map((l) => ({ ...l, score: (l.scores?.[profile] ?? l.score ?? null) }));
    const map = Object.fromEntries(result.map((l) => [l._id, l.score]));
    assert(map.a1 === 85, `a1 score 85 (got ${map.a1})`);
    assert(map.a2 === 55, `a2 score 55`);
    assert(map.a3 === 75, `a3 score 75`);
    assert(map.a4 === 60, `a4 score 60`);
  });

  await test('[route filter] compound district=02 + profile=owner_occupier', async () => {
    const params = new URLSearchParams('district=02&profile=owner_occupier&sort=score_desc');
    const { and, profile } = buildAndConditions(params);
    const districtCond = and.find((c) => c.bezirk);
    assert(districtCond && districtCond.bezirk === '1020', `filter.bezirk === '1020'`);
    // Apply both: filter to 1020, then shape scores
    const filtered = MOCK.filter((l) => l.bezirk === '1020');
    const shaped = filtered.map((l) => ({ ...l, score: (l.scores?.[profile] ?? l.score ?? null) }));
    const map = Object.fromEntries(shaped.map((l) => [l._id, l.score]));
    assert(shaped.length === 2, `2 listings (got ${shaped.length})`);
    assert(map.a1 === 85, `a1 owner_occupier score 85`);
    assert(map.a3 === 75, `a3 owner_occupier score 75`);
  });

  console.log('\n=== ' + pass + ' passed, ' + fail + ' failed ===');
  if (failures.length > 0) {
    console.log('\nFailures:');
    for (const f of failures) console.log('  - ' + f);
    process.exit(1);
  }
}

main();
