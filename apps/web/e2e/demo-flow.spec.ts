import { expect, test } from "@playwright/test";

test("interview demo lifecycle", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Erin Employee")).toBeVisible();

  await page.getByTestId("identity-switcher").selectOption("employee@example.local");
  await page.getByLabel("Project name").fill("Interview Demo Sandbox");
  await page
    .getByLabel("Business justification")
    .fill("Evaluate governed AI assistance for customer support workflows.");
  await page.getByLabel("Sponsor").fill("Casey CTO");
  await page.getByLabel("Cost center").fill("ENG-AI");
  await page.getByLabel("Budget").fill("100");
  await page.getByLabel("Users").fill("4");
  await page.getByLabel("Data class").selectOption("internal");
  await page.getByLabel("amazon bedrock").check();
  await page.getByLabel("github copilot").check();
  await page.getByLabel("Proprietary source code").check();
  await page.getByLabel("Usage pattern").fill("Burst testing during a two-week prototype.");
  await page.getByLabel("Monthly volume").fill("200000");
  await page.getByTestId("submit-request").click();
  await expect(page.getByTestId("status-AWAITING_MANAGER_APPROVAL")).toBeAttached();

  await page.getByTestId("identity-switcher").selectOption("approver@example.local");
  await page.getByTestId("approve-manager").click();
  await expect(page.getByTestId("status-AWAITING_CTO_APPROVAL")).toBeAttached();

  await page.getByTestId("identity-switcher").selectOption("cto@example.local");
  await page.getByTestId("approve-cto").click();
  await expect(page.getByTestId("status-ACTIVE")).toBeAttached();

  await page.getByTestId("identity-switcher").selectOption("admin@example.local");
  await expect(page.getByText("Developer Controls")).toBeVisible();
  await page.getByTestId("usage-warning-amazon_bedrock").click();
  await page.getByTestId("usage-critical-amazon_bedrock").click();
  await page.getByTestId("usage-enforcement-amazon_bedrock").click();
  await expect(page.getByTestId("status-SUSPENDED")).toBeAttached();
  await page.getByTestId("restore-amazon_bedrock").click();
  await expect(page.getByTestId("status-ACTIVE")).toBeAttached();
  await page.getByTestId("expire-amazon_bedrock").click();
  await expect(page.getByTestId("status-CLOSED")).toBeAttached();
  await expect(page.getByText("Latest archive")).toBeVisible();

  await page.getByTestId("identity-switcher").selectOption("auditor@example.local");
  await expect(page.getByText("Audit Trail")).toBeVisible();
  await expect(page.getByText("lifecycle.closed")).toBeVisible();
  await page.getByText("Export CSV").click();
  await expect(page.getByText(/CSV export ready/)).toBeVisible();
});
