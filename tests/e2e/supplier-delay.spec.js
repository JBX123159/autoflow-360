const { test, expect } = require("@playwright/test");
const { getList, login, openScenario } = require("./e2e-helpers");

test("DEMO-DELAY-001 保留供应商延期、整改证据和独立关闭记录", async ({ page }) => {
  await login(page);
  const project = await openScenario(page, "DEMO-DELAY-001");

  await expect(page.locator("#af-section-risks")).toContainText("供应商到货晚于客户交期");
  await expect(page.locator("#af-section-exceptions")).toContainText("已关闭");

  const risks = await getList(
    page,
    "Project Risk",
    { customer_project: project.name, risk_type: "供应商延期" },
    ["name", "risk_level", "status", "reference_doctype", "reference_name"],
  );
  expect(risks.some((row) => row.risk_level === "高")).toBeTruthy();

  const exceptions = await getList(
    page,
    "Business Exception",
    { customer_project: project.name, exception_type: "供应商延期" },
    ["name", "status", "root_cause", "verification_evidence", "verified_by", "verified_at"],
  );
  expect(exceptions).toHaveLength(1);
  expect(exceptions[0].status).toBe("已关闭");
  expect(exceptions[0].root_cause).toBeTruthy();
  expect(exceptions[0].verification_evidence).toBeTruthy();
  expect(exceptions[0].verified_by).toBeTruthy();
});
