import { test, expect } from '@playwright/test';

test.describe('Race Dashboard Page', () => {

  test.beforeEach(async ({ page }) => {
    // Go to the dashboard page
    await page.goto('/dashboard/');
  });

  test('should load dashboard and display header', async ({ page }) => {
    await expect(page.locator('h1')).toHaveText('Race Dashboard');
    await expect(page.locator('text=Search for races and view their leaderboards')).toBeVisible();
  });

  test('should have working race search input with debounce', async ({ page }) => {
    const input = page.locator('#race-search');
    await input.fill('Race');
    await expect(input).toHaveValue('Race');

    // Wait for debounce to trigger (1 second)
    await page.waitForTimeout(1100);

    // Check if URL updated with query parameter (form auto-submitted)
    await expect(page).toHaveURL(/.*race_search=Race.*/);
  });

  test('should toggle completed and upcoming checkboxes exclusively', async ({ page }) => {
    const completed = page.locator('#completed');
    const upcoming = page.locator('#upcoming');

    // Check completed, ensure upcoming is not checked
    await completed.check();
    await expect(upcoming).not.toBeChecked();

    // Check upcoming, completed should now be unchecked
    await upcoming.check();
    await expect(completed).not.toBeChecked();
  });


  test('should display the Leaflet map', async ({ page }) => {
    const map = page.locator('#map');
    await expect(map).toBeVisible();
    await expect(map).toHaveAttribute('style', /height: 500px/);
  });

});
