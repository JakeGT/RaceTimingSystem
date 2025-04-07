import { defineConfig, devices } from '@playwright/test';

const isWindows = process.platform === 'win32';

const webServer = {
  command: isWindows
    ? 'cd running && call venv\\Scripts\\activate && pip install -r requirements.txt && python manage.py runserver > NUL 2>&1'
    : 'cd running && . venv/bin/activate && pip install -r requirements.txt && python manage.py runserver > /dev/null 2>&1',
  url: 'http://127.0.0.1:8000',
  timeout: 120_000, // Wait up to 2 minutes for the server to start
  reuseExistingServer: !process.env.CI, // Reuse server if not in CI
};

export default defineConfig({
  testDir: './tests',
  retries: 2,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',

  use: {
    baseURL: 'http://127.0.0.1:8000',
    headless: true,
    trace: 'on-first-retry',
  },

  webServer, // Ensures server starts before tests

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
