import { test, expect } from '@playwright/test';

/** Password unlock for the Pro gate on /alerts.
 *
 * The point of these tests is that the password is worth something: the box
 * only appears for a non-Pro user, the secret leaves the browser to be checked
 * server-side, a wrong one changes nothing, and an unconfigured deployment
 * fails closed instead of open. */

const ME_API = '**/api/me';
const UNLOCK_API = '**/api/unlock';
const ALERT_API = '**/api/saved-searches/alert';

/** Keep the alert list quiet so these tests only exercise the gate. */
async function stubAlerts(page: import('@playwright/test').Page) {
  await page.route(ALERT_API, (route) =>
    route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ items: [] }),
    }));
}

async function stubMe(page: import('@playwright/test').Page, isPro: boolean) {
  await page.route(ME_API, (route) =>
    route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ is_pro: isPro, saved_search_count: 0 }),
    }));
}

test('a free user gets the unlock box', async ({ page }) => {
  await stubAlerts(page);
  await stubMe(page, false);
  await page.goto('/alerts');
  await expect(page.getByTestId('unlock-form')).toBeVisible();
  await expect(page.getByTestId('unlock-password')).toBeVisible();
});

test('a pro user never sees the unlock box', async ({ page }) => {
  await stubAlerts(page);
  await stubMe(page, true);
  await page.goto('/alerts');
  await expect(page.getByTestId('alerts-page')).toBeVisible();
  await expect(page.getByTestId('unlock-form')).toHaveCount(0);
});

test('the password is posted to the server, not compared in the browser',
  async ({ page }) => {
    await stubAlerts(page);
    await stubMe(page, false);
    let posted: { password?: string } | null = null;
    await page.route(UNLOCK_API, (route) => {
      posted = route.request().postDataJSON();
      return route.fulfill({
        status: 200, contentType: 'application/json',
        body: JSON.stringify({ ok: true, is_pro: true }),
      });
    });

    await page.goto('/alerts');
    await page.getByTestId('unlock-password').fill('open-sesame-1234');
    await page.getByTestId('unlock-submit').click();

    await expect.poll(() => posted?.password).toBe('open-sesame-1234');
    // Entitlement came back true, so the box is gone and the form is usable.
    await expect(page.getByTestId('unlock-form')).toHaveCount(0);
    await expect(page.getByTestId('alert-status')).toContainText('Freigeschaltet');
  });

test('a wrong password leaves the gate shut', async ({ page }) => {
  await stubAlerts(page);
  await stubMe(page, false);
  await page.route(UNLOCK_API, (route) =>
    route.fulfill({
      status: 401, contentType: 'application/json',
      body: JSON.stringify({ error: 'invalid_password' }),
    }));

  await page.goto('/alerts');
  await page.getByTestId('unlock-password').fill('wrong');
  await page.getByTestId('unlock-submit').click();

  await expect(page.getByTestId('alert-status')).toContainText('Falsches Passwort');
  await expect(page.getByTestId('unlock-form')).toBeVisible();
});

test('repeated guessing is throttled and says so', async ({ page }) => {
  await stubAlerts(page);
  await stubMe(page, false);
  await page.route(UNLOCK_API, (route) =>
    route.fulfill({
      status: 429, contentType: 'application/json',
      body: JSON.stringify({ error: 'too_many_attempts' }),
    }));

  await page.goto('/alerts');
  await page.getByTestId('unlock-password').fill('guess');
  await page.getByTestId('unlock-submit').click();

  await expect(page.getByTestId('alert-status')).toContainText('Zu viele Versuche');
});

test('a deployment with no password configured fails closed', async ({ page }) => {
  await stubAlerts(page);
  await stubMe(page, false);
  await page.route(UNLOCK_API, (route) =>
    route.fulfill({
      status: 503, contentType: 'application/json',
      body: JSON.stringify({ error: 'unlock_not_configured' }),
    }));

  await page.goto('/alerts');
  await page.getByTestId('unlock-password').fill('anything');
  await page.getByTestId('unlock-submit').click();

  await expect(page.getByTestId('alert-status')).toContainText('PRO_UNLOCK_PASSWORD');
  await expect(page.getByTestId('unlock-form')).toBeVisible();
});

/** Hits the real route. The test server runs without PRO_UNLOCK_PASSWORD, so
 * the correct behaviour is a refusal — an unset secret must never mean
 * "everyone is Pro". */
test('the real unlock endpoint refuses when unconfigured', async ({ request }) => {
  const res = await request.post('/api/unlock', {
    data: { password: 'whatever' },
  });
  expect(res.ok()).toBeFalsy();
  expect([401, 503]).toContain(res.status());
});

/** A 402 from the create call reveals the unlock box, so a cookie that lost its
 * entitlement is not a dead end. */
test('a 402 on create reveals the unlock box', async ({ page }) => {
  await stubMe(page, true);
  await page.route(ALERT_API, (route) => {
    if (route.request().method() === 'POST') {
      return route.fulfill({
        status: 402, contentType: 'application/json',
        body: JSON.stringify({ error: 'upgrade_required' }),
      });
    }
    return route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ items: [] }),
    });
  });

  await page.goto('/alerts');
  await expect(page.getByTestId('unlock-form')).toHaveCount(0);
  await page.getByTestId('alert-chatid').fill('-100123456');
  await page.getByTestId('alert-submit').click();
  await expect(page.getByTestId('unlock-form')).toBeVisible();
});
