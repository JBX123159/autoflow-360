const { test, expect } = require("@playwright/test");
const { getList, login, openScenario } = require("./e2e-helpers");

test("DEMO-RESAMPLE-001 保留首轮重新打样和次轮客户认可证据", async ({ page }) => {
  await login(page);
  const project = await openScenario(page, "DEMO-RESAMPLE-001");

  await expect(page.locator("#af-section-documents")).toContainText("Sample Request");
  await expect(page.locator("#af-section-documents")).toContainText("Customer Feedback");

  const samples = await getList(
    page,
    "Sample Request",
    { customer_project: project.name },
    ["name", "round_number", "previous_sample_request", "status", "feedback"],
    "round_number asc",
  );
  expect(samples).toHaveLength(2);
  expect(samples[0].round_number).toBe(1);
  expect(samples[0].status).toBe("重新打样");
  expect(samples[1].round_number).toBe(2);
  expect(samples[1].previous_sample_request).toBe(samples[0].name);
  expect(samples[1].status).toBe("客户认可");

  const feedback = await getList(
    page,
    "Customer Feedback",
    { sample_request: ["in", samples.map((row) => row.name)] },
    ["sample_request", "decision", "submitted_by", "submitted_at"],
  );
  expect(new Set(feedback.map((row) => row.decision))).toEqual(
    new Set(["重新打样", "客户认可"]),
  );
});
