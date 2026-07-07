import { defineConfig, devices } from '@playwright/test';

// Verification-only config: points at the deployed production build
// (https://immo-agent-vienna.vercel.app) so tests run against real data,
// not the empty local Mongo used by the default config.
// Invoke with:  npx playwright test --config=playwright.prod.config.ts
export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: 'list',

  use: {
    baseURL: 'https://immo-agent-vienna.vercel.app',
    trace: 'on-first-retry',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
