import { test, expect } from '@playwright/test';

// Regression guard for the "filters render zero properties" bug.
// Root cause was /api/listings/map returning coordinates:null for every
// un-geocoded listing (no district-centroid fallback), which the viewport
// filter then hid — empty map + empty rail on databases with sparse
// geocoding. WHY these tests: they pin the server contract (fallback
// coordinates) and the user-visible outcome (pins + cards) for both views.

test.describe('map API coordinate fallback', () => {
  test('un-geocoded listings with a known Bezirk get district-centroid coordinates', async ({ request }) => {
    const res = await request.get('/api/listings/map?sort=score_desc');
    expect(res.status()).toBe(200);
    const { listings } = await res.json();
    expect(listings.length).toBeGreaterThan(0);

    const withBezirk = listings.filter(
      (l: { bezirk?: string | null }) => typeof l.bezirk === 'string' && /^1\d{2}0$/.test(l.bezirk)
    );
    expect(withBezirk.length).toBeGreaterThan(0);
    for (const l of withBezirk) {
      expect(l.coordinates, `listing ${l._id} (bezirk ${l.bezirk}) must have coordinates`).not.toBeNull();
      expect(l.coordinate_source).not.toBe('none');
    }
  });

  test('min_score keeps score-less listings (parity with /api/listings/top)', async ({ request }) => {
    const res = await request.get('/api/listings/map?min_score=30&sort=score_desc');
    expect(res.status()).toBe(200);
    const { listings } = await res.json();
    expect(listings.length).toBeGreaterThan(0);
    for (const l of listings) {
      const ok = l.score === null || l.score >= 30;
      expect(ok, `listing ${l._id} score=${l.score} violates min_score contract`).toBe(true);
    }
  });
});

test.describe('filtered views still render properties', () => {
  test('map view with min_score filter shows pins and rail cards', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto('/dashboard/map?min_score=30');

    const markers = page.locator('.map-desktop .leaflet-marker-icon');
    await expect(markers.first()).toBeVisible({ timeout: 15000 });
    expect(await markers.count()).toBeGreaterThan(0);

    const railCards = page.locator('[data-testid="slim-listing-card"]');
    await expect(railCards.first()).toBeVisible({ timeout: 15000 });
  });

  test('dashboard view with min_score filter shows a non-zero match count', async ({ page }) => {
    await page.goto('/dashboard?min_score=30');
    await expect(page.locator('h1')).toContainText('Top Property Picks');
    await expect(page.getByText(/^[1-9]\d* listings? matching your filters$/)).toBeVisible({
      timeout: 15000,
    });
  });

  test('dashboard commute filter still returns listings', async ({ page }) => {
    await page.goto(
      '/dashboard?dest_name=Stephansplatz&dest_lat=48.2083&dest_lon=16.3731&max_commute=45'
    );
    await expect(page.getByText(/^[1-9]\d* listings? matching your filters$/)).toBeVisible({
      timeout: 15000,
    });
  });
});
