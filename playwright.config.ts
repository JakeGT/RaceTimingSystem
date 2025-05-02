import { defineConfig, devices } from '@playwright/test';

const isWindows = process.platform === 'win32';

const webServer = {
  command: isWindows
    ? 'cd running && call venv\\Scripts\\activate && pip install -r requirements.txt && python manage.py runserver'
    : 'cd running && . venv/bin/activate && pip install -r requirements.txt && python manage.py runserver',
  url: 'http://127.0.0.1:8000',
  timeout: 120_000, // 2 minutes
  reuseExistingServer: !process.env.CI,
};

export default defineConfig({
  testDir: './tests',
  retries: process.env.CI ? 2 : 0,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  workers: process.env.CI ? 1 : undefined,
  reporter: [['html'], ['list']],

  use: {
    baseURL: 'http://127.0.0.1:8000',
    headless: true,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },

  webServer,

  projects: [
    // Desktop Browsers
    {
      name: 'Desktop Chrome',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'Desktop Firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'Desktop Safari',
      use: { ...devices['Desktop Safari'] },
    },

    // Mobile Emulation
    {
      name: 'Mobile Chrome',
      use: { ...devices['Pixel 5'] },
    },
    {
      name: 'Mobile Safari',
      use: { ...devices['iPhone 12'] },
    },
  ],
});

