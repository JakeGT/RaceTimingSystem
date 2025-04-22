import { test, expect } from '@playwright/test';

test.describe('Registration Page', () => {
  test('should display the registration form and submit successfully with valid data', async ({ page }) => {
    // Navigate to the registration page
    await page.goto('http://127.0.0.1:8000/register');

    // Check if the registration form is visible
    await expect(page.locator('form')).toBeVisible();
    await expect(page.locator('input#username')).toBeVisible();
    await expect(page.locator('input#email')).toBeVisible();
    await expect(page.locator('input#password1')).toBeVisible();
    await expect(page.locator('input#password2')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();

    // Fill in the form with valid data
    await page.fill('input#username', 'newuser');
    await page.fill('input#email', 'newuser@example.com');
    await page.fill('input#password1', 'validpassword');
    await page.fill('input#password2', 'validpassword');

    // Submit the form
    await page.click('button[type="submit"]');

    // Wait for navigation after successful registration
    await page.waitForNavigation();

    // Verify that the user is redirected to a login or confirmation page
    await expect(page.locator('a[href="/login"]')).toBeVisible();
  });

  test('should display error messages for invalid form inputs', async ({ page }) => {
    // Navigate to the registration page
    await page.goto('http://127.0.0.1:8000/register');

    // Fill in the form with invalid data
    await page.fill('input#username', '');  // Leave username blank
    await page.fill('input#email', 'invalid-email'); // Invalid email
    await page.fill('input#password1', 'short'); // Password too short
    await page.fill('input#password2', 'different'); // Passwords don't match

    // Submit the form
    await page.click('button[type="submit"]');

    // Wait for the form error messages to appear
    await expect(page.locator('.alert-danger')).toBeVisible();

    // Check for specific form validation errors
    await expect(page.locator('.invalid-feedback')).toHaveText(/This field is required/);
    await expect(page.locator('input#email')).toHaveClass(/is-invalid/);
    await expect(page.locator('input#password1')).toHaveClass(/is-invalid/);
    await expect(page.locator('input#password2')).toHaveClass(/is-invalid/);
  });

  test('should show success message when valid form is submitted', async ({ page }) => {
    // Navigate to the registration page
    await page.goto('http://127.0.0.1:8000/register');

    // Fill in the form with valid data
    await page.fill('input#username', 'validuser');
    await page.fill('input#email', 'validuser@example.com');
    await page.fill('input#password1', 'ValidPassword123');
    await page.fill('input#password2', 'ValidPassword123');

    // Submit the form
    await page.click('button[type="submit"]');

    // Wait for navigation or for a success message to be shown
    await page.waitForNavigation();

    // Check for success message (Assuming a success message appears upon successful registration)
    await expect(page.locator('.alert.alert-success')).toBeVisible();
  });
});
