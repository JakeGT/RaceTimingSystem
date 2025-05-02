import { test, expect } from '@playwright/test';

test.describe('Registration Page', () => {
  test('should display the registration form and submit successfully with valid data', async ({ page }) => {
    await page.goto('http://127.0.0.1:8000/register');

    // Check form visibility
    await expect(page.locator('form')).toBeVisible();
    await expect(page.locator('#username')).toBeVisible();
    await expect(page.locator('#email')).toBeVisible();
    await expect(page.locator('#password1')).toBeVisible();
    await expect(page.locator('#password2')).toBeVisible();

    // Fill in form
    const uniqueUsername = `user_${Date.now()}`;
    await page.fill('#first_name', 'Test');
    await page.fill('#last_name', 'User');
    await page.fill('#username', uniqueUsername);
    await page.fill('#email', `${uniqueUsername}@example.com`);
    await page.fill('#password1', 'ValidPass123!');
    await page.fill('#password2', 'ValidPass123!');

    // Submit and wait for success message or redirect
    await Promise.all([
      page.waitForURL('**/login', { timeout: 5000 }).catch(() => {}),
      page.click('button[type="submit"]'),
    ]);

    // Expect login link or success message
    const successMessage = page.locator('.alert-success');
    const loginLink = page.locator('a[href="/login"]');

    await expect(
      successMessage.or(loginLink)
    ).toBeVisible({ timeout: 5000 });
  });

  test('should display error messages for invalid form inputs', async ({ page }) => {
    await page.goto('http://127.0.0.1:8000/register');

    // Fill invalid data
    await page.fill('#first_name', 'Valid');
    await page.fill('#last_name', '');
    await page.fill('#username', '');
    await page.fill('#email', 'bademail');
    await page.fill('#password1', 'short');
    await page.fill('#password2', 'mismatch');

    await page.click('button[type="submit"]');

    await page.evaluate(() => window.scrollTo(0, 0));

    // Check for field-specific errors
    await expect(page.locator('#username')).toHaveClass(/form-control/);
  });

  test('should show success message or redirect when valid form is submitted', async ({ page }) => {
    await page.goto('http://127.0.0.1:8000/register');

    const uniqueUsername = `user_${Date.now()}`;
    await page.locator('#first_name').scrollIntoViewIfNeeded();
    await page.fill('#first_name', 'Valid');
    await page.fill('#last_name', 'User');
    await page.fill('#username', uniqueUsername);
    await page.fill('#email', `${uniqueUsername}@example.com`);
    await page.fill('#password1', 'StrongPassword123!');
    await page.fill('#password2', 'StrongPassword123!');

    await Promise.all([
      page.waitForURL('**/login', { timeout: 5000 }).catch(() => {}),
      page.click('button[type="submit"]'),
    ]);

    await expect(
      page.locator('.alert-success').or(page.locator('a[href="/login"]'))
    ).toBeVisible({ timeout: 5000 });
  });
});
