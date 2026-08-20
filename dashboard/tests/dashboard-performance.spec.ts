import { test, expect, type Page } from '@playwright/test';

const LISTINGS = {
  listings: [
    {
      _id: 'exact-1',
      title: 'Exact-coordinate flat',
      url: 'https://example.test/exact-1',
      source_enum: 'willhaben',
      bezirk: '1010',
      price_total: 420000,
      area_m2: 60,
      rooms: 2,
      score: 82,
      scores: { default: 82 },
      image_url: null,
      coordinates: { lat: 48.2082, lon: 16.3738 },
      coordinate_source: 'exact',
      price_is_estimated: false,
      landmark_hint: null,
    },
    {
      _id: 'district-1',
      title: 'District fallback flat',
      url: 'https://example.test/district-1',
      source_enum: 'willhaben',
      bezirk: '1020',
      price_total: 360000,
      area_m2: 55,
      rooms: 2,
      score: 74,
      scores: { default: 74 },
      image_url: null,
      coordinates: { lat: 48.2126, lon: 16.3899 },
      coordinate_source: 'district',
      price_is_estimated: false,
      landmark_hint: null,
    },
  ],
  total: 2,
};

async function mockDashboardApis(page: Page) {
  await page.route('**/api/listings/map*', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(LISTINGS),
  }));
  await page.route('**/api/listings/top*', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(LISTINGS),
  }));
  await page.route('**/api/geo/infrastructure*', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ type: 'FeatureCollection', features: [] }),
  }));
  await page.route('**/api/insights*', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({}),
  }));
  await page.route('**/api/listings/stream*', (route) => route.fulfill({
    status: 200,
    contentType: 'text/event-stream',
    body: 'data: {"type":"unsupported"}\n\n',
  }));
}

test('desktop mounts one Leaflet map and requests listings once', async ({ page }) => {
  await mockDashboardApis(page);
  const listingRequests: string[] = [];
  page.on('request', (request) => {
    if (request.url().includes('/api/listings/map')) listingRequests.push(request.url());
  });

  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('/dashboard/map');

  await expect(page.locator('.leaflet-container')).toHaveCount(1);
  expect(listingRequests).toHaveLength(1);
});

test('mobile mounts one Leaflet map', async ({ page }) => {
  await mockDashboardApis(page);

  await page.setViewportSize({ width: 375, height: 800 });
  await page.goto('/dashboard/map');

  await expect(page.locator('.leaflet-container')).toHaveCount(1);
});

test('a superseded listing response cannot overwrite the latest response', async ({ page }) => {
  await mockDashboardApis(page);
  await page.unroute('**/api/listings/map*');

  let requestCount = 0;
  let releaseFirstRequest = () => {};
  const firstRequestHeld = new Promise<void>((resolve) => {
    releaseFirstRequest = resolve;
  });
  await page.route('**/api/listings/map*', async (route) => {
    requestCount += 1;
    if (requestCount === 1) {
      await firstRequestHeld;
      try {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(LISTINGS),
        });
      } catch {
        // The abortable fetch may close the route before the stale response resolves.
      }
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ...LISTINGS,
        listings: [{ ...LISTINGS.listings[0], title: 'Latest listing', score: 99 }],
        total: 1,
      }),
    });
  });

  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('/dashboard/map');
  await page.locator('[data-testid="profile-selector"]').first().selectOption('urban_professional');

  await expect(page.locator('.leaflet-container')).toHaveCount(1);
  await expect(page.locator('[data-testid="title"]').first()).toHaveText('Latest listing');
  releaseFirstRequest();
  await page.waitForTimeout(100);
  await expect(page.locator('[data-testid="title"]').first()).toHaveText('Latest listing');
  expect(requestCount).toBe(2);
});
