const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const BASE_URL = process.env.AUTOFLOW_E2E_BASE_URL || "http://autoflow.localhost:8000";
const PASSWORD = process.env.AUTOFLOW_E2E_PASSWORD;
const ROOT_DIR = path.resolve(__dirname, "..", "..");
const DOCS_DIR = path.join(ROOT_DIR, "docs", "images");
const VIDEO_DIR = path.join(
  ROOT_DIR,
  "videos",
  "autoflow-360-launch",
  "assets",
  "product",
);

if (!PASSWORD) {
  throw new Error("运行演示截图前必须设置 AUTOFLOW_E2E_PASSWORD。");
}

for (const directory of [DOCS_DIR, VIDEO_DIR]) {
  fs.mkdirSync(directory, { recursive: true });
}

async function waitForWorkbench(page) {
  await page.waitForSelector(".autoflow-page", { state: "visible" });
  await page.waitForSelector(".af-project-open", { state: "visible" });
}

async function resetScroll(page) {
  await page.evaluate(() => {
    window.scrollTo(0, 0);
    for (const element of document.querySelectorAll("*")) {
      if (element.scrollTop) {
        element.scrollTop = 0;
      }
      if (element.scrollLeft) {
        element.scrollLeft = 0;
      }
    }
  });
  await page.waitForTimeout(150);
}

async function saveScreenshot(page, filename, options = {}) {
  const docsPath = path.join(DOCS_DIR, filename);
  const videoPath = path.join(VIDEO_DIR, filename);
  await page.screenshot({
    path: docsPath,
    fullPage: false,
    animations: "disabled",
    ...options,
  });
  fs.copyFileSync(docsPath, videoPath);
  console.log(`CAPTURED ${filename}`);
}

async function login(page) {
  await page.goto(`${BASE_URL}/login`, { waitUntil: "domcontentloaded" });
  await page.locator("#login_email").fill("Administrator");
  await page.locator("#login_password").fill(PASSWORD);

  const loginResponse = page.waitForResponse((response) => {
    return response.url().includes("/api/method/login") && response.request().method() === "POST";
  });
  await page.locator(".btn-login:not(.btn-login-with-email-link)").click({ noWaitAfter: true });
  const response = await loginResponse;
  if (!response.ok()) {
    throw new Error(`登录失败，HTTP 状态码：${response.status()}`);
  }
}

async function openScenario(page, demoKey) {
  await page.goto(`${BASE_URL}/app/autoflow-workbench`, { waitUntil: "domcontentloaded" });
  await waitForWorkbench(page);
  const button = page.locator(".af-project-open").filter({ hasText: demoKey });
  await button.waitFor({ state: "visible" });
  await button.click();
  await page.locator(".af-panorama").waitFor({ state: "visible" });
  await page.locator(".af-panorama-title").filter({ hasText: demoKey }).waitFor({ state: "visible" });
  await resetScroll(page);
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    locale: "zh-CN",
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  page.setDefaultTimeout(15_000);

  try {
    await login(page);

    await page.goto(`${BASE_URL}/app/autoflow-workbench`, { waitUntil: "domcontentloaded" });
    await waitForWorkbench(page);
    await resetScroll(page);
    await saveScreenshot(page, "01-workbench-overview.png");

    await page.locator("#af-project-heading").scrollIntoViewIfNeeded();
    await page.waitForTimeout(150);
    await saveScreenshot(page, "07-project-portfolio.png");

    await openScenario(page, "DEMO-NORMAL-001");
    await saveScreenshot(page, "02-normal-project.png");
    await page.locator(".af-document-group").filter({ hasText: "财务" }).scrollIntoViewIfNeeded();
    await page.waitForTimeout(150);
    await saveScreenshot(page, "08-normal-finance-closure.png");

    await openScenario(page, "DEMO-DELAY-001");
    await saveScreenshot(page, "03-supplier-delay.png");
    await page.locator("#af-section-exceptions").scrollIntoViewIfNeeded();
    await page.waitForTimeout(150);
    await saveScreenshot(page, "09-delay-remediation.png");

    await openScenario(page, "DEMO-RESAMPLE-001");
    await saveScreenshot(page, "04-resample.png");

    await page.goto(`${BASE_URL}/app/autoflow-cockpit`, { waitUntil: "domcontentloaded" });
    await page.locator(".autoflow-page:not([aria-busy]) .af-metric").first().waitFor({ state: "visible" });
    await resetScroll(page);
    await saveScreenshot(page, "05-management-cockpit.png");

    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`${BASE_URL}/app/autoflow-workbench`, { waitUntil: "domcontentloaded" });
    await waitForWorkbench(page);
    await resetScroll(page);
    await saveScreenshot(page, "06-mobile-workbench.png");
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
