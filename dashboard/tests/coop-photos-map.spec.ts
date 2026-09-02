import { test, expect } from '@playwright/test';
import { MongoClient } from 'mongodb';

/** Co-op photos on /coop and co-op pins on the map.
 *
 * The local DB holds only a handful of co-op rows and none with coordinates or
 * a photo, so these tests seed their own — otherwise they would pass on an
 * empty result set and prove nothing. Fixtures are keyed by a URL prefix that
 * cannot collide with scraped data and are removed again in afterAll. */
const URI = process.env.MONGODB_URI || 'mongodb://localhost:27017/immo';
const FIXTURE_PREFIX = 'https://fixture.invalid/coop-photos-map/';
// Same-origin and genuinely loadable: pointing the "good" fixture at an
// unresolvable host would race its own onError handler and swap in the
// placeholder mid-assertion.
const IMAGE_URL = '/icon.svg';
const BROKEN_IMAGE_URL = 'https://unresolvable.invalid/gone.jpg';

// A rent, not a purchase price — the exact shape that the map's purchase-tuned
// €/m² band used to reject (945 / 70 ≈ €13/m²).
const RENT = 945;

function coopDoc(suffix: string, extra: Record<string, unknown>) {
  return {
    url: FIXTURE_PREFIX + suffix,
    title: `Fixture co-op ${suffix}`,
    address: `Fixturegasse ${suffix}, 1220 Wien`,
    bezirk: '1220',
    rooms: 3,
    area_m2: 70.09,
    price_total: RENT,
    own_funds: 8000,
    bautraeger: 'FixtureBau',
    builder_url: FIXTURE_PREFIX + suffix,
    special_features: ['Balkon'],
    is_genossenschaft: true,
    buyable: false,
    coop_source: 'bautraeger_direct',
    url_is_valid: true,
    listing_status: 'active',
    processed_at: Math.floor(Date.now() / 1000),
    coordinates: { lat: 48.2245, lon: 16.4356 },
    coordinate_source: 'exact',
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
    coopDoc('with-photo', { image_url: IMAGE_URL }),
    coopDoc('no-photo', { image_url: null }),
    coopDoc('broken-photo', { image_url: BROKEN_IMAGE_URL }),
    coopDoc('high-price', { price_total: 350000 }),
  ]);
});

test.afterAll(async () => {
  await client.db('immo').collection('listings')
    .deleteMany({ url: { $regex: '^' + FIXTURE_PREFIX } });
  await client.close();
});

test('/coop renders a photo for a unit that has one', async ({ page }) => {
  await page.goto('/coop?bezirk=1220');
  const row = page.locator('[data-testid="coop-item"]', {
    hasText: 'Fixturegasse with-photo',
  });
  await expect(row).toBeVisible();
  const thumb = row.locator('[data-testid="coop-thumb"]');
  await expect(thumb).toHaveAttribute('src', IMAGE_URL);
  // The thumbnail must occupy real layout space, not collapse to a 0-px box.
  const box = await thumb.boundingBox();
  expect(box!.width).toBeGreaterThan(50);
  expect(box!.height).toBeGreaterThan(50);
});

test('/coop falls back to a placeholder when the photo fails to load', async ({ page }) => {
  // Builder images are hotlinked, so 403s and dead URLs are routine — the row
  // must degrade to the placeholder instead of showing a broken-image glyph.
  await page.goto('/coop?bezirk=1220');
  const row = page.locator('[data-testid="coop-item"]', {
    hasText: 'Fixturegasse broken-photo',
  });
  await expect(row).toBeVisible();
  await expect(row.locator('[data-testid="coop-thumb-fallback"]')).toBeVisible();
  await expect(row.locator('[data-testid="coop-thumb"]')).toHaveCount(0);
});

test('/coop falls back to a placeholder when a unit has no photo', async ({ page }) => {
  await page.goto('/coop?bezirk=1220');
  const row = page.locator('[data-testid="coop-item"]', {
    hasText: 'Fixturegasse no-photo',
  });
  await expect(row).toBeVisible();
  await expect(row.locator('[data-testid="coop-thumb-fallback"]')).toBeVisible();
  await expect(row.locator('[data-testid="coop-thumb"]')).toHaveCount(0);
});

test('map returns co-op rentals that the purchase €/m² band used to reject', async ({ request }) => {
  const res = await request.get('/api/listings/map?genossenschaft=true&sort=score_desc');
  expect(res.ok()).toBeTruthy();
  const body = await res.json();
  const urls = (body.listings as Array<{ url: string; coordinates: unknown }>)
    .map((l) => l.url);
  expect(urls).toContain(FIXTURE_PREFIX + 'with-photo');
  expect(urls).toContain(FIXTURE_PREFIX + 'no-photo');
});

test('purchase map excludes co-op rentals', async ({ request }) => {
  const res = await request.get('/api/listings/map');
  expect(res.ok()).toBeTruthy();
  const body = await res.json();
  const urls = (body.listings as Array<{ url: string }>).map((l) => l.url);
  expect(urls).not.toContain(FIXTURE_PREFIX + 'with-photo');
});

test('purchase top endpoint excludes co-op rows even when their price looks like a purchase', async ({ request }) => {
  const res = await request.get('/api/listings/top?limit=100');
  expect(res.ok()).toBeTruthy();
  const body = await res.json();
  const urls = (body.listings as Array<{ url: string }>).map((l) => l.url);
  expect(urls).not.toContain(FIXTURE_PREFIX + 'high-price');
});

test('co-op pins label the rent as monthly', async ({ page }) => {
  // The map sidebar also renders the broken-photo fixture, whose host is
  // deliberately unresolvable. That one failed request is expected; it is
  // matched by ORIGIN, so any other console error still fails the test.
  const errors: string[] = [];
  page.on('console', (m) => {
    if (m.type() !== 'error') return;
    if (m.location()?.url?.includes('unresolvable.invalid')) return;
    errors.push(m.text());
  });

  // Armed BEFORE goto: the map fires its fetch during page load, so a listener
  // attached afterwards can miss the response entirely and hang.
  const mapResponse = page.waitForResponse(
    (r) => r.url().includes('/api/listings/map') && r.url().includes('genossenschaft=true') && r.ok(),
  );
  await page.goto('/dashboard/map?genossenschaft=true');
  await mapResponse;

  // €945 on a co-op pin is a monthly rent; without the suffix it reads as a
  // €945 apartment sitting next to €450k ones.
  await expect(page.locator('.leaflet-marker-icon', { hasText: '€945/mo' }).first())
    .toBeVisible({ timeout: 15000 });
  expect(errors).toHaveLength(0);
});
