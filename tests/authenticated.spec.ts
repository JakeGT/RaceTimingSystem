import { test, expect } from '@playwright/test';

test.describe('Authenticated User Test', () => {

  test('should allow authenticated user to access the dashboard', async ({ page }) => {
    // Step 1: Navigate to the login page
    await page.goto('http://127.0.0.1:8000/login');

    // Step 2: Fill the login form with valid credentials
    await page.fill('input#username', 'your-username'); // Replace with valid test username
    await page.fill('input#password', 'your-password'); // Replace with valid test password

    // Step 3: Submit the login form
    await page.click('button[type="submit"]');

    // Wait for the dashboard page to load after login
    await page.waitForNavigation();

    // Step 4: Verify the user is redirected to the dashboard
    await expect(page).toHaveURL('http://127.0.0.1:8000/dashboard');

    // Now that the user is logged in, you can test the dashboard page
    await expect(page.locator('h1.display-4')).toHaveText('Race Dashboard');
    // Add further tests for elements visible only to logged-in users...
  });
});
