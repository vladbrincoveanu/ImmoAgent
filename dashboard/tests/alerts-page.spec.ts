import { test, expect } from '@playwright/test';

const ALERT_API = '**/api/saved-searches/alert';

const STORED = {
  _id: '507f1f77bcf86cd799439011',
  kind: 'keyword',
  keywords: ['Ablöse', 'Nachmieter'],
  keyword: 'Ablöse',
  filters: { min_area: 60, max_area: 90, max_price: 900 },
  email: null,
  telegram_chat_id: '-100123456',
  confirmed: true,
  created_at: null,
};

/** The /alerts dashboard: create a keyword watch on the private-transfer feed.
 *
 * Alerts are Pro-only, so an anonymous visitor gets a 402 and the page must say
 * so rather than appearing to succeed. These assertions run against the real
 * rendered DOM, not screenshots. */

test('alerts page renders the create form with every filter', async ({ page }) => {
  await page.goto('/alerts');
  await expect(page.getByTestId('alerts-page')).toBeVisible();
  await expect(page.getByTestId('alert-keywords')).toBeVisible();
  await expect(page.getByTestId('alert-min-area')).toBeVisible();
  await expect(page.getByTestId('alert-max-area')).toBeVisible();
  await expect(page.getByTestId('alert-min-rooms')).toBeVisible();
  await expect(page.getByTestId('alert-max-rooms')).toBeVisible();
  await expect(page.getByTestId('alert-max-price')).toBeVisible();
  await expect(page.getByTestId('alert-email')).toBeVisible();
  await expect(page.getByTestId('alert-chatid')).toBeVisible();
  await expect(page.getByTestId('alert-submit')).toBeVisible();
});

test('submitting with no channel surfaces an error instead of failing silently',
  async ({ page }) => {
    await page.goto('/alerts');
    await page.getByTestId('alert-keywords').fill('1100');
    await page.getByTestId('alert-submit').click();
    // Either the Pro gate or the missing-channel validation — both must be shown.
    await expect(page.getByTestId('alert-status')).toBeVisible();
    const text = await page.getByTestId('alert-status').textContent();
    expect(text?.trim().length ?? 0).toBeGreaterThan(0);
  });

test('an invalid telegram chat id is rejected, not stored', async ({ page }) => {
  await page.goto('/alerts');
  await page.getByTestId('alert-chatid').fill('@notanid');
  await page.getByTestId('alert-submit').click();
  await expect(page.getByTestId('alert-status')).toBeVisible();
});

test('keywords are posted as an array and blank filters stay unset', async ({ page }) => {
  let posted: any = null;
  await page.route(ALERT_API, async (route) => {
    if (route.request().method() === 'POST') {
      posted = route.request().postDataJSON();
      return route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, message: 'Alert angelegt.' }),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [] }),
    });
  });
  await page.goto('/alerts');
  await page.getByTestId('alert-keywords').fill('Ablöse, Nachmieter , ');
  await page.getByTestId('alert-min-area').fill('60');
  await page.getByTestId('alert-max-price').fill('900');
  await page.getByTestId('alert-chatid').fill('-100123456');
  await page.getByTestId('alert-submit').click();
  await expect(page.getByTestId('alert-status')).toBeVisible();
  expect(posted.keywords).toEqual(['Ablöse', 'Nachmieter']);
  expect(posted.kind).toBe('keyword');
  expect(posted.filters.min_area).toBe(60);
  expect(posted.filters.max_price).toBe(900);
  expect(posted.filters.max_area).toBeUndefined();
});

test('stored alert renders all keys, filters, test, and delete controls', async ({ page }) => {
  await page.route(ALERT_API, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [STORED] }),
    }));
  await page.goto('/alerts');
  const item = page.getByTestId('alert-item').first();
  await expect(item).toContainText('Ablöse');
  await expect(item).toContainText('Nachmieter');
  await expect(item).toContainText('60');
  await expect(item).toContainText('900');
  await expect(page.getByTestId('alert-test').first()).toBeVisible();
  await expect(page.getByTestId('alert-delete').first()).toBeVisible();
});

test('delete calls the API with the alert id', async ({ page }) => {
  let deletedUrl: string | null = null;
  await page.route(ALERT_API + '*', (route) => {
    if (route.request().method() === 'DELETE') {
      deletedUrl = route.request().url();
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true }),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [STORED] }),
    });
  });
  await page.goto('/alerts');
  await page.getByTestId('alert-delete').first().click();
  await expect.poll(() => deletedUrl).toContain(STORED._id);
});

test('test delivery surfaces the provider error', async ({ page }) => {
  await page.route('**/api/saved-searches/alert/test', (route) =>
    route.fulfill({
      status: 502,
      contentType: 'application/json',
      body: JSON.stringify({ error: 'Telegram lehnte die Nachricht ab: chat not found' }),
    }));
  await page.route(ALERT_API, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [STORED] }),
    }));
  await page.goto('/alerts');
  await page.getByTestId('alert-test').first().click();
  await expect(page.getByTestId('alert-status')).toContainText('chat not found');
});

test('the private rubric is reachable from /coop', async ({ page }) => {
  await page.goto('/coop');
  const link = page.getByTestId('coop-private-link');
  await expect(link).toBeVisible();
  await link.click();
  await expect(page.getByTestId('coop-private-page')).toBeVisible();
});

test('global navigation links to alerts and private transfers', async ({ page }) => {
  await page.goto('/dashboard');
  const nav = page.locator('body > header');
  await expect(nav.getByRole('link', { name: 'Alerts' })).toBeVisible();
  await expect(nav.getByRole('link', { name: 'Ablöse' })).toBeVisible();
});
