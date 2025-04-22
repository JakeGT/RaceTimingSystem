import { test, expect } from '@playwright/test';

test.describe('Race Dashboard Page', () => {
  test('should display race dashboard for logged-in users', async ({ page }) => {
    // Assuming you are logged in, navigate to the dashboard
    await page.goto('http://127.0.0.1:8000/dashboard');

    // Check if the page title is correct
    await expect(page.locator('h1.display-4')).toHaveText('Race Dashboard');

    // Check if the authenticated user links are displayed
    await expect(page.locator('a[href="/race_history"]')).toBeVisible();
    await expect(page.locator('a[href="/race_organiser_dashboard"]')).toBeVisible();
    await expect(page.locator('a[href="/register_for_race"]')).toBeVisible();
    await expect(page.locator('a[href="/upcoming_races"]')).toBeVisible();
    await expect(page.locator('a[href="/race_config"]')).toBeVisible();

    // Verify the search input is present
    await expect(page.locator('input#race-search')).toBeVisible();
    await expect(page.locator('input#completed')).toBeVisible();
  });

  test('should show no races found message if there are no races', async ({ page }) => {
    // Navigate to the dashboard page
    await page.goto('http://127.0.0.1:8000/dashboard');

    // Check for the "No races found" message
    await expect(page.locator('p')).toHaveText('No races found. Please add a race.');
  });

  test('should allow user to search for a race', async ({ page }) => {
    // Navigate to the dashboard page
    await page.goto('http://127.0.0.1:8000/dashboard');

    // Fill in the search field with a race name
    await page.fill('input#race-search', 'Marathon');

    // Click on the search button
    await page.click('button[type="submit"]');

    // Wait for the search results to be displayed
    await expect(page.locator('.list-group')).toBeVisible();

    // Verify that the search term is reflected in the results
    await expect(page.locator('.list-group-item')).toHaveText('Marathon');
  });

  test('should filter races based on completion status', async ({ page }) => {
    // Navigate to the dashboard page
    await page.goto('http://127.0.0.1:8000/dashboard');

    // Check that the checkbox is visible and not checked initially
    const checkbox = page.locator('input#completed');
    await expect(checkbox).toBeVisible();
    await expect(checkbox).not.toBeChecked();

    // Click to check the "Show Completed Races Only" checkbox
    await checkbox.click();

    // Submit the form to apply the filter
    await page.click('button[type="submit"]');

    // Verify that the filter is applied, you may want to check if the races shown are completed
    // This step assumes you have a way to know if races are completed
    await expect(page.locator('.list-group')).toBeVisible();
    // Add any additional assertions related to filtering, e.g., check if completed races are listed
  });

  test('should navigate to the race detail page when a race is selected', async ({ page }) => {
    // Navigate to the dashboard page
    await page.goto('http://127.0.0.1:8000/dashboard');

    // Assume there are races displayed in the list
    await expect(page.locator('.list-group-item')).toBeVisible();

    // Click on a race to navigate to the race detail page
    const firstRaceLink = page.locator('.list-group-item');
    await firstRaceLink.click();

    // Wait for the navigation to the race detail page
    await page.waitForNavigation();

    // Check if the URL is the race detail page, assuming the URL structure is like /race/<id>
    await expect(page.url()).toMatch(/\/race\/\d+/);
  });
});
