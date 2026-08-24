const { chromium } = require("playwright");
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto("http://localhost:3100/login?mode=signup", { waitUntil: "networkidle" });
  await page.fill('input[type="email"]', `x${Date.now()}@t.com`);
  await page.fill('input[type="password"]', "password123");
  await page.locator('form input:not([type="email"]):not([type="password"])').first().fill("X");
  await page.click('button:has-text("Create account")');
  try { await page.waitForURL("**/request", { timeout: 8000 }); } catch {}
  await page.waitForSelector("text=Carbon Steel", { timeout: 15000 });
  const n1 = await page.locator("div.border", { hasText: "Railings" }).count();
  const n2 = await page.locator("div.border", { hasText: "Railings" }).locator('button:has-text("Add")').count();
  const btns = await page.locator("button").allInnerTexts();
  console.log({ n1, n2, sampleButtons: btns.slice(0, 8) });
  await browser.close();
})();
