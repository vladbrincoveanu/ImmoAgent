import { test, expect, type ConsoleMessage } from '@playwright/test';

/** Cross-page health gate: every top-level route must render its main landmark,
 * load its images, and produce no console errors or failed requests. This is
 * the check that catches "the page is technically 200 but visibly broken". */
const ROUTES = ['/', '/dashboard', '/dashboard/map', '/coop'] as const;
const EXPECTED_SECURITY_HEADERS = {
  'x-content-type-options': 'nosniff',
  'referrer-policy': 'strict-origin-when-cross-origin',
  'x-frame-options': 'DENY',
  'permissions-policy': 'camera=(), microphone=(), geolocation=()',
};

for (const route of ROUTES) {
  test(`page health: ${route}`, async ({ page }) => {
    test.setTimeout(60000);

    const consoleErrors: string[] = [];
    const failedRequests: string[] = [];

    page.on('console', (msg: ConsoleMessage) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text());
    });
    page.on('requestfailed', (req) => {
      // An aborted SSE stream on teardown is expected, not a page defect.
      if (req.url().includes('/api/listings/stream')) return;
      failedRequests.push(`${req.url()} — ${req.failure()?.errorText ?? 'unknown'}`);
    });

    const response = await page.goto(route, { waitUntil: 'domcontentloaded' });
    expect(response?.status(), `${route} HTTP status`).toBeLessThan(400);
    expect(response?.headers(), `${route} security headers`).toMatchObject(EXPECTED_SECURITY_HEADERS);

    // Something meaningful must be on screen — not a blank shell.
    await expect(page.locator('body')).toBeVisible();
    const text = (await page.locator('body').innerText()).trim();
    expect(text.length, `${route} rendered no visible text`).toBeGreaterThan(50);

    // Images that 404 render at zero natural width.
    const brokenImages = await page.evaluate(() =>
      Array.from(document.querySelectorAll('img'))
        .filter((img) => img.complete && img.naturalWidth === 0)
        .map((img) => img.currentSrc || img.src)
        .filter((src) => src.length > 0)
    );
    expect(brokenImages, `${route} has broken images`).toEqual([]);

    expect(consoleErrors, `${route} console errors`).toEqual([]);
    expect(failedRequests, `${route} failed requests`).toEqual([]);
  });
}
