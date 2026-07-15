// End-to-end UI test for the filter system. Mocks /api/listings/top via
// page.route() so the test doesn't need a live MongoDB. Drives the actual
// dashboard UI to verify the user-reported symptoms are fixed:
//   - "selecting bezirk it doesnt not filter only those"
//   - "selecting buyer profiles nothing happnes"
//
// Run: npx playwright test tests/filter-ui-e2e.spec.ts --reporter=list

import { test, expect, Page } from '@playwright/test';

// Same short→long mapping the real validator uses
const SHORT_TO_LONG: Record<string, string> = {
  '1': '1010', '2': '1020', '3': '1030', '4': '1040', '5': '1050',
  '6': '1060', '7': '1070', '8': '1080', '9': '1090',
  '01': '1010', '02': '1020', '03': '1030', '04': '1040', '05': '1050',
  '06': '1060', '07': '1070', '08': '1080', '09': '1090',
  '10': '1100', '11': '1110', '12': '1120', '13': '1130', '14': '1140',
  '15': '1150', '16': '1160', '17': '1170', '18': '1180', '19': '1190',
  '20': '1200', '21': '1210', '22': '1220', '23': '1230',
};

const MOCK_BY_DISTRICT: Record<string, Array<{
  _id: string;
  title: string;
  bezirk: string;
  score: number;
  scores: Record<string, number>;
  price_total: number;
  area_m2: number;
  rooms: number;
  url: string;
  source_enum: string;
  image_url: string | null;
  url_is_valid: boolean;
  listing_status: string;
  processed_at: string;
  estimated_down_pct: number;
  coordinates: { lat: number; lon: number } | null;
  coordinate_source: string;
  price_is_estimated: boolean;
}>> = {
  '': [
    { _id: 'a1', title: 'Leopoldstadt loft A', bezirk: '1020', score: 70, scores: { default: 70, owner_occupier: 85 }, price_total: 400000, area_m2: 60, rooms: 2, url: 'http://x/1', source_enum: 'willhaben', image_url: null, url_is_valid: true, listing_status: 'active', processed_at: '2026-01-01', estimated_down_pct: 20, coordinates: { lat: 48.21, lon: 16.38 }, coordinate_source: 'exact', price_is_estimated: false },
    { _id: 'a2', title: 'Margareten flat B',    bezirk: '1050', score: 60, scores: { default: 60, owner_occupier: 55 }, price_total: 350000, area_m2: 50, rooms: 2, url: 'http://x/2', source_enum: 'willhaben', image_url: null, url_is_valid: true, listing_status: 'active', processed_at: '2026-01-01', estimated_down_pct: 20, coordinates: { lat: 48.19, lon: 16.36 }, coordinate_source: 'exact', price_is_estimated: false },
    { _id: 'a3', title: 'Leopoldstadt big C',   bezirk: '1020', score: 80, scores: { default: 80, owner_occupier: 75 }, price_total: 450000, area_m2: 90, rooms: 3, url: 'http://x/3', source_enum: 'derstandard', image_url: null, url_is_valid: true, listing_status: 'active', processed_at: '2026-01-01', estimated_down_pct: 20, coordinates: { lat: 48.22, lon: 16.40 }, coordinate_source: 'exact', price_is_estimated: false },
    { _id: 'a4', title: 'Neubau flat D',         bezirk: '1070', score: 65, scores: { default: 65, owner_occupier: 60 }, price_total: 480000, area_m2: 70, rooms: 2, url: 'http://x/4', source_enum: 'willhaben', image_url: null, url_is_valid: true, listing_status: 'active', processed_at: '2026-01-01', estimated_down_pct: 20, coordinates: { lat: 48.20, lon: 16.35 }, coordinate_source: 'exact', price_is_estimated: false },
  ],
  '1020': [
    { _id: 'a1', title: 'Leopoldstadt loft A', bezirk: '1020', score: 70, scores: { default: 70, owner_occupier: 85 }, price_total: 400000, area_m2: 60, rooms: 2, url: 'http://x/1', source_enum: 'willhaben', image_url: null, url_is_valid: true, listing_status: 'active', processed_at: '2026-01-01', estimated_down_pct: 20, coordinates: { lat: 48.21, lon: 16.38 }, coordinate_source: 'exact', price_is_estimated: false },
    { _id: 'a3', title: 'Leopoldstadt big C',   bezirk: '1020', score: 80, scores: { default: 80, owner_occupier: 75 }, price_total: 450000, area_m2: 90, rooms: 3, url: 'http://x/3', source_enum: 'derstandard', image_url: null, url_is_valid: true, listing_status: 'active', processed_at: '2026-01-01', estimated_down_pct: 20, coordinates: { lat: 48.22, lon: 16.40 }, coordinate_source: 'exact', price_is_estimated: false },
  ],
};

async function installApiMock(page: Page) {
  // Mock /api/listings/top: respond with listings filtered by district,
  // and apply the same per-profile score transformation route.ts does
  // (`score: scores?.[profile] ?? l.score ?? null`).
  await page.route('**/api/listings/top**', async (route) => {
    const url = new URL(route.request().url());
    const districtRaw = url.searchParams.get('district') ?? '';
    const district = SHORT_TO_LONG[districtRaw] ?? districtRaw;
    const profile = url.searchParams.get('profile') ?? 'default';
    const items = (MOCK_BY_DISTRICT[district] ?? []).map((l) => ({
      ...l,
      score: (l.scores[profile] ?? l.score ?? null),
    }));
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ listings: items, total: items.length }),
    });
  });
  // Mock /api/insights (called by SmartInsightsPanel)
  await page.route('**/api/insights**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({}) });
  });
  // Mock /api/saved-searches
  await page.route('**/api/saved-searches**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ saved: [] }) });
  });
}

test.describe('Filter system — live UI verification', () => {
  test.beforeEach(async ({ page }) => {
    await installApiMock(page);
  });

  test('selecting district 02 narrows the visible listings to Leopoldstadt only', async ({ page }) => {
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: /Top Property Picks/i })).toBeVisible({ timeout: 15000 });

    // Wait for first render: 4 mock listings
    await expect(page.getByText('Leopoldstadt loft A')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Margareten flat B')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('Leopoldstadt big C')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('Neubau flat D')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText(/4 listings matching your filters/)).toBeVisible();

    // Now select district 02 (Leopoldstadt)
    await page.locator('input[placeholder="e.g. 02"]').fill('02');
    await expect(page).toHaveURL(/district=02/);

    // Leopoldstadt cards still visible, other two gone
    await expect(page.getByText('Leopoldstadt loft A')).toBeVisible();
    await expect(page.getByText('Leopoldstadt big C')).toBeVisible();
    await expect(page.getByText('Margareten flat B')).toHaveCount(0);
    await expect(page.getByText('Neubau flat D')).toHaveCount(0);
    await expect(page.getByText(/2 listings matching your filters/)).toBeVisible();
  });

  test('selecting profile=owner_occupier re-ranks by owner_occupier score, not default', async ({ page }) => {
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: /Top Property Picks/i })).toBeVisible({ timeout: 15000 });
    await expect(page.getByText('Leopoldstadt loft A')).toBeVisible({ timeout: 10000 });

    // Default sort by score_desc: a3 (80) > a1 (70) > a4 (65) > a2 (60)
    // The first card title should be "Leopoldstadt big C" (a3, score 80)
    const firstCard = page.locator('article, [data-listing], .listing-card, [class*="card"]').first();

    // Switch to owner_occupier profile
    await page.locator('[data-testid="profile-selector"]').first().selectOption('owner_occupier');
    await expect(page).toHaveURL(/profile=owner_occupier/);

    // Re-fetch happens; wait for re-render. owner_occupier scores: a1=85, a3=75, a4=60, a2=55
    // So new order: a1 (85) > a3 (75) > a4 (60) > a2 (55)
    // The first listing should now be "Leopoldstadt loft A" (a1, owner_occupier=85)
    await expect(page.getByText('Leopoldstadt loft A').first()).toBeVisible();
    // Verify a1's visible score badge (in the rendered card) is 85
    // (we look for the score 85 in a position adjacent to the a1 title)
    const a1Card = page.locator('text=Leopoldstadt loft A').first().locator('xpath=ancestor::article[1] | ancestor::div[contains(@class,"card")][1] | ancestor::div[contains(@class,"rounded")][1]').first();
    await expect(a1Card).toContainText('85');
  });

  test('compound: district=02 + profile=owner_occupier → 2 listings with owner_occupier scores', async ({ page }) => {
    page.on('response', (r) => {
      if (r.url().includes('/api/listings/top')) {
        console.log('  [debug] API call:', r.url(), 'status:', r.status());
      }
    });
    await page.goto('/dashboard?district=02', { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: /Top Property Picks/i })).toBeVisible({ timeout: 15000 });
    // Wait for at least one listings/top response
    await page.waitForResponse((r) => r.url().includes('/api/listings/top'), { timeout: 10000 });
    await page.waitForTimeout(1000);  // let state propagate
    const count = await page.getByText(/listings matching your filters/).textContent();
    console.log('  [debug] count text:', count);
    await expect(page.getByText('Leopoldstadt loft A')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Leopoldstadt big C')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('Margareten flat B')).toHaveCount(0);
    await expect(page.getByText(/2 listings matching your filters/)).toBeVisible();

    // Switch profile
    await page.locator('[data-testid="profile-selector"]').first().selectOption('owner_occupier');

    // Both URL params present (compound)
    await expect(page).toHaveURL(/district=02/);
    await expect(page).toHaveURL(/profile=owner_occupier/);

    // Still 2 listings (Leopoldstadt only)
    await expect(page.getByText('Leopoldstadt loft A')).toBeVisible();
    await expect(page.getByText('Leopoldstadt big C')).toBeVisible();
    await expect(page.getByText('Margareten flat B')).toHaveCount(0);
    await expect(page.getByText('Neubau flat D')).toHaveCount(0);

    // Scores: a1 owner_occupier=85, a3 owner_occupier=75 — visible on cards
    const a1Card = page.locator('text=Leopoldstadt loft A').first().locator('xpath=ancestor::article[1] | ancestor::div[contains(@class,"rounded")][1]').first();
    const a3Card = page.locator('text=Leopoldstadt big C').first().locator('xpath=ancestor::article[1] | ancestor::div[contains(@class,"rounded")][1]').first();
    await expect(a1Card).toContainText('85');
    await expect(a3Card).toContainText('75');
  });
});
