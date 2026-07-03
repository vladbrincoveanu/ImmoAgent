import { test, expect } from '@playwright/test';

const LISTINGS = [
  {
    _id: 'geo-0', title: 'A', url: 'https://example.com/0', source_enum: 'willhaben',
    bezirk: '1070', price_total: 300000, area_m2: 70, rooms: 3, score: 40,
    image_url: null, coordinates: { lat: 48.2, lon: 16.35 }, coordinate_source: 'exact',
    landmark_hint: null, price_is_estimated: false,
  },
];

const GEOJSON = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      properties: { bezirk: '1070', name: 'Neubau' },
      geometry: { type: 'Polygon', coordinates: [[[16.33, 48.19], [16.36, 48.19], [16.36, 48.21], [16.33, 48.21], [16.33, 48.19]]] },
    },
    {
      type: 'Feature',
      properties: { bezirk: '1010', name: 'Innere Stadt' },
      geometry: { type: 'Polygon', coordinates: [[[16.36, 48.20], [16.39, 48.20], [16.39, 48.22], [16.36, 48.22], [16.36, 48.20]]] },
    },
  ],
};

const HEATMAP = { districts: { '1070': { avg_price_per_m2: 6200, count: 42 }, '1010': { avg_price_per_m2: 9000, count: 12 } } };

test.beforeEach(async ({ page }) => {
  await page.route('**/api/listings/map**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ listings: LISTINGS, total: LISTINGS.length }) }));
  await page.route('**/api/listings/stream**', (route) =>
    route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' }));
  await page.route('**/vienna-districts.geojson', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(GEOJSON) }));
  await page.route('**/api/district-heatmap', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(HEATMAP) }));
});

test('toggling District prices renders choropleth polygons, tooltip and legend', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('/dashboard/map');
  await expect(page.locator('.map-desktop .leaflet-marker-icon').first()).toBeVisible({ timeout: 10000 });

  // Open the layers popover and toggle the heatmap on.
  await page.locator('[data-testid="layers-btn"]').click();
  await page.locator('[data-testid="layer-row-heatmap"]').click();

  // Two polygons render in the desktop overlay pane.
  const polys = page.locator('.map-desktop .leaflet-overlay-pane path');
  await expect(polys.first()).toBeVisible({ timeout: 10000 });
  await expect(polys).toHaveCount(2);

  // Legend visible while active (scoped to the desktop map; a hidden mobile
  // MapView also renders one).
  await expect(page.locator('.map-desktop [data-testid="heatmap-legend"]')).toBeVisible();

  // Hover a polygon → tooltip shows district + €/m².
  await polys.first().hover();
  await expect(page.locator('.map-desktop .leaflet-tooltip')).toContainText('/m²');

  // Toggle off → polygons and legend gone.
  await page.locator('[data-testid="layer-row-heatmap"]').click();
  await expect(page.locator('.map-desktop [data-testid="heatmap-legend"]')).toHaveCount(0);
  await expect(page.locator('.map-desktop .leaflet-overlay-pane path')).toHaveCount(0);
});
