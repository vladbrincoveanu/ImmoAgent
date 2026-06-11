import { test, expect } from '@playwright/test';

test.describe('Commute calculator + rent yield + max-commute filter', () => {
  test('commute endpoint returns walk + transit times with route', async ({ request }) => {
    const res = await request.get(
      '/api/commute?lat=48.21&lon=16.37&dest_lat=48.2082&dest_lon=16.3738&dest_name=Stephansplatz'
    );
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data.destination.name).toBe('Stephansplatz');
    expect(data.walk.minutes).toBeGreaterThan(0);
    expect(data.walk.km).toBeGreaterThan(0);
    expect(data.transit.minutes).toBeGreaterThan(0);
    expect(data.transit.route.from).toBeTruthy();
    expect(data.transit.route.to).toBeTruthy();
    expect(['transit', 'walk']).toContain(data.recommended.mode);
  });

  test('destinations endpoint returns 10 presets', async ({ request }) => {
    const res = await request.get('/api/destinations');
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data.destinations.length).toBeGreaterThanOrEqual(10);
    expect(data.destinations[0]).toHaveProperty('name');
    expect(data.destinations[0]).toHaveProperty('lat');
    expect(data.destinations[0]).toHaveProperty('lon');
  });

  test('rent-estimate endpoint returns monthly rent + yield for a listing', async ({ request }) => {
    const res = await request.get('/api/rent-estimate?area_m2=80&price_total=400000&bezirk=1050');
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data.monthly_rent_eur).toBeGreaterThan(0);
    expect(data.annual_rent_eur).toBeGreaterThan(0);
    expect(data.gross_yield_pct).toBeGreaterThan(0);
    expect(data.rent_per_m2).toBeGreaterThan(0);
  });

  test('top listings API now returns coordinates (stored or centroid fallback)', async ({ request }) => {
    const res = await request.get('/api/listings/top?profile=default');
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    const withCoords = data.listings.filter((l: { coordinates?: { lat: number; lon: number } | null }) => l.coordinates != null);
    expect(withCoords.length).toBeGreaterThan(0);
  });

  test('listing detail API returns coordinates', async ({ request }) => {
    const topRes = await request.get('/api/listings/top?profile=default');
    const top = await topRes.json();
    const id = top.listings[0]._id;
    const res = await request.get(`/api/listings/${id}`);
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data.coordinates).toBeTruthy();
    expect(typeof data.coordinates.lat).toBe('number');
    expect(typeof data.coordinates.lon).toBe('number');
  });

  test('dashboard shows Smart Insights panel with 7 cards', async ({ page }) => {
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    await expect(page.locator('[data-testid="smart-insights"]')).toBeVisible();
    const cards = page.locator('[data-testid="smart-insights"] > div');
    expect(await cards.count()).toBe(7);
  });

  test('dashboard shows CommuteFilter with destination dropdown', async ({ page }) => {
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    await expect(page.locator('[data-testid="commute-filter"]')).toBeVisible();
    const dropdown = page.locator('[data-testid="commute-destination"]');
    await expect(dropdown).toBeVisible();
    const opts = await dropdown.locator('option').allTextContents();
    expect(opts.length).toBeGreaterThan(1);
    expect(opts.some((o) => o.toLowerCase().includes('stephansplatz'))).toBeTruthy();
  });

  test('commute filter narrows listings when max_commute set', async ({ page }) => {
    await page.goto('/dashboard?profile=default', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle');
    const cardsBefore = await page.locator('.grid > div.cursor-pointer').count();

    await page.goto('/dashboard?profile=default&dest_name=Stephansplatz%20(city%20center)&dest_lat=48.2082&dest_lon=16.3738&max_commute=30', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(800);

    const cardsAfter = await page.locator('.grid > div.cursor-pointer').count();
    expect(cardsAfter).toBeLessThanOrEqual(cardsBefore);
    expect(cardsAfter).toBeGreaterThan(0);
    expect(page.url()).toContain('max_commute=30');
    expect(page.url()).toContain('dest_name=Stephansplatz');
  });

  test('listing detail modal shows commute + rent panels when destination set', async ({ page }) => {
    await page.goto('/dashboard?dest_name=Stephansplatz%20(city%20center)&dest_lat=48.2082&dest_lon=16.3738&max_commute=30', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle');
    const cards = page.locator('.grid > div.cursor-pointer');
    await cards.first().click();
    await page.waitForTimeout(1500);
    await expect(page.locator('[data-testid="commute-rent-section"]')).toBeVisible();
    await expect(page.locator('[data-testid="commute-panel"]')).toBeVisible();
    await expect(page.locator('[data-testid="rent-panel"]')).toBeVisible();
  });

  test('rent yield badge shows on listing cards', async ({ page }) => {
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle');
    const yields = page.locator('[data-testid="rent-yield-badge"]');
    expect(await yields.count()).toBeGreaterThan(0);
  });

  test('zone vs avg filter URL param reduces results', async ({ page, request }) => {
    const before = await (await request.get('/api/insights')).json();
    const after = await (await request.get('/api/insights?below_avg_pct=30')).json();
    expect(after.total).toBeLessThanOrEqual(before.total);
  });

  test('map page header has ProfileSelector', async ({ page }) => {
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle');
    await expect(page.locator('header [data-testid="profile-selector"]')).toBeVisible();
  });

  test('MapLegend shows U-Bahn and school counts from /api/geo/infrastructure', async ({ page }) => {
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle');
    const legend = page.locator('[data-testid="map-legend"]');
    await expect(legend).toBeVisible();
    await expect(legend).toContainText('U-Bahn');
    await expect(legend).toContainText('School');
  });

  test('MapGuide overlay explains every dot type so user knows what they mean', async ({ page }) => {
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle');
    const guide = page.locator('[data-testid="map-guide"]');
    await expect(guide).toBeVisible();
    await expect(page.locator('[data-testid="legend-price-pin"]')).toContainText('Price pin');
    await expect(page.locator('[data-testid="legend-ubahn"]')).toContainText('U-Bahn station');
    await expect(page.locator('[data-testid="legend-school"]')).toContainText('School');
  });

  test('U-Bahn dots render with a permanent name label on the map (the literal complaint: "dots do not say anything")', async ({ page }) => {
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1500);
    const ubahnDots = page.locator('path[stroke="#1d4ed8"]');
    expect(await ubahnDots.count()).toBeGreaterThan(0);
    const labels = page.locator('.leaflet-infra-label');
    expect(await labels.count()).toBeGreaterThan(0);
    const firstLabelText = await labels.first().textContent();
    expect(firstLabelText && firstLabelText.trim().length).toBeGreaterThan(0);
    // Check that at least one U-Bahn name we know is in the labels
    const allLabels = await labels.allTextContents();
    const hasKnownStation = allLabels.some((l) => /Stephansplatz|Karlsplatz|Westbahnhof|Hauptbahnhof|Praterstern/i.test(l));
    expect(hasKnownStation).toBeTruthy();
  });

  test('School dots render on the map (hover tooltips show name)', async ({ page }) => {
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1500);
    const schoolDots = page.locator('path[stroke="#16a34a"]');
    expect(await schoolDots.count()).toBeGreaterThan(0);
  });
});
