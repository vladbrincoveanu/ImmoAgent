import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: 'list',

  use: {
    baseURL: 'http://localhost:3010',
    trace: 'on-first-retry',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  // Run the suite against a production build, not `next dev`.
  // react-leaflet v4 double-initialises the Leaflet map under React StrictMode's
  // dev-only double-invoke of layout effects ("Map container is already
  // initialized"), which crashes /dashboard/map and takes the whole React tree
  // down with it. Production builds do not double-invoke, so the map renders
  // correctly there — testing the prod build exercises what users actually get.
  webServer: {
    command:
      'npm run build && PORT=3010 MONGODB_URI=mongodb://localhost:27017/immo npm run start',
    port: 3010,
    reuseExistingServer: true,
    timeout: 300000,
  },
});
