import { test, expect } from '@playwright/test';

test.describe('Landing Page Tests', () => {
    test.beforeEach(async ({ page }) => {
        // Navigate to the landing page
        await page.goto('http://127.0.0.1:8000');
    });

    test('should have the correct title', async ({ page }) => {
        await expect(page).toHaveTitle('Welcome to Race Timing System');
    });

    test('should display the hero section correctly', async ({ page }) => {
        const heroHeading = page.locator('h1.display-3');
        const heroText = page.locator('p.lead');

        await expect(heroHeading).toBeVisible();
        await expect(heroHeading).toHaveText('Automatic Race Timing');
        await expect(heroText).toHaveText('Computer vision model for automatic Race Timing');
    });

    test('should have a working dashboard button', async ({ page }) => {
        const dashboardButton = page.locator('a.btn-primary:has-text("Go to Dashboard")');
        await expect(dashboardButton).toBeVisible();
        await expect(dashboardButton).toHaveAttribute('href', '/dashboard/');
    });

    test('should display feature cards correctly', async ({ page }) => {
        const featureTitles = await page.locator('.card-title').allTextContents();
        expect(featureTitles).toEqual([
            'Live Race Tracking',
            'Participant Management',
            'Advanced Filters'
        ]);
    });

    test('should show Sign Up and Log In buttons if not authenticated', async ({ page }) => {
        const signUpButton = page.locator('a.btn-success:has-text("Sign Up")');
        const loginButton = page.locator('a.btn-outline-primary:has-text("Log In")');

        await expect(signUpButton).toBeVisible();
        await expect(signUpButton).toHaveAttribute('href', '/register/');

        await expect(loginButton).toBeVisible();
        await expect(loginButton).toHaveAttribute('href', '/login/');
    });

    test('navbar should have dashboard and login/logout button', async ({ page }) => {
        const dashboardNav = page.locator('nav a:has-text("Dashboard")');
        const loginNav = page.locator('nav a:has-text("Login")');

        await expect(dashboardNav).toBeVisible();
        await expect(dashboardNav).toHaveAttribute('href', '/dashboard/');

        await expect(loginNav).toBeVisible();
        await expect(loginNav).toHaveAttribute('href', '/login/');
    });

    // Check if hamburger menu is visible and click it if necessary
    test('should open the hamburger menu if the three lines are visible', async ({ page }) => {
        const hamburgerMenu = page.locator('.navbar-toggler'); // Hamburger menu
        const navbarItems = page.locator('nav .navbar-nav');

        // Check if the hamburger menu (three lines icon) is visible
        const isHamburgerVisible = await hamburgerMenu.isVisible();

        if (isHamburgerVisible) {
            // Click the hamburger menu to reveal the navbar items
            await hamburgerMenu.click();
        }

        // Now check if the navbar items are visible
        await expect(navbarItems).toBeVisible();

        // Verify that Dashboard button and Login button are in the navbar
        const dashboardNav = page.locator('nav a:has-text("Dashboard")');
        const loginNav = page.locator('nav a:has-text("Login")');

        await expect(dashboardNav).toBeVisible();
        await expect(dashboardNav).toHaveAttribute('href', '/dashboard/');

        await expect(loginNav).toBeVisible();
        await expect(loginNav).toHaveAttribute('href', '/login/');
    });
});
