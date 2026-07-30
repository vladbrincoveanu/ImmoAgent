import { test, expect } from '@playwright/test';

/** The map page opens an EventSource against /api/listings/stream. When the
 * deployment cannot serve change streams (a standalone mongod has no oplog) the
 * server used to just close the stream, and the client retried every 5s for as
 * long as the tab stayed open. These tests pin the connection down in both
 * directions: the server must announce the terminal condition, and the client
 * must stop asking.
 *
 * The request-count bound holds on either deployment: on a replica set the
 * single connection stays open, on a standalone it is closed once and not
 * retried. */
test.describe('SSE listings stream', () => {
  test('does not reconnect in a loop on /dashboard/map', async ({ page }) => {
    // Long by design: the assertion is "no extra connects happened over a real
    // time window", which cannot be collapsed into a web-first assertion.
    test.setTimeout(60000);

    const streamRequests: string[] = [];
    page.on('request', (req) => {
      if (req.url().includes('/api/listings/stream')) streamRequests.push(req.url());
    });

    // Not networkidle: an SSE connection is by definition never idle, so
    // waiting for it is what made this test hang rather than fail.
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });
    await expect(page.locator('.leaflet-container').first()).toBeVisible();

    // The old client retried at a fixed 5s, so a 16s window caught ~4 connects.
    // Anything above 2 means backoff/give-up is not working.
    await page.waitForTimeout(16000);

    expect(
      streamRequests.length,
      `expected at most 2 SSE connects, saw ${streamRequests.length}`
    ).toBeLessThanOrEqual(2);
  });

  test('stream endpoint responds as SSE and terminates cleanly', async ({ request }) => {
    const res = await request.get('/api/listings/stream', { timeout: 20000 });
    expect(res.status()).toBe(200);
    expect(res.headers()['content-type']).toContain('text/event-stream');

    // On a deployment without change streams the body carries the terminal
    // notice and the response completes instead of hanging open.
    const body = await res.text();
    if (body.length > 0) {
      expect(body).toMatch(/unsupported|heartbeat|new_listing/);
    }
  });

  test('map page still renders while live updates are unavailable', async ({ page }) => {
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });

    // A dead SSE connection must not take the page down with it. Scoped to the
    // desktop top bar: the page also renders a ProfileSelector inside
    // `mobile-map-fallback`, so a bare `header`-scoped locator matches two
    // elements and fails Playwright's strict mode.
    await expect(
      page.locator('[data-testid="map-top-bar"] [data-testid="profile-selector"]')
    ).toBeVisible();
    await expect(page.locator('.leaflet-container').first()).toBeVisible();
  });
});
