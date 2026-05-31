# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: smoke.spec.ts >> Dashboard Smoke Tests >> root page redirects to /dashboard
- Location: tests/smoke.spec.ts:16:7

# Error details

```
Test timeout of 30000ms exceeded while running "beforeEach" hook.
```

```
Error: page.fill: Test timeout of 30000ms exceeded.
Call log:
  - waiting for locator('input[id="username"]')

```

# Page snapshot

```yaml
- generic [ref=e4]:
  - navigation [ref=e5]:
    - generic [ref=e8]:
      - img [ref=e9]
      - generic [ref=e20]: knowledgeforge
    - list [ref=e21]:
      - listitem [ref=e22]:
        - link "Workspace" [ref=e23] [cursor=pointer]:
          - /url: /workspace
          - img [ref=e24]
          - generic [ref=e27]: Workspace
      - listitem [ref=e28]:
        - link "Code Architecture" [ref=e29] [cursor=pointer]:
          - /url: /code-architecture
          - img [ref=e30]
          - generic [ref=e33]: Code Architecture
      - listitem [ref=e34]:
        - link "System Metrics" [ref=e35] [cursor=pointer]:
          - /url: /metrics
          - img [ref=e36]
          - generic [ref=e38]: System Metrics
      - listitem [ref=e39]:
        - link "Settings" [ref=e40] [cursor=pointer]:
          - /url: /settings
          - img [ref=e41]
          - generic [ref=e44]: Settings
      - listitem [ref=e45]:
        - link "Review Queue" [ref=e46] [cursor=pointer]:
          - /url: /review
          - img [ref=e47]
          - generic [ref=e49]: Review Queue
  - main [ref=e50]
```

# Test source

```ts
  1  | import { test, expect, type Page } from '@playwright/test';
  2  | 
  3  | async function login(page: Page) {
  4  |   await page.goto('/login');
> 5  |   await page.fill('input[id="username"]', 'test');
     |              ^ Error: page.fill: Test timeout of 30000ms exceeded.
  6  |   await page.fill('input[id="password"]', 'test123');
  7  |   await page.click('button[type="submit"]');
  8  |   await page.waitForURL(/\/dashboard/, { timeout: 10000 });
  9  | }
  10 | 
  11 | test.describe('Dashboard Smoke Tests', () => {
  12 |   test.beforeEach(async ({ page }) => {
  13 |     await login(page);
  14 |   });
  15 | 
  16 |   test('root page redirects to /dashboard', async ({ page }) => {
  17 |     const serverErrors: string[] = [];
  18 |     page.on('response', response => {
  19 |       if (response.status() >= 500 && response.status() !== 503) {
  20 |         serverErrors.push(`${response.status()} ${response.url()}`);
  21 |       }
  22 |     });
  23 | 
  24 |     await page.goto('/');
  25 |     await page.waitForURL(/\/dashboard/);
  26 | 
  27 |     expect(serverErrors.length).toBe(0);
  28 |   });
  29 | 
  30 |   test('dashboard listing page renders header and filter bar', async ({ page }) => {
  31 |     const serverErrors: string[] = [];
  32 |     page.on('response', response => {
  33 |       if (response.status() >= 500 && response.status() !== 503) {
  34 |         serverErrors.push(`${response.status()} ${response.url()}`);
  35 |       }
  36 |     });
  37 | 
  38 |     await page.goto('/dashboard');
  39 |     await page.waitForLoadState('networkidle');
  40 | 
  41 |     await expect(page.locator('h1')).toContainText('Top Property Picks');
  42 |     await expect(page.locator('input[type="number"]').first()).toBeVisible();
  43 | 
  44 |     expect(serverErrors.length).toBe(0);
  45 |   });
  46 | 
  47 |   test('dashboard map page renders header', async ({ page }) => {
  48 |     const serverErrors: string[] = [];
  49 |     page.on('response', response => {
  50 |       if (response.status() >= 500 && response.status() !== 503) {
  51 |         serverErrors.push(`${response.status()} ${response.url()}`);
  52 |       }
  53 |     });
  54 | 
  55 |     await page.goto('/dashboard/map');
  56 |     await page.waitForLoadState('networkidle');
  57 |     await expect(page.locator('h1')).toContainText('Property Map');
  58 | 
  59 |     const mapVisible = await page.locator('.leaflet-container').isVisible().catch(() => false);
  60 |     if (!mapVisible) {
  61 |       await expect(page.locator('text=No listings match your filters').first()).toBeVisible({ timeout: 10000 });
  62 |     }
  63 | 
  64 |     expect(serverErrors.length).toBe(0);
  65 |   });
  66 | 
  67 |   test('dashboard listing page is not stuck in loading state', async ({ page }) => {
  68 |     await page.goto('/dashboard');
  69 |     await page.waitForLoadState('networkidle');
  70 | 
  71 |     await expect(page.locator('text=Loading...')).toHaveCount(0, { timeout: 15000 });
  72 |   });
  73 | 
  74 |   test('dashboard map page is not stuck in loading state', async ({ page }) => {
  75 |     await page.goto('/dashboard/map');
  76 |     await page.waitForLoadState('networkidle');
  77 | 
  78 |     await expect(page.locator('text=Loading...')).toHaveCount(0, { timeout: 15000 });
  79 |   });
  80 | });
  81 | 
```