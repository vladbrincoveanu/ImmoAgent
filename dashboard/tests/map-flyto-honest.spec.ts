import { test, expect } from '@playwright/test';

// Four geocoded fixtures (in the default zoom-13 viewport) + one un-geocoded.
const GEOCODED = [
  { lat: 48.2089, lon: 16.3965 },
  { lat: 48.2050, lon: 16.3700 },
  { lat: 48.2100, lon: 16.3600 },
  { lat: 48.1984, lon: 16.3850 },
].map((c, i) => ({
  _id: `geo-${i}`,
  title: `Geocoded ${i}`,
  url: `https://example.com/g${i}`,
  source_enum: 'willhaben',
  bezirk: '1030',
  price_total: 300000 + i * 10000,
  area_m2: 70 + i,
  rooms: 3,
  score: 40 - i,
  image_url: null,
  coordinates: { lat: c.lat, lon: c.lon },
  coordinate_source: 'exact',
  landmark_hint: null,
  price_is_estimated: false,
}));

const NO_COORD = {
  _id: 'none-0',
  title: 'No location listing',
  url: 'https://example.com/n0',
  source_enum: 'willhaben',
  bezirk: '1100',
  price_total: 250000,
  area_m2: 60,
  rooms: 2,
  score: 30,
  image_url: null,
  coordinates: null,
  coordinate_source: 'none',
  landmark_hint: null,
  price_is_estimated: false,
};

const FIXTURES = [...GEOCODED, NO_COORD];

test.beforeEach(async ({ page }) => {
  await page.route('**/api/listings/map**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ listings: FIXTURES, total: FIXTURES.length }),
    });
  });
  await page.route('**/api/listings/stream**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' });
  });
});

test('un-geocoded listing has no marker on the desktop map', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('/dashboard/map');

  const markers = page.locator('.map-desktop .leaflet-marker-icon');
  await expect(markers.first()).toBeVisible({ timeout: 10000 });
  // Exactly the four geocoded fixtures render; the 'none' listing does not.
  await expect(markers).toHaveCount(4);
});

test('clicking a rail card flies the map to that listing', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('/dashboard/map');

  await expect(page.locator('.map-desktop .leaflet-marker-icon').first()).toBeVisible({ timeout: 10000 });

  // Click the rail card for geo-3 (bottom of the viewport).
  await page.locator('[data-testid="slim-listing-card"][data-id="geo-3"]').click();

  // flyTo runs ~1.2s; poll the live map center exposed on the container.
  await expect
    .poll(
      async () => {
        return page.evaluate(() => {
          const el = document.querySelector('.map-desktop .leaflet-container') as
            | (Element & { __map?: { getCenter(): { lat: number; lng: number } } })
            | null;
          const c = el?.__map?.getCenter();
          return c ? Math.round(c.lat * 1000) : null;
        });
      },
      { timeout: 8000 }
    )
    .toBe(Math.round(48.1984 * 1000));

  const lng = await page.evaluate(() => {
    const el = document.querySelector('.map-desktop .leaflet-container') as
      | (Element & { __map?: { getCenter(): { lat: number; lng: number } } })
      | null;
    return el?.__map?.getCenter().lng ?? null;
  });
  expect(lng).not.toBeNull();
  expect(Math.abs((lng as number) - 16.385)).toBeLessThan(0.002);
});
