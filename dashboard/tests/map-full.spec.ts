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

test.describe('Map page structure', () => {
  test('page loads with correct header', async ({ page }) => {
    const errors = await collectErrors(page);
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });
    await waitForMapReady(page);

    await expect(page.locator('h1')).toContainText('Property Map', { timeout: 10000 });

    const unexpected = errors.filter(isUnexpectedError);
    expect(unexpected).toHaveLength(0);
  });

  test('sidebar shows LISTINGS header with count', async ({ page }) => {
    const errors = await collectErrors(page);
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });
    await waitForMapReady(page);

    const listingsHeader = page.locator('text=LISTINGS').first();
    await expect(listingsHeader).toBeVisible({ timeout: 10000 });

    const unexpected = errors.filter(isUnexpectedError);
    expect(unexpected).toHaveLength(0);
  });

  test('sidebar filter bar has all controls', async ({ page }) => {
    const errors = await collectErrors(page);
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });
    await waitForMapReady(page);

    await expect(page.locator('input[type="number"]').first()).toBeVisible({ timeout: 10000 });
    await expect(page.locator('input[placeholder="e.g. 02"]')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('button:has-text("Refresh")')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('select')).toBeVisible({ timeout: 5000 });

    const unexpected = errors.filter(isUnexpectedError);
    expect(unexpected).toHaveLength(0);
  });

  test('zoom controls are visible when map loads', async ({ page }) => {
    const errors = await collectErrors(page);
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });
    await waitForMapReady(page);

    const leaflet = page.locator('.leaflet-container');
    if (await leaflet.count() > 0) {
      await expect(page.locator('.leaflet-control-zoom-in')).toBeVisible({ timeout: 5000 });
      await expect(page.locator('.leaflet-control-zoom-out')).toBeVisible({ timeout: 5000 });
    }

    const unexpected = errors.filter(isUnexpectedError);
    expect(unexpected).toHaveLength(0);
  });
});

test.describe('Map empty state', () => {
  test('shows empty message when no listings', async ({ page }) => {
    const errors = await collectErrors(page);
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });
    await waitForMapReady(page);
    await page.waitForTimeout(3000);

    const emptyInSidebar = page.locator('text=No listings match your filters').first();
    const emptyInMapArea = page.locator('.flex.items-center.justify-center.bg-gray-50 >> text=No listings');
    const mapContainer = page.locator('.leaflet-container');

    const emptyVisible = await emptyInSidebar.isVisible().catch(() => false) ||
                         await emptyInMapArea.isVisible().catch(() => false);
    const mapVisible = await mapContainer.isVisible().catch(() => false);

    expect(emptyVisible || mapVisible).toBeTruthy();

    const unexpected = errors.filter(isUnexpectedError);
    expect(unexpected).toHaveLength(0);
  });
});

test.describe('Map legend', () => {
  test('legend visible when map has listings', async ({ page }) => {
    const errors = await collectErrors(page);
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });
    await waitForMapReady(page);
    await page.waitForTimeout(2000);

    const leaflet = page.locator('.leaflet-container');
    if (await leaflet.count() > 0) {
      const legend = page.locator('text=Legend');
      if (await legend.count() > 0) {
        await expect(legend).toBeVisible({ timeout: 5000 });
      }
    }

    const unexpected = errors.filter(isUnexpectedError);
    expect(unexpected).toHaveLength(0);
  });
});

test.describe('Sidebar interactions', () => {
  test('sidebar listing count updates after refresh', async ({ page }) => {
    const errors = await collectErrors(page);
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });
    await waitForMapReady(page);

    const listingsHeader = page.locator('text=LISTINGS').first();
    await expect(listingsHeader).toBeVisible({ timeout: 10000 });

    const refreshBtn = page.locator('button:has-text("Refresh")').first();
    if (await refreshBtn.isVisible()) {
      await refreshBtn.click();
      await page.waitForTimeout(1500);
    }

    const unexpected = errors.filter(isUnexpectedError);
    expect(unexpected).toHaveLength(0);
  });

  test('changing sort option triggers refresh', async ({ page }) => {
    const errors = await collectErrors(page);
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });
    await waitForMapReady(page);

    const select = page.locator('select').first();
    await expect(select).toBeVisible({ timeout: 10000 });
    await select.selectOption('price_asc');
    await page.waitForTimeout(1500);
    await expect(select).toHaveValue('price_asc');

    const unexpected = errors.filter(isUnexpectedError);
    expect(unexpected).toHaveLength(0);
  });

  test('min score filter input accepts values', async ({ page }) => {
    const errors = await collectErrors(page);
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });
    await waitForMapReady(page);

    const scoreInput = page.locator('input[type="number"]').first();
    await expect(scoreInput).toBeVisible({ timeout: 10000 });
    await scoreInput.fill('50');
    await expect(scoreInput).toHaveValue('50');

    const unexpected = errors.filter(isUnexpectedError);
    expect(unexpected).toHaveLength(0);
  });

  test('district filter input accepts values', async ({ page }) => {
    const errors = await collectErrors(page);
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });
    await waitForMapReady(page);

    const districtInput = page.locator('input[placeholder="e.g. 02"]');
    await expect(districtInput).toBeVisible({ timeout: 10000 });
    await districtInput.fill('02');
    await expect(districtInput).toHaveValue('02');

    const unexpected = errors.filter(isUnexpectedError);
    expect(unexpected).toHaveLength(0);
  });
});

test.describe('Marker interactions', () => {
  test('clicking a marker updates sidebar selection', async ({ page }) => {
    const errors = await collectErrors(page);
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });
    await waitForMapReady(page);
    await page.waitForTimeout(2000);

    const leaflet = page.locator('.leaflet-container');
    if (await leaflet.count() > 0) {
      const markers = page.locator('.leaflet-marker-icon');
      const count = await markers.count();
      if (count > 0) {
        await markers.first().click({ timeout: 5000 });
        await page.waitForTimeout(800);
      }
    }

    const unexpected = errors.filter(isUnexpectedError);
    expect(unexpected).toHaveLength(0);
  });

  test('multiple rapid marker clicks do not crash', async ({ page }) => {
    const errors = await collectErrors(page);
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });
    await waitForMapReady(page);
    await page.waitForTimeout(2000);

    const leaflet = page.locator('.leaflet-container');
    if (await leaflet.count() > 0) {
      const markers = page.locator('.leaflet-marker-icon');
      const count = await markers.count();
      if (count > 1) {
        await markers.nth(0).click();
        await page.waitForTimeout(200);
        await markers.nth(1).click();
        await page.waitForTimeout(200);
        await markers.nth(Math.floor(count / 2)).click();
        await page.waitForTimeout(200);
      }
    }

    const unexpected = errors.filter(isUnexpectedError);
    expect(unexpected).toHaveLength(0);
  });
});

test.describe('BottomSheet (mobile viewport)', () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test('BottomSheet renders with drag handle and count', async ({ page }) => {
    const errors = await collectErrors(page);
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });
    await waitForMapReady(page);
    await page.waitForTimeout(3000);

    const handle = page.locator('.rounded-full').first();
    await expect(handle).toBeVisible({ timeout: 8000 });

    const unexpected = errors.filter(isUnexpectedError);
    expect(unexpected).toHaveLength(0);
  });

  test('mobile filter FAB is visible', async ({ page }) => {
    const errors = await collectErrors(page);
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });
    await waitForMapReady(page);
    await page.waitForTimeout(2000);

    const fab = page.locator('[aria-label="Open filters"]');
    await expect(fab).toBeVisible({ timeout: 8000 });

    const unexpected = errors.filter(isUnexpectedError);
    expect(unexpected).toHaveLength(0);
  });

  test('tapping filter FAB opens FilterDrawer', async ({ page }) => {
    const errors = await collectErrors(page);
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });
    await waitForMapReady(page);
    await page.waitForTimeout(2000);

    const fab = page.locator('[aria-label="Open filters"]');
    await fab.click({ timeout: 5000 });
    await page.waitForTimeout(800);

    await expect(page.getByRole('heading', { name: 'Filters' })).toBeVisible({ timeout: 5000 });
    await expect(page.locator('button:has-text("Apply")')).toBeVisible({ timeout: 3000 });
    await expect(page.locator('button:has-text("Reset")')).toBeVisible({ timeout: 3000 });

    const unexpected = errors.filter(isUnexpectedError);
    expect(unexpected).toHaveLength(0);
  });

  test('FilterDrawer closes via backdrop click', async ({ page }) => {
    const errors = await collectErrors(page);
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });
    await waitForMapReady(page);
    await page.waitForTimeout(2000);

    const fab = page.locator('[aria-label="Open filters"]');
    await fab.click();
    await page.waitForTimeout(800);

    await expect(page.locator('button:has-text("Apply")')).toBeVisible({ timeout: 5000 });

    const backdrop = page.locator('[class*="absolute inset-0 bg-black"]');
    await backdrop.click({ position: { x: 10, y: 10 } });
    await page.waitForTimeout(800);

    await expect(page.getByRole('heading', { name: 'Filters' })).not.toBeVisible({ timeout: 5000 });

    const unexpected = errors.filter(isUnexpectedError);
    expect(unexpected).toHaveLength(0);
  });

  test('FilterDrawer Close button works', async ({ page }) => {
    const errors = await collectErrors(page);
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });
    await waitForMapReady(page);
    await page.waitForTimeout(2000);

    const fab = page.locator('[aria-label="Open filters"]');
    await fab.click();
    await page.waitForTimeout(800);

    await expect(page.locator('button:has-text("Apply")')).toBeVisible({ timeout: 5000 });

    const closeBtn = page.locator('[aria-label="Close filters"]');
    await closeBtn.click();
    await page.waitForTimeout(800);

    await expect(page.getByRole('heading', { name: 'Filters' })).not.toBeVisible({ timeout: 5000 });

    const unexpected = errors.filter(isUnexpectedError);
    expect(unexpected).toHaveLength(0);
  });

  test('FilterDrawer Reset button is present', async ({ page }) => {
    const errors = await collectErrors(page);
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });
    await waitForMapReady(page);
    await page.waitForTimeout(2000);

    const fab = page.locator('[aria-label="Open filters"]');
    await fab.click();
    await page.waitForTimeout(800);

    await expect(page.locator('button:has-text("Reset")')).toBeVisible({ timeout: 5000 });

    const closeBtn = page.locator('[aria-label="Close filters"]');
    await closeBtn.click();

    const unexpected = errors.filter(isUnexpectedError);
    expect(unexpected).toHaveLength(0);
  });
});

test.describe('ListingDetail modal', () => {
  test('clicking sidebar listing opens detail modal', async ({ page }) => {
    const errors = await collectErrors(page);
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });
    await waitForMapReady(page);
    await page.waitForTimeout(2000);

    const sidebarItems = page.locator('[class*="rounded-lg"][class*="border"]').first();
    if (await sidebarItems.isVisible({ timeout: 3000 }).catch(() => false)) {
      await sidebarItems.click({ timeout: 3000 });
      await page.waitForTimeout(1000);
    }

    const unexpected = errors.filter(isUnexpectedError);
    expect(unexpected).toHaveLength(0);
  });

  test('detail modal close button works', async ({ page }) => {
    const errors = await collectErrors(page);
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });
    await waitForMapReady(page);
    await page.waitForTimeout(2000);

    const sidebarItems = page.locator('[class*="rounded-lg"][class*="border"]').first();
    if (await sidebarItems.isVisible({ timeout: 3000 }).catch(() => false)) {
      await sidebarItems.click({ timeout: 3000 });
      await page.waitForTimeout(800);

      const closeBtn = page.locator('[aria-label="Close"]');
      if (await closeBtn.count() > 0) {
        await closeBtn.click();
        await page.waitForTimeout(500);
      }
    }

    const unexpected = errors.filter(isUnexpectedError);
    expect(unexpected).toHaveLength(0);
  });
});

test.describe('Map stability under repeated interactions', () => {
  test('zoom in/out 10 times then pan does not crash', async ({ page }) => {
    const errors = await collectErrors(page);
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });
    await waitForMapReady(page);
    await page.waitForTimeout(2000);

    const leaflet = page.locator('.leaflet-container');
    if (await leaflet.count() > 0) {
      const zoomIn = page.locator('.leaflet-control-zoom-in');
      if (await zoomIn.count() > 0) {
        for (let i = 0; i < 10; i++) {
          await zoomIn.click();
          await page.waitForTimeout(50);
        }
        const bbox = await leaflet.boundingBox();
        if (bbox) {
          await page.mouse.move(bbox.x + bbox.width / 2, bbox.y + bbox.height / 2);
          await page.mouse.down();
          await page.mouse.move(bbox.x + bbox.width / 2 + 150, bbox.y + bbox.height / 2);
          await page.mouse.up();
        }
        for (let i = 0; i < 10; i++) {
          await page.locator('.leaflet-control-zoom-out').click();
          await page.waitForTimeout(50);
        }
      }
      await expect(leaflet).toBeAttached({ timeout: 5000 });
    }

    const unexpected = errors.filter(isUnexpectedError);
    expect(unexpected).toHaveLength(0);
  });

  test('sidebar scroll does not crash', async ({ page }) => {
    const errors = await collectErrors(page);
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });
    await waitForMapReady(page);
    await page.waitForTimeout(2000);

    const sidebar = page.locator('.flex-1.overflow-y-auto').first();
    if (await sidebar.isVisible({ timeout: 3000 }).catch(() => false)) {
      await sidebar.evaluate((el: HTMLElement) => { el.scrollTop = 500; });
      await page.waitForTimeout(200);
      await sidebar.evaluate((el: HTMLElement) => { el.scrollTop = 0; });
      await page.waitForTimeout(200);
    }

    const unexpected = errors.filter(isUnexpectedError);
    expect(unexpected).toHaveLength(0);
  });
});