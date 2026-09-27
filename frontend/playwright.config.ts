import { defineConfig, devices } from '@playwright/test';

// Its own port, so the suite never fights the compose stack on :3000 — and
// never runs against a dev server, where Next compiles each route on first
// visit and a sign-in can take minutes.
const PORT = process.env.E2E_PORT ?? '3100';
const BASE_URL = process.env.E2E_BASE_URL ?? `http://localhost:${PORT}`;

export default defineConfig({
  testDir: './e2e',
  // The suite drives a real stack (Django + Postgres + Redis) and shares one
  // seeded company, so tests run in order rather than in parallel.
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  // Generous because the suite drives a real Django + Postgres + Redis stack,
  // and password hashing is deliberately expensive.
  timeout: 120_000,
  expect: { timeout: 30_000 },
  reporter: process.env.CI ? [['github'], ['list']] : [['list']],
  use: {
    baseURL: BASE_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    locale: 'ar-EG',
  },
  // Builds and serves the app itself unless E2E_BASE_URL points elsewhere.
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        command: `npm run build && npx next start -p ${PORT}`,
        url: `http://localhost:${PORT}/ar/login`,
        reuseExistingServer: !process.env.CI,
        timeout: 15 * 60_000,
        stdout: 'ignore',
        stderr: 'pipe',
      },

  projects: [
    // Signs in once per role and stores the cookies for everything else.
    { name: 'setup', testMatch: /auth\.setup\.ts/ },
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
      dependencies: ['setup'],
    },
  ],
});
