const { chromium } = require("playwright");
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const errs = [];
  page.on("pageerror", (e) => errs.push("PAGEERROR: " + e));
  page.on("console", (m) => { if (m.type() === "error") errs.push("CONSOLE: " + m.text()); });
  page.on("response", (r) => { if (r.url().includes("/api/")) console.log("API:", r.status(), r.url()); });

  await page.goto("http://localhost:3100/login?mode=signup", { waitUntil: "networkidle" });
  await page.fill('input[type="email"]', `dbg_${Date.now()}@test.com`);
  await page.fill('input[type="password"]', "password123");
  await page.locator('input[placeholder*="Leave blank"]').fill("Dbg Co");
  await page.click('button:has-text("Create account")');
  await page.waitForTimeout(6000);
  console.log("URL now:", page.url());
  const errDiv = await page.locator(".text-destructive").allInnerTexts().catch(() => []);
  console.log("error div:", errDiv);
  console.log("errors:", errs.slice(0, 5));
  await browser.close();
})();
