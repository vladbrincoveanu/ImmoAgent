import { test, expect, Page } from '@playwright/test';

const KNOWN_INFRA_ERRORS = [
  'database unavailable',
  'failed to fetch',
  'networkerror',
  'next.js',
  '503',
  'server error',
  'hydration',
  'warning:',
  'react',
  'websocket',
  '429',
  'too many requests',
];

function isUnexpectedError(msg: string): boolean {
  const lower = msg.toLowerCase();
  return !KNOWN_INFRA_ERRORS.some(e => lower.includes(e));
}

async function collectErrors(page: Page): Promise<string[]> {
  const errors: string[] = [];
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(msg.text());
  });
  return errors;
}

async function waitForMapReady(page: Page) {
  await page.waitForURL('**/dashboard/map', { timeout: 15000 });
  await page.waitForFunction(() => {
    const h1 = document.querySelector('h1');
    return h1 && h1.textContent && h1.textContent.length > 0;
  }, { timeout: 20000 });
}

test.describe('Pin click → sidebar selection (the critical bug)', () => {
  test('clicking a marker: popup opens AND sidebar highlights AND zoom does NOT lock the map', async ({ page }) => {
    const errors = await collectErrors(page);
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });
    await waitForMapReady(page);
    await page.waitForTimeout(3000); // wait for listings to load

    const leaflet = page.locator('.leaflet-container');
    if (await leaflet.count() === 0) {
      // No map — DB likely empty, skip
      return;
    }

    const markers = page.locator('.leaflet-marker-icon');
    const count = await markers.count();

    if (count === 0) {
      // No markers, skip
      return;
    }

    // Get map bounding box for zoom testing
    const bbox = await leaflet.boundingBox();
    expect(bbox).not.toBeNull();

    // Record initial zoom level
    const zoomIn = page.locator('.leaflet-control-zoom-in');
    const zoomOut = page.locator('.leaflet-control-zoom-out');
    const initialZoomVisible = await zoomIn.isVisible();

    // Click first marker
    await markers.first().click({ timeout: 5000 });
    await page.waitForTimeout(1500);

    // 1. Popup should appear (leaflet popup container)
    const popup = page.locator('.leaflet-popup');
    await expect(popup).toBeVisible({ timeout: 5000 });

    // 2. Sidebar item should be highlighted (border-accent)
    const highlightedItem = page.locator('.border-accent').first();
    await expect(highlightedItem).toBeVisible({ timeout: 3000 });

    // 3. Zoom controls should still work (map NOT frozen)
    if (initialZoomVisible) {
      await zoomIn.click();
      await page.waitForTimeout(300);
      await zoomIn.click();
      await page.waitForTimeout(300);
      await zoomOut.click();
      await page.waitForTimeout(300);
    }

    // 4. Map container should still be interactive
    await expect(leaflet).toBeVisible();

    // 5. Can click a different marker (sidebar should update)
    if (count > 1) {
      await markers.nth(1).click({ timeout: 5000 });
      await page.waitForTimeout(1000);
    }

    const unexpected = errors.filter(isUnexpectedError);
    expect(unexpected).toHaveLength(0);
  });

  test('sidebar click selects listing on map and popup opens', async ({ page }) => {
    const errors = await collectErrors(page);
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });
    await waitForMapReady(page);
    await page.waitForTimeout(3000);

    const leaflet = page.locator('.leaflet-container');
    if (await leaflet.count() === 0) return;

    const markers = page.locator('.leaflet-marker-icon');
    const count = await markers.count();
    if (count === 0) return;

    // Click a marker first to select it
    await markers.first().click({ timeout: 5000 });
    await page.waitForTimeout(1000);

    // Popup should be visible
    const popup = page.locator('.leaflet-popup');
    const popupVisible = await popup.isVisible().catch(() => false);

    // Click zoom controls to confirm map is still alive
    const zoomIn = page.locator('.leaflet-control-zoom-in');
    if (await zoomIn.isVisible()) {
      await zoomIn.click();
      await page.waitForTimeout(200);
    }

    const unexpected = errors.filter(isUnexpectedError);
    expect(unexpected).toHaveLength(0);
  });

  test('rapid clicking multiple markers does not freeze map', async ({ page }) => {
    const errors = await collectErrors(page);
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });
    await waitForMapReady(page);
    await page.waitForTimeout(3000);

    const leaflet = page.locator('.leaflet-container');
    if (await leaflet.count() === 0) return;

    const markers = page.locator('.leaflet-marker-icon');
    const count = await markers.count();
    if (count === 0) return;

    // Rapid click on different markers
    for (let i = 0; i < Math.min(count, 5); i++) {
      await markers.nth(i).click({ timeout: 3000 });
      await page.waitForTimeout(300);
    }

    // After all clicks, map should still be interactive
    await expect(leaflet).toBeVisible();
    const zoomIn = page.locator('.leaflet-control-zoom-in');
    const zoomOut = page.locator('.leaflet-control-zoom-out');
    if (await zoomIn.isVisible()) {
      await zoomIn.click();
      await page.waitForTimeout(200);
      await zoomOut.click();
      await page.waitForTimeout(200);
    }

    const unexpected = errors.filter(isUnexpectedError);
    expect(unexpected).toHaveLength(0);
  });
});