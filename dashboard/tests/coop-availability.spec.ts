import { test, expect } from '@playwright/test';
import { MongoClient } from 'mongodb';

const URI = 'mongodb://localhost:27017/immo';
const FIXTURE_ID = `${Date.now()}-${process.pid}`;
const FIXTURE_PREFIX = `https://fixture.invalid/coop-availability/${FIXTURE_ID}/`;
const FIXTURE_LABEL = `Availability fixture ${FIXTURE_ID}`;
const FIXTURE_URLS = [
  'developer-active',
  'developer-taken',
  'private-active',
  'private-taken',
].map((suffix) => FIXTURE_PREFIX + suffix);

function doc(suffix: string, extra: Record<string, unknown> = {}) {
  return {
    url: FIXTURE_PREFIX + suffix,
    title: `${FIXTURE_LABEL} ${suffix}`,
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

let client: MongoClient | undefined;

test.beforeAll(async () => {
  const nextClient = new MongoClient(URI);
  try {
    await nextClient.connect();
    client = nextClient;
    const listings = nextClient.db('immo').collection('listings');
    await listings.deleteMany({ url: { $in: FIXTURE_URLS } });
    await listings.insertMany([
      doc('developer-active'),
      doc('developer-taken', { listing_status: 'taken' }),
      doc('private-active', {
        coop_kind: 'private_transfer',
        coop_source: 'willhaben',
        description: `${FIXTURE_LABEL} active private transfer`,
      }),
      doc('private-taken', {
        coop_kind: 'private_transfer',
        coop_source: 'willhaben',
        description: `${FIXTURE_LABEL} taken private transfer`,
        listing_status: 'taken',
      }),
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
      .deleteMany({ url: { $in: FIXTURE_URLS } });
  } finally {
    await activeClient.close().catch(() => {});
  }
});

test('/coop hides taken developer offers but keeps active offers', async ({ page }) => {
  await page.goto(`/coop?q=${encodeURIComponent(FIXTURE_LABEL)}`);

  await expect(page.getByTestId('coop-item')).toHaveCount(1);
  await expect(page.getByTestId('coop-address')).toContainText('developer-active');
  await expect(page.locator('body')).not.toContainText('developer-taken');
});

test('/coop/private hides taken private transfers but keeps active transfers', async ({ page }) => {
  await page.goto(`/coop/private?q=${encodeURIComponent(FIXTURE_LABEL)}`);

  await expect(page.getByTestId('private-item')).toHaveCount(1);
  await expect(page.getByTestId('private-title')).toContainText('private-active');
  await expect(page.locator('body')).not.toContainText('private-taken');
});
