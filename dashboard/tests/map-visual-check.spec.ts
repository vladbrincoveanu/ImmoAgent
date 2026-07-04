import { test } from '@playwright/test';

const FIXTURES = [{
  _id: 'geo-0', title: 'A', url: 'https://example.com/0', source_enum: 'willhaben',
  bezirk: '1070', price_total: 300000, area_m2: 70, rooms: 3, score: 40,
  image_url: null, coordinates: { lat: 48.2, lon: 16.35 }, coordinate_source: 'exact',
  landmark_hint: null, price_is_estimated: false,
}];

test.beforeEach(async ({ page }) => {
  await page.route('**/api/listings/map**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ listings: FIXTURES, total: 1 }) }));
  await page.route('**/api/listings/stream**', (route) =>
    route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' }));
});

for (const w of [375, 768, 1280]) {
  test(`map renders @ ${w}px`, async ({ page }) => {
    await page.setViewportSize({ width: w, height: 800 });
    await page.goto('/dashboard/map');
    await page.locator('.leaflet-container:visible').first().waitFor({ timeout: 10000 });
    await page.screenshot({ path: `.test-out/map-${w}.png`, fullPage: false });
  });
}
