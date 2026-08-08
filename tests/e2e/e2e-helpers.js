const { expect } = require("@playwright/test");

async function login(page) {
  const password = process.env.AUTOFLOW_E2E_PASSWORD;
  if (!password) {
    throw new Error("运行端到端测试前必须设置 AUTOFLOW_E2E_PASSWORD。请勿把密码写入仓库。");
  }

  await page.goto("/login");
  await page.locator("#login_email").fill("Administrator");
  await page.locator("#login_password").fill(password);
  const loginResponse = page.waitForResponse((response) => {
    return response.url().includes("/api/method/login") && response.request().method() === "POST";
  });
  const postLoginNavigation = page.waitForURL(
    (url) => url.pathname !== "/login",
    { waitUntil: "domcontentloaded" },
  );
  await page.locator(".btn-login:not(.btn-login-with-email-link)").click();
  const [response] = await Promise.all([loginResponse, postLoginNavigation]);
  expect(response.ok()).toBeTruthy();
  await page.goto("/app/autoflow-workbench", { waitUntil: "domcontentloaded" });
}

async function callFrappe(page, method, args = {}) {
  return page.evaluate(
    async ({ methodName, methodArgs }) => {
      const response = await frappe.call({
        method: methodName,
        type: "GET",
        args: methodArgs,
      });
      return response.message;
    },
    { methodName: method, methodArgs: args },
  );
}

async function getProjectByDemoKey(page, demoKey) {
  const result = await callFrappe(page, "frappe.client.get_value", {
    doctype: "Customer Project",
    filters: { demo_key: demoKey },
    fieldname: ["name", "project_name", "stage"],
  });
  expect(result).toBeTruthy();
  expect(result.name).toBeTruthy();
  return result;
}

async function getList(page, doctype, filters, fields, orderBy = "name asc") {
  return callFrappe(page, "frappe.client.get_list", {
    doctype,
    filters,
    fields,
    order_by: orderBy,
    limit_page_length: 100,
  });
}

async function openScenario(page, demoKey) {
  const project = await getProjectByDemoKey(page, demoKey);
  await page.goto("/app/autoflow-workbench");
  await expect(page.locator(".autoflow-page")).toBeVisible();
  const projectButton = page.locator(".af-project-open").filter({ hasText: demoKey });
  await expect(projectButton).toBeVisible();
  await projectButton.click();
  await expect(page.locator(".af-panorama")).toBeVisible();
  await expect(page.locator(".af-panorama-title")).toContainText(demoKey);
  return project;
}

module.exports = {
  callFrappe,
  getList,
  login,
  openScenario,
};
