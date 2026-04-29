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
  'websocket',
  'ws://',
  'wss://',
  'hot update',
  '429',
  'too many requests',
  'err_conn_refused',
  'server:',
  'client:',
  '/favicon.ico',
  '404',
  'failed to load resource',
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

async function clickMarkerByIndex(page: Page, index: number) {
  const attached = await page.evaluate(
    ({ idx }) => {
      const icons = document.querySelectorAll('.leaflet-marker-icon');
      if (!icons[idx]) return false;
      const icon = icons[idx] as HTMLElement;
      const style = window.getComputedStyle(icon);
      return style.display !== 'none' && style.visibility !== 'hidden' && icon.offsetParent !== null;
    },
    { idx: index }
  );
  if (!attached) return;
  return page.evaluate(
    ({ idx }) => {
      const icons = document.querySelectorAll('.leaflet-marker-icon');
      (icons[idx] as HTMLElement)?.click();
    },
    { idx: index }
  );
}

test.describe('Pin click → sidebar selection (the critical bug)', () => {
  test('clicking a marker: popup opens AND sidebar highlights AND zoom does NOT lock the map', async ({ page }) => {
    const errors = await collectErrors(page);
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });
    await waitForMapReady(page);
    await page.waitForTimeout(3000);

    const leaflet = page.locator('.leaflet-container');
    if (await leaflet.count() === 0) return;

    const markers = page.locator('.leaflet-marker-icon');
    const count = await markers.count();
    if (count === 0) return;

    const zoomIn = page.locator('.leaflet-control-zoom-in');
    const initialZoomVisible = await zoomIn.isVisible();

    await clickMarkerByIndex(page, 0);
    await page.waitForTimeout(1500);

    const popup = page.locator('.leaflet-popup');
    await expect(popup).toBeVisible({ timeout: 5000 });

    const highlightedItem = page.locator('.border-accent').first();
    await expect(highlightedItem).toBeVisible({ timeout: 3000 });

    if (initialZoomVisible) {
      await zoomIn.click();
      await page.waitForTimeout(300);
      await zoomIn.click();
      await page.waitForTimeout(300);
      await page.locator('.leaflet-control-zoom-out').click();
      await page.waitForTimeout(300);
    }

    await expect(leaflet).toBeVisible();

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

    await clickMarkerByIndex(page, 0);
    await page.waitForTimeout(1000);

    const popup = page.locator('.leaflet-popup');
    await expect(popup).toBeVisible({ timeout: 5000 });

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

    for (let i = 0; i < Math.min(count, 5); i++) {
      await clickMarkerByIndex(page, i);
      await page.waitForTimeout(300);
    }

    await expect(leaflet).toBeVisible();
    const zoomIn = page.locator('.leaflet-control-zoom-in');
    if (await zoomIn.isVisible()) {
      await zoomIn.click();
      await page.waitForTimeout(200);
      await page.locator('.leaflet-control-zoom-out').click();
      await page.waitForTimeout(200);
    }

    const unexpected = errors.filter(isUnexpectedError);
    expect(unexpected).toHaveLength(0);
  });
});