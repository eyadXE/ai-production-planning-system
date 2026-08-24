const { chromium } = require("playwright");
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  page.on("response", async (r) => {
    if (r.url().includes("/api/")) {
      let b = ""; try { b = (await r.text()).slice(0, 120); } catch {}
      console.log("API", r.status(), r.request().method(), r.url().replace("http://localhost:3100",""), b);
    }
  });
  await page.goto("http://localhost:3100/login?mode=signup", { waitUntil: "networkidle" });
  await page.fill('input[type="email"]', `dbg2_${Date.now()}@test.com`);
  await page.fill('input[type="password"]', "password123");
  await page.locator('form input:not([type="email"]):not([type="password"])').first().fill("Dbg User");
  // check validation state before click
  const valid = await page.evaluate(() => {
    const f = document.querySelector("form");
    return { formValid: f.checkValidity(), invalid: [...f.querySelectorAll(":invalid")].map(i => i.placeholder || i.type) };
  });
  console.log("validity:", valid);
  await page.click('button:has-text("Create account")');
  await page.waitForTimeout(4000);
  console.log("URL:", page.url());
  await browser.close();
})();
