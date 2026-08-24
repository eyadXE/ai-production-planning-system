const { chromium } = require("playwright");
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  page.on("request", (r) => { if (r.url().includes("/api/")) console.log(">> REQ", r.method(), r.url()); });
  page.on("response", async (r) => {
    if (r.url().includes("/api/")) {
      let body = "";
      try { body = (await r.text()).slice(0, 150); } catch {}
      console.log("<< RES", r.status(), r.url(), body);
    }
  });
  await page.goto("http://localhost:3100/login?mode=signup", { waitUntil: "networkidle" });
  // is the button actually enabled/visible? list all buttons
  const btns = await page.locator("button").allInnerTexts();
  console.log("buttons:", btns);
  await page.fill('input[type="email"]', `dbg2_${Date.now()}@test.com`);
  await page.fill('input[type="password"]', "password123");
  await page.click('button:has-text("Create account")');
  await page.waitForTimeout(5000);
  console.log("URL:", page.url());
  console.log("body has error?:", (await page.innerText("body")).slice(0, 300).replace(/\n/g, " | "));
  await browser.close();
})();
