const { test, expect } = require("@playwright/test");
const { getList, login, openScenario } = require("./e2e-helpers");

test("DEMO-NORMAL-001 完成交付、开票、回款和结项闭环", async ({ page }) => {
  await login(page);
  const project = await openScenario(page, "DEMO-NORMAL-001");

  await expect(page.locator(".af-summary-grid")).toContainText("已结项");
  await expect(page.locator("#af-section-flow")).toContainText("项目结项");
  await expect(page.locator("#af-section-documents")).toContainText("Sales Order");
  await expect(page.locator("#af-section-documents")).toContainText("Purchase Order");
  await expect(page.locator("#af-section-documents")).toContainText("Delivery Note");
  await expect(page.locator("#af-section-documents")).toContainText("Sales Invoice");
  await expect(page.locator("#af-section-documents")).toContainText("Payment Entry");

  const paymentEntries = await getList(
    page,
    "Payment Entry",
    { custom_customer_project: project.name, docstatus: 1 },
    ["name", "paid_amount", "received_amount", "paid_from_account_currency", "paid_to_account_currency"],
  );
  expect(paymentEntries).toHaveLength(1);
  expect(paymentEntries[0].paid_amount).toBeGreaterThan(0);
});
