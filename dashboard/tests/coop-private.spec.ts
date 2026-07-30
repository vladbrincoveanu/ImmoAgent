import { test, expect } from '@playwright/test';
import { MongoClient } from 'mongodb';

/** The /coop/private rubric: co-op flats passed on directly by sitting tenants.
 *
 * Seeds its own fixtures — the local DB has no private-transfer rows, so every
 * assertion here would otherwise pass against an empty list and prove nothing.
 * The two negative fixtures are the point of the page: a builder-direct co-op
 * unit and an ordinary rental with a kitchen Ablöse must BOTH stay out. */
const URI = process.env.MONGODB_URI || 'mongodb://localhost:27017/immo';
const FIXTURE_PREFIX = 'https://fixture.invalid/coop-private/';

function doc(suffix: string, extra: Record<string, unknown>) {
  return {
    url: FIXTURE_PREFIX + suffix,
    title: `Fixture Weitergabe ${suffix}`,
    address: `Weitergabegasse ${suffix}, 1100 Wien`,
    bezirk: '1100',
    rooms: 3,
    area_m2: 68,
    price_total: 890,
    url_is_valid: true,
    listing_status: 'active',
    processed_at: Math.floor(Date.now() / 1000),
    ...extra,
  };
}

let client: MongoClient;

test.beforeAll(async () => {
  client = new MongoClient(URI);
  await client.connect();
  const listings = client.db('immo').collection('listings');
  await listings.deleteMany({ url: { $regex: '^' + FIXTURE_PREFIX } });
  await listings.insertMany([
    doc('transfer-a', {
      coop_kind: 'private_transfer',
      is_genossenschaft: true,
      coop_source: 'willhaben',
      description: 'Genossenschaftswohnung, Nachmieter gesucht, Ablöse VB.',
      first_seen_at: '2026-07-30T09:00:00Z',
    }),
    doc('transfer-b', {
      coop_kind: 'private_transfer',
      is_genossenschaft: true,
      coop_source: 'willhaben',
      description: 'Geförderte Wohnung weiterzugeben, Eigenmittelanteil übernehmen.',
      first_seen_at: '2026-07-30T08:00:00Z',
    }),
    // Builder-direct co-op: belongs on /coop, never here.
    doc('builder-direct', {
      is_genossenschaft: true,
      buyable: false,
      coop_source: 'bautraeger_direct',
      description: 'Genossenschaftswohnung über Bauträger, Vergabe per Wohnticket.',
    }),
    // The classic false positive: an Ablöse with no co-op involvement.
    doc('kitchen-abloese', {
      description: 'Freifinanzierte Wohnung, Küche gegen Ablöse zu übernehmen.',
    }),
  ]);
});

test.afterAll(async () => {
  await client.db('immo').collection('listings')
    .deleteMany({ url: { $regex: '^' + FIXTURE_PREFIX } });
  await client.close();
});

test('/coop/private lists only private transfers', async ({ page }) => {
  await page.goto('/coop/private');
  await expect(page.getByTestId('coop-private-page')).toBeVisible();

  const titles = await page.getByTestId('private-title').allTextContents();
  const joined = titles.join(' | ');
  expect(joined).toContain('transfer-a');
  expect(joined).toContain('transfer-b');
  // The two that must never appear.
  expect(joined).not.toContain('builder-direct');
  expect(joined).not.toContain('kitchen-abloese');
});

test('newest transfer sorts first — the only part of an FCFS feed that matters',
  async ({ page }) => {
    await page.goto('/coop/private');
    const titles = await page.getByTestId('private-title').allTextContents();
    const a = titles.findIndex((t) => t.includes('transfer-a'));
    const b = titles.findIndex((t) => t.includes('transfer-b'));
    expect(a).toBeGreaterThanOrEqual(0);
    expect(b).toBeGreaterThanOrEqual(0);
    expect(a).toBeLessThan(b);
  });

test('search matches the ad body, not just the title', async ({ page }) => {
  // "Eigenmittelanteil" appears ONLY in transfer-b's description. A title-only
  // search would return nothing here, which is the bug this guards.
  await page.goto('/coop/private?q=Eigenmittelanteil');
  const titles = await page.getByTestId('private-title').allTextContents();
  expect(titles.join(' | ')).toContain('transfer-b');
  expect(titles.join(' | ')).not.toContain('transfer-a');
});

test('search escapes regex metacharacters instead of exploding', async ({ page }) => {
  await page.goto('/coop/private?q=' + encodeURIComponent('(a+)+$'));
  // Renders an empty state rather than 500ing or hanging on backtracking.
  await expect(page.getByTestId('coop-private-page')).toBeVisible();
  await expect(page.getByTestId('private-empty')).toBeVisible();
});

test('district filter narrows the list', async ({ page }) => {
  await page.goto('/coop/private?bezirk=1210');
  await expect(page.getByTestId('private-empty')).toBeVisible();
});
