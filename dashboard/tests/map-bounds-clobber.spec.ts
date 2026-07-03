import { test, expect } from '@playwright/test';

/**
 * Regression test for the "0 in view / no pins on desktop" bug.
 *
 * WHY this exists:
 * The /dashboard/map page mounts TWO <MapView> instances at once — a desktop one
 * (.map-desktop, visible >= md) and a mobile one (.md:hidden, display:none on
 * desktop). Both share a single onBoundsChange={setBounds} handler. The hidden
 * mobile map has a 0x0 Leaflet container, so its getBounds() returns degenerate
 * bounds. When that unsized map emitted bounds it clobbered the visible desktop
 * map's real bounds, so viewportListings filtered to zero — the desktop map
 * rendered tiles but NO pins and the rail showed "0 in view".
 *
 * The old marker tests missed this because `.leaflet-marker-icon` also matches
 * the hidden mobile map's markers. This test scopes assertions to `.map-desktop`.
 *
 * Data is mocked so the test is deterministic and does not depend on Mongo.
 */

// Five listings spread across central Vienna, all inside the default
// zoom-13 viewport centered on [48.2082, 16.3738].
const FIXTURE_LISTINGS = [
  { lat: 48.2089, lon: 16.3965 },
  { lat: 48.2050, lon: 16.3700 },
  { lat: 48.2100, lon: 16.3600 },
  { lat: 48.1984, lon: 16.3850 },
  { lat: 48.2020, lon: 16.3750 },
].map((c, i) => ({
  _id: `fixture-${i}`,
  title: `Test listing ${i}`,
  url: `https://example.com/${i}`,
  source_enum: 'willhaben',
  bezirk: '1030',
  price_total: 300000 + i * 10000,
  area_m2: 70 + i,
  rooms: 3,
  score: 35 - i,
  image_url: null,
  coordinates: { lat: c.lat, lon: c.lon },
  coordinate_source: 'district',
  landmark_hint: null,
  price_is_estimated: false,
}));

test.beforeEach(async ({ page }) => {
  await page.route('**/api/listings/map**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ listings: FIXTURE_LISTINGS, total: FIXTURE_LISTINGS.length }),
    });
  });
  // Keep the SSE stream quiet so it doesn't inject extra listings.
  await page.route('**/api/listings/stream**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' });
  });
});

test('desktop map keeps listings in view — hidden mobile map must not clobber bounds', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('/dashboard/map');

  const railCount = page.locator('[data-testid="rail-count"]');
  await expect(railCount).toBeVisible();

  // The bug rendered "0 in view"; a healthy desktop map keeps its viewport
  // listings. Poll long enough that any late bounds emit from the hidden map
  // would have clobbered a good value.
  await expect(railCount).toHaveText(/[1-9]\d* in view/, { timeout: 10000 });

  // The VISIBLE desktop map must actually show pins (scoped to .map-desktop so
  // we don't accidentally match the hidden mobile map's markers).
  const desktopMarkers = page.locator('.map-desktop .leaflet-marker-icon');
  await expect(desktopMarkers.first()).toBeVisible({ timeout: 10000 });
  expect(await desktopMarkers.count()).toBeGreaterThan(0);
});
