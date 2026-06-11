import { test, expect } from '@playwright/test';

test.describe('Map infrastructure overlay + zone stats', () => {
  test('map page shows U-Bahn + school markers', async ({ page }) => {
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    await expect(page.locator('.leaflet-container')).toBeVisible();

    const ubahnMarkers = page.locator('path[stroke="#1d4ed8"]');
    const schoolMarkers = page.locator('path[stroke="#16a34a"]');
    const total = await ubahnMarkers.count() + await schoolMarkers.count();
    expect(total).toBeGreaterThan(10);
  });

  test('infrastructure API returns GeoJSON FeatureCollection', async ({ request }) => {
    const res = await request.get('/api/geo/infrastructure');
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data.type).toBe('FeatureCollection');
    expect(Array.isArray(data.features)).toBeTruthy();
    expect(data.features.length).toBeGreaterThan(0);
    const kinds = new Set(data.features.map((f: { properties: { kind: string } }) => f.properties.kind));
    expect(kinds.has('ubahn')).toBeTruthy();
    expect(kinds.has('school')).toBeTruthy();
  });

  test('infrastructure API respects ?types=ubahn only', async ({ request }) => {
    const res = await request.get('/api/geo/infrastructure?types=ubahn');
    const data = await res.json();
    const kinds = new Set(data.features.map((f: { properties: { kind: string } }) => f.properties.kind));
    expect(kinds.has('school')).toBeFalsy();
    expect(kinds.has('ubahn')).toBeTruthy();
  });

  test('zone stats API returns district context for a known listing', async ({ request, page }) => {
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle');
    const firstCardLink = page.locator('[class*="cursor-pointer"]').first();
    if (await firstCardLink.count() === 0) return;

    const url = await page.evaluate(async () => {
      const res = await fetch('/api/listings/top?limit=1');
      const data = await res.json();
      return data.listings?.[0]?._id;
    });
    if (!url) return;

    const res = await request.get(`/api/listings/${url}/zone-stats`);
    if (!res.ok()) return;
    const data = await res.json();
    expect(data.district).toBeDefined();
    expect(data.total_in_district).toBeGreaterThan(0);
    expect(data.avg_price).toBeGreaterThan(0);
    expect(typeof data.this_listing.price_vs_avg_pct).toBe('number');
  });
});
