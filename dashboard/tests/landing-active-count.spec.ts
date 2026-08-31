import { test, expect } from '@playwright/test';
import { MongoClient } from 'mongodb';

const URI = process.env.MONGODB_URI || 'mongodb://localhost:27017/immo';
const FIXTURE_ID = `${Date.now()}-${process.pid}`;
const FIXTURE_PREFIX = `https://fixture.invalid/landing-active/${FIXTURE_ID}/`;

// Producer-shaped rows: the scrapers insert WITHOUT `url_is_valid` (only
// invalidation sets `False`), and coop rows carry no `listing_status` either.
// The landing page's old `{ url_is_valid: true, taken: { $ne: true } }` count
// matched literally nothing against these — regressions here are exactly the
// "0+ Active listings despite N active co-op records" bug. See
// docs/AGENTS-style notes in coop-query.ts for the canonical active idiom.
function coopRow(suffix: string) {
  return {
    url: FIXTURE_PREFIX + suffix,
    title: `Landing fixture ${suffix}`,
    is_genossenschaft: true,
    buyable: false,
    coop_source: 'bautraeger_direct',
    source_enum: 'LANDING_FIXTURE',
    bezirk: '1220',
    area_m2: 75,
  };
}

function purchaseRow(suffix: string) {
  return {
    url: FIXTURE_PREFIX + suffix,
    title: `Landing fixture ${suffix}`,
    source_enum: 'LANDING_FIXTURE',
    bezirk: '1220',
    area_m2: 75,
    price_total: 300000,
    listing_status: 'active',
  };
}

function takenRow(suffix: string) {
  return {
    ...coopRow(suffix),
    listing_status: 'taken',
    url_is_valid: false,
  };
}

let client: MongoClient | undefined;

test.beforeAll(async () => {
  const nextClient = new MongoClient(URI);
  try {
    await nextClient.connect();
    client = nextClient;
    const listings = nextClient.db('immo').collection('listings');
    await listings.deleteMany({ url: { $regex: `^${FIXTURE_PREFIX}` } });
    await listings.insertMany([
      coopRow('coop'),
      purchaseRow('purchase'),
      coopRow('coop-taken'),
      takenRow('taken-explicit'),
    ]);
  } catch (error) {
    if (!client) await nextClient.close().catch(() => {});
    throw error;
  }
});

test.afterAll(async () => {
  const activeClient = client;
  client = undefined;
  if (!activeClient) return;
  try {
    await activeClient.db('immo').collection('listings')
      .deleteMany({ url: { $regex: `^${FIXTURE_PREFIX}` } });
  } finally {
    await activeClient.close().catch(() => {});
  }
});

test('landing page shows non-zero active listings for producer-shaped rows', async ({ page }) => {
  // The canonical "active" definition used across /coop, the map and
  // /api/stats/taken: url_is_valid is present-but-not-false AND not marked
  // taken. Rows where the field is absent (normal scrape) count as active.
  const expectedActive = await client!.db('immo').collection('listings').countDocuments({
    url_is_valid: { $ne: false },
    listing_status: { $ne: 'taken' },
  });

  await page.goto('/');

  const stat = page.locator('div').filter({ hasText: /^\d{1,3}\+$/ }).first();
  await expect(stat, 'landing active-listing count').toBeVisible();
  const shown = parseInt((await stat.innerText()).replace('+', ''), 10);

  expect(Number.isFinite(shown), `count parsed as "${shown}"`).toBe(true);
  expect(shown).toBe(expectedActive);
  expect(shown).toBeGreaterThan(0);
});