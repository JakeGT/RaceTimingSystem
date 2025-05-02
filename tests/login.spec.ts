import { test, expect } from '@playwright/test';

test.describe('Login Page', () => {
  test('should display the login form and submit successfully', async ({ page }) => {
    // Navigate to the login page
    await page.goto('http://127.0.0.1:8000/login');

    // Check if the login form is present
    await expect(page.locator('form')).toBeVisible();
    await expect(page.locator('input#username')).toBeVisible();
    await expect(page.locator('input#password')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();

    // Fill in the form with valid username and password
    await page.fill('input#username', 'test');
    await page.fill('input#password', 'Password123$');

    await Promise.all([
      page.waitForNavigation(), // waits for a full page navigation
      page.click('button[type="submit"]'),
    ]);

    // Verify that login is successful (e.g., check for the presence of a dashboard link or other element)
    // For example, checking that a dashboard button appears (you can adjust the selector based on your app's structure)
    await expect(page.locator('a[href="/"]')).toBeVisible();
  });

  test('should display error message for invalid login', async ({ page }) => {
    // Navigate to the login page
    await page.goto('http://127.0.0.1:8000/login');

    // Fill in the form with invalid username and password
    await page.fill('input#username', 'wrong-username');
    await page.fill('input#password', 'wrong-password');

    // Submit the form
    await page.click('button[type="submit"]');

    // Wait for the page to reload and show error message
    const errorMessage = page.locator('.alert.alert-error');
    await expect(errorMessage).toBeVisible();
    await expect(errorMessage).toContainText('Invalid username or password');  // Adjust this based on your error message
  });
});
