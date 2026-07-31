import { test, expect } from '@playwright/test';
import { MongoClient } from 'mongodb';

// Covers the two filter controls that replaced the old Bauträger <select> and the
// Zimmer/Fläche bucket chips: a free-text name search (`q`) and open numeric
// min/max ranges (`rooms_min`/`rooms_max`, `area_min`/`area_max`).
//
// Seeded fixture in the local Mongo (mongodb://localhost:27017/immo), both 3-Zimmer:
//   A  1130  OEVW  3 Zi  63 m²     €550  Thomas-Morus-Gasse 2-12
//   B  1220  OESW  3 Zi  70.09 m²  €945  Erzherzog-Karl-Straße 140
const A = 'Thomas-Morus-Gasse 2-12';
const B = 'Erzherzog-Karl-Straße 140';

const count = (page: import('@playwright/test').Page) => page.getByTestId('coop-item');

test.describe('/coop free-text search', () => {
  test('matches builder name, case-insensitively', async ({ page }) => {
    await page.goto('/coop?q=OEVW');
    await expect(count(page)).toHaveCount(1);
    await expect(page.getByTestId('coop-address')).toContainText(A);

    // Lower-case must find the same row — the query uses $options:'i'.
    await page.goto('/coop?q=oevw');
    await expect(count(page)).toHaveCount(1);
    await expect(page.getByTestId('coop-address')).toContainText(A);
  });

  test('matches a street name in the address, not just the builder', async ({ page }) => {
    await page.goto('/coop?q=erzherzog');
    await expect(count(page)).toHaveCount(1);
    await expect(page.getByTestId('coop-address')).toContainText(B);
  });

  test('matches a mid-string substring', async ({ page }) => {
    // "Morus" is not a prefix of any field — an anchored regex would miss it.
    await page.goto('/coop?q=Morus');
    await expect(count(page)).toHaveCount(1);
    await expect(page.getByTestId('coop-address')).toContainText(A);
  });

  test('treats regex metacharacters as literal text (no injection, no ReDoS)', async ({ page }) => {
    // Unescaped, `.*` would match every row. Escaped, it is a literal two-char
    // string that appears in no name field, so the correct answer is zero.
    await page.goto('/coop?q=' + encodeURIComponent('.*'));
    await expect(count(page)).toHaveCount(0);
    await expect(page.getByTestId('coop-empty')).toBeVisible();

    // A classic catastrophic-backtracking payload must also be inert. If this
    // reached Mongo unescaped it could pin the server; escaped it is just text.
    await page.goto('/coop?q=' + encodeURIComponent('(a+)+$'));
    await expect(count(page)).toHaveCount(0);
    await expect(page.getByTestId('coop-empty')).toBeVisible();
  });

  test('round-trips the search box and offers builder names as suggestions', async ({ page }) => {
    await page.goto('/coop?q=OEVW');
    await expect(page.getByTestId('filter-q')).toHaveValue('OEVW');

    // Suggestions come from the full inventory, so both builders are offered even
    // while filtered down to one.
    const opts = page.locator('#coop-builder-names option');
    await expect(opts).toHaveCount(2);
    await expect(opts.nth(0)).toHaveAttribute('value', 'OESW');
    await expect(opts.nth(1)).toHaveAttribute('value', 'OEVW');
  });
});

test.describe('/coop numeric min/max ranges', () => {
  test('rooms range includes and excludes on both bounds', async ({ page }) => {
    // Both fixtures are 3 Zimmer.
    await page.goto('/coop?rooms_min=3&rooms_max=3');
    await expect(count(page)).toHaveCount(2);

    await page.goto('/coop?rooms_min=4');
    await expect(count(page)).toHaveCount(0);

    await page.goto('/coop?rooms_max=2');
    await expect(count(page)).toHaveCount(0);
  });

  test('area range splits the two fixtures and handles fractional m²', async ({ page }) => {
    // A is 63 m², B is 70.09 m².
    await page.goto('/coop?area_min=65');
    await expect(count(page)).toHaveCount(1);
    await expect(page.getByTestId('coop-address')).toContainText(B);

    await page.goto('/coop?area_max=65');
    await expect(count(page)).toHaveCount(1);
    await expect(page.getByTestId('coop-address')).toContainText(A);

    // Brackets B's real scraped float (70.09) — a bucket implementation that
    // rounded to 70 would drop it.
    await page.goto('/coop?area_min=70&area_max=71');
    await expect(count(page)).toHaveCount(1);
    await expect(page.getByTestId('coop-address')).toContainText(B);
  });

  test('blank boxes mean no bound, not zero', async ({ page }) => {
    // The regression this guards: Number('') === 0, so a naive parse turns an
    // empty "bis" box into area_m2 <= 0 and empties the page.
    await page.goto('/coop?rooms_min=&rooms_max=&area_min=&area_max=');
    await expect(count(page)).toHaveCount(2);

    // Junk is ignored the same way rather than throwing or matching everything.
    await page.goto('/coop?area_min=abc&rooms_max=-5');
    await expect(count(page)).toHaveCount(2);
  });

  test('an inverted range matches nothing rather than everything', async ({ page }) => {
    await page.goto('/coop?rooms_min=4&rooms_max=2');
    await expect(count(page)).toHaveCount(0);
    await expect(page.getByTestId('coop-empty')).toBeVisible();
  });

  test('round-trips the range boxes', async ({ page }) => {
    await page.goto('/coop?rooms_min=2&area_max=80');
    await expect(page.getByTestId('filter-rooms-min')).toHaveValue('2');
    await expect(page.getByTestId('filter-area-max')).toHaveValue('80');
    await expect(page.getByTestId('filter-rooms-max')).toHaveValue('');
  });

  test('combines the text search with a range', async ({ page }) => {
    // OEVW (63 m²) is excluded by the area floor even though the name matches.
    await page.goto('/coop?q=OEVW&area_min=65');
    await expect(count(page)).toHaveCount(0);

    await page.goto('/coop?q=OEVW&area_min=60');
    await expect(count(page)).toHaveCount(1);
    await expect(page.getByTestId('coop-address')).toContainText(A);
  });
});

test.describe('/coop legacy filter URLs', () => {
  // The bucket chips and the Bauträger dropdown are gone from the UI, but old
  // bookmarks and Telegram deep links still carry their params. Silently
  // ignoring them would widen those links to the whole inventory.
  test('still honours the removed bucket and dropdown params', async ({ page }) => {
    await page.goto('/coop?bautraeger=OEVW');
    await expect(count(page)).toHaveCount(1);
    await expect(page.getByTestId('coop-address')).toContainText(A);

    await page.goto('/coop?rooms=4');
    await expect(count(page)).toHaveCount(0);

    await page.goto('/coop?area=51-74');
    await expect(count(page)).toHaveCount(2);

    await page.goto('/coop?area=0-50');
    await expect(count(page)).toHaveCount(0);
  });
});

test.describe('/coop rooms range matches the displayed rounded value', () => {
  // The page renders Math.round(rooms), so a 2,5-Zimmer unit shows "3 Zimmer".
  // Filtering "von 3" must therefore include it, or the user is told 3 Zimmer
  // and then cannot find the row by asking for 3. No seeded fixture has a
  // fractional room count, so this test supplies one and removes it again.
  const URL_MARKER = 'https://example.invalid/coop-rounding-fixture';
  let client: MongoClient | undefined;

  test.beforeAll(async () => {
    client = new MongoClient('mongodb://localhost:27017/immo');
    await client.connect();
    await client.db().collection('listings').insertOne({
      url: URL_MARKER,
      title: 'Rundungsgasse 1, 1100 Wien – 2,5 Zimmer',
      address: 'Rundungsgasse 1, 1100 Wien',
      bezirk: '1100',
      rooms: 2.5,
      area_m2: 55,
      price_total: 600,
      bautraeger: 'ROUNDFIXTURE',
      is_genossenschaft: true,
      url_is_valid: true,
      coop_source: 'mygewo',
      buyable: false,
      processed_at: 1,
    });
  });

  test.afterAll(async () => {
    // Must run even on failure: the sibling specs assert an exact count of 2.
    await client?.db().collection('listings').deleteOne({ url: URL_MARKER });
    await client?.close();
  });

  test('a 2,5-Zimmer unit displayed as "3 Zimmer" is found by rooms_min=3', async ({ page }) => {
    await page.goto('/coop?q=ROUNDFIXTURE');
    await expect(count(page)).toHaveCount(1);
    // Confirm the premise: the page really does show it as 3 Zimmer.
    await expect(page.getByTestId('coop-rooms')).toHaveText('3 rooms');

    await page.goto('/coop?q=ROUNDFIXTURE&rooms_min=3');
    await expect(count(page)).toHaveCount(1);

    await page.goto('/coop?q=ROUNDFIXTURE&rooms_max=3');
    await expect(count(page)).toHaveCount(1);

    // ...and it is still excluded by a genuinely higher floor.
    await page.goto('/coop?q=ROUNDFIXTURE&rooms_min=4');
    await expect(count(page)).toHaveCount(0);
  });
});
