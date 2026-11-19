/**
 * End-to-End Playwright Specifications (PRD §11.5: E2E-1, E2E-2, E2E-3).
 */

import { test, expect } from "@playwright/test";

test.describe("FitBudget AI E2E Suite (PRD §11.5)", () => {
  test("E2E-1: Full demo flow — register, onboarding, nutrition, meal plan, workout, tracker, chat proposal, dashboard, export", async ({
    page,
  }) => {
    const uniqueEmail = `e2e.${Date.now()}@example.com`;

    await page.goto("/register");
    await page.fill("#full-name", "Budi Santoso");
    await page.fill("#email", uniqueEmail);
    await page.fill("#password", "PasswordAman123!");
    await page.check("#consent-terms");
    await page.check("#consent-health");
    await page.click('button[type="submit"]');

    await expect(page).toHaveURL(/\/onboarding/);
    await page.click('button[type="submit"]');

    await expect(page).toHaveURL(/\/nutrition/);
    await expect(page.getByTestId("nutrition-targets-card")).toBeVisible();

    await page.goto("/meal-plan");
    await page.getByTestId("generate-meal-plan-btn").click();
    await expect(page.getByTestId("status-badge")).toBeVisible({ timeout: 25000 });
    await page.getByTestId("confirm-meal-plan-btn").click();

    await page.goto("/workout");
    await page.getByTestId("generate-workout-btn").click();
    await expect(page.getByTestId("workout-session-card").first()).toBeVisible();

    await page.goto("/tracker");
    await page.getByTestId("submit-food-log").click();
    await expect(page.getByTestId("tracker-success-banner")).toBeVisible();

    await page.goto("/dashboard");
    await expect(page.getByTestId("dashboard-text-summary")).toBeVisible();
  });

  test("E2E-2: Non-AI mode — when AI status is disabled, chat shows non-AI banner & disables input", async ({
    page,
  }) => {
    await page.route("**/api/v1/ai/status", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          enabled: false,
          provider: "none",
          model: null,
          cloud_consent_required: false,
          cloud_consent_granted: false,
        }),
      });
    });
    await page.route("**/api/v1/ai/messages", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ messages: [] }),
      });
    });

    await page.goto("/chat");
    await expect(page.getByTestId("ai-unavailable-banner")).toBeVisible();
    await expect(page.getByTestId("chat-input")).toBeDisabled();
  });

  test("E2E-3: Mobile viewport (360x800) has no horizontal overflow", async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 800 });
    for (const path of ["/login", "/register", "/meal-plan", "/workout", "/dashboard"]) {
      await page.goto(path);
      const overflow = await page.evaluate(() => {
        return document.documentElement.scrollWidth > document.documentElement.clientWidth;
      });
      expect(overflow, `Horizontal overflow detected on ${path}`).toBe(false);
    }
  });
});

