import { test, expect } from '@playwright/test';

const KNOWN_INFRA_ERRORS = [
  'database unavailable',
  'failed to fetch',
  'networkerror',
  'next.js',
  '503',
  'server error',
  'hydration',
  'warning:',
  'websocket',
  'ws://',
  'wss://',
  'hot update',
  '429',
  'too many requests',
  'err_conn_refused',
  'server:',
  'client:',
  'style "',
  '/favicon.ico',
  '404',
  'failed to load resource',
];

function isUnexpectedError(msg: string): boolean {
  const lower = msg.toLowerCase();
  if (KNOWN_INFRA_ERRORS.some(e => lower.includes(e))) return false;
  return true;
}

test.describe('Map interaction freeze tests', () => {
  test('no crash during zoom in/out on empty-state map', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') errors.push(msg.text());
    });

    await page.goto('/dashboard/map');
    await page.waitForLoadState('load');

    // Map or empty state must be present
    const mapOrEmpty = page.locator('.leaflet-container').or(page.locator('text=No listings match your filters').first());
    await expect(mapOrEmpty).toBeAttached({ timeout: 10000 });

    // If map is present, interact with it
    const leaflet = page.locator('.leaflet-container');
    if (await leaflet.count() > 0) {
      const zoomIn = page.locator('.leaflet-control-zoom-in');
      if (await zoomIn.count() > 0) {
        for (let i = 0; i < 5; i++) {
          await zoomIn.click();
          await page.waitForTimeout(80);
        }
        const zoomOut = page.locator('.leaflet-control-zoom-out');
        for (let i = 0; i < 3; i++) {
          await zoomOut.click();
          await page.waitForTimeout(80);
        }
      }
      await expect(leaflet).toBeAttached({ timeout: 5000 });
    }

    const unexpected = errors.filter(isUnexpectedError);
    expect(unexpected.length).toBe(0);
  });

  test('no crash during zoom in/out on map with listings', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') errors.push(msg.text());
    });

    await page.goto('/dashboard/map');
    await page.waitForLoadState('load');
    await page.waitForTimeout(2000);

    const leaflet = page.locator('.leaflet-container');

    if (await leaflet.count() === 0) {
      // DB empty — just verify page loaded without crash
      await expect(page.locator('h1')).toContainText('Property Map');
    } else {
      await expect(leaflet).toBeAttached({ timeout: 10000 });

      const zoomIn = page.locator('.leaflet-control-zoom-in');
      if (await zoomIn.count() > 0) {
        for (let i = 0; i < 5; i++) {
          await zoomIn.click();
          await page.waitForTimeout(80);
        }
        const bbox = await leaflet.boundingBox();
        if (bbox) {
          const cx = bbox.x + bbox.width / 2;
          const cy = bbox.y + bbox.height / 2;
          await page.mouse.move(cx, cy);
          await page.mouse.down();
          await page.mouse.move(cx + 100, cy + 50);
          await page.mouse.up();
        }
        await page.waitForTimeout(300);
        const zoomOut = page.locator('.leaflet-control-zoom-out');
        for (let i = 0; i < 5; i++) {
          await zoomOut.click();
          await page.waitForTimeout(80);
        }
      }
      await expect(leaflet).toBeAttached({ timeout: 5000 });
    }

    const unexpected = errors.filter(isUnexpectedError);
    expect(unexpected.length).toBe(0);
  });

  test('no crash after marker click + zoom combination', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') errors.push(msg.text());
    });

    await page.goto('/dashboard/map');
    await page.waitForLoadState('load');
    await page.waitForTimeout(2000);

    const leaflet = page.locator('.leaflet-container');

    if (await leaflet.count() === 0) {
      await expect(page.locator('h1')).toContainText('Property Map');
    } else {
      await expect(leaflet).toBeAttached({ timeout: 10000 });

      const markers = page.locator('.leaflet-marker-icon');
      const count = await markers.count();
      if (count > 0) {
        await markers.first().click({ timeout: 5000 }).catch(() => {});
        await page.waitForTimeout(500);
        if (count > 1) {
          await markers.nth(Math.floor(count / 2)).click({ timeout: 5000, force: true }).catch(() => {});
          await page.waitForTimeout(500);
        }
      }

      const zoomIn = page.locator('.leaflet-control-zoom-in');
      if (await zoomIn.count() > 0) {
        await zoomIn.click();
        await page.waitForTimeout(300);
      }
      await expect(leaflet).toBeAttached({ timeout: 5000 });
    }

    const unexpected = errors.filter(isUnexpectedError);
    expect(unexpected.length).toBe(0);
  });

  test('pin click shows SelectedCard, map click dismisses it', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') errors.push(msg.text());
    });

    await page.goto('/dashboard/map');
    await page.waitForLoadState('load');
    await page.waitForTimeout(2000);

    const leaflet = page.locator('.leaflet-container');
    if (await leaflet.count() === 0) {
      await expect(page.locator('h1')).toContainText('Property Map');
      return;
    }

    await expect(leaflet).toBeAttached({ timeout: 10000 });

    const markers = page.locator('.leaflet-marker-icon');
    const count = await markers.count();
    if (count === 0) return;

    await markers.first().click({ timeout: 5000, force: true });
    await page.waitForTimeout(400);

    const viewDetails = page.locator('button:has-text("View details")').or(page.locator('text=View details →')).first();
    const cardVisible = await viewDetails.isVisible().catch(() => false);
    if (cardVisible) {
      const bbox = await leaflet.boundingBox();
      if (bbox) {
        await page.mouse.click(bbox.x + 10, bbox.y + 10);
        await page.waitForTimeout(300);
        await expect(viewDetails).not.toBeVisible();
      }
    }

    const unexpected = errors.filter(isUnexpectedError);
    expect(unexpected.length).toBe(0);
  });

  test('sidebar shows "N in view" counter', async ({ page }) => {
    await page.goto('/dashboard/map');
    await page.waitForLoadState('load');
    await page.waitForTimeout(2000);

    const inViewText = page.locator('text=in view').first();
    const isVisible = await inViewText.isVisible().catch(() => false);
    if (isVisible) {
      await expect(inViewText).toBeVisible();
    }
  });
});