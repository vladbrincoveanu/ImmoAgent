import { test, expect } from '@playwright/test';
import { MongoClient } from 'mongodb';

/**
 * Several apartments in one Genossenschaft project legitimately share a single
 * builder reservation URL — mygewo gives per-unit /angebot/ pages only for the
 * first result page. They used to collapse into one rendered row (duplicate
 * React key on `url`), which is one half of why /coop showed 17 of ~58 units.
 *
 * Seeds its own rows into a district the other co-op specs don't use, and
 * removes them again, so the fixed counts they assert stay valid.
 */
const URI = process.env.MONGODB_URI || 'mongodb://localhost:27017/immo';
const SHARED_URL = 'https://www.example-bt.at/projekt/1030-siblings';
const MARKER = 'Geschwistergasse';

// Production shape after the identity fix: one `builder_url` for the project,
// a per-unit `url` fragment (the `url` index is unique, so siblings cannot
// share one — verified: seeding identical urls fails with E11000), and a
// coop_uid per unit. That the scraper produces these is guarded on the Python
// side; this spec guards that the page renders them as separate rows.
const sibling = (n: number) => ({
  url: `${SHARED_URL}#mygewo-sib${n}`,
  coop_uid: `mygewo:sib${n}`,
  builder_url: SHARED_URL,
  source: 'genossenschaft',
  source_enum: 'genossenschaft',
  is_genossenschaft: true,
  coop_source: 'bautraeger_direct',
  buyable: false,
  bautraeger: 'SIBLING-CONTROL',
  bezirk: '1030',
  address: `${MARKER} 1, 1030 Wien`,
  rooms: 3,
  area_m2: 68,
  price_total: 700 + n,
  processed_at: 1_700_000_000 + n,
});

let client: MongoClient;

test.beforeAll(async () => {
  client = await MongoClient.connect(URI);
  await client.db().collection('listings').insertMany([sibling(1), sibling(2), sibling(3)]);
});

test.afterAll(async () => {
  await client.db().collection('listings').deleteMany({ bautraeger: 'SIBLING-CONTROL' });
  await client.close();
});

test('units sharing one project URL each render as their own row', async ({ page }) => {
  const errors: string[] = [];
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push(m.text());
  });

  await page.goto('/coop?bezirk=1030');

  const items = page.getByTestId('coop-item');
  await expect(items).toHaveCount(3);
  await expect(page.getByTestId('coop-count')).toHaveText('3 Treffer');

  // Distinct rows, not one row rendered three times: each shows its own rent.
  const rents = await items.getByTestId('coop-rent').allTextContents();
  expect(new Set(rents).size).toBe(3);

  // …while all three still link to the one page where the project is reserved.
  const hrefs = await items.getByRole('link').first().evaluateAll((links) =>
    links.map((l) => (l as HTMLAnchorElement).getAttribute('href')),
  );
  expect(hrefs.every((h) => h === SHARED_URL)).toBe(true);

  await expect(page.locator('body')).toContainText(MARKER);
  expect(errors).toHaveLength(0);
});
