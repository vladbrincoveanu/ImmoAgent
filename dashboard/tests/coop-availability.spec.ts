import { test, expect } from '@playwright/test';
import { MongoClient } from 'mongodb';

const URI = process.env.MONGODB_URI || 'mongodb://localhost:27017/immo';
const FIXTURE_PREFIX = 'https://fixture.invalid/coop-availability/';

function doc(suffix: string, extra: Record<string, unknown> = {}) {
  return {
    url: FIXTURE_PREFIX + suffix,
    title: `Availability fixture ${suffix}`,
    address: `Availabilitygasse ${suffix}, 1220 Wien`,
    bezirk: '1220',
    rooms: 3,
    area_m2: 80,
    price_total: 900,
    own_funds: 10000,
    bautraeger: 'FixtureBau',
    builder_url: FIXTURE_PREFIX + 'builder/' + suffix,
    image_url: null,
    special_features: [],
    is_genossenschaft: true,
    buyable: false,
    coop_source: 'bautraeger_direct',
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
    doc('developer-active'),
    doc('developer-taken', { listing_status: 'taken' }),
    doc('private-active', {
      coop_kind: 'private_transfer',
      coop_source: 'willhaben',
      description: 'Active private transfer',
    }),
    doc('private-taken', {
      coop_kind: 'private_transfer',
      coop_source: 'willhaben',
      description: 'Taken private transfer',
      listing_status: 'taken',
    }),
  ]);
});

test.afterAll(async () => {
  await client.db('immo').collection('listings')
    .deleteMany({ url: { $regex: '^' + FIXTURE_PREFIX } });
  await client.close();
});

test('/coop hides taken developer offers but keeps active offers', async ({ page }) => {
  await page.goto('/coop');

  await expect(page.getByTestId('coop-item')).toHaveCount(1);
  await expect(page.getByTestId('coop-address')).toContainText('developer-active');
  await expect(page.locator('body')).not.toContainText('developer-taken');
});

test('/coop/private hides taken private transfers but keeps active transfers', async ({ page }) => {
  await page.goto('/coop/private');

  await expect(page.getByTestId('private-item')).toHaveCount(1);
  await expect(page.getByTestId('private-title')).toContainText('private-active');
  await expect(page.locator('body')).not.toContainText('private-taken');
});
