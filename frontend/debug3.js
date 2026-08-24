const { chromium } = require("playwright");
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  page.on("pageerror", (e) => console.log("PAGEERROR:", String(e).slice(0,200)));
  await page.goto("http://localhost:3100/login", { waitUntil: "networkidle" });
  await page.fill('input[type="email"]', "client@oususapp.com");
  await page.fill('input[type="password"]', "demo1234");
  await page.click('button:has-text("Sign in")');
  await page.waitForTimeout(2500);
  await page.goto("http://localhost:3100/request", { waitUntil: "networkidle" });
  await page.waitForSelector("text=Carbon Steel", { timeout: 15000 });

  const btns = await page.locator('button:has-text("Add")').allInnerTexts();
  console.log("add-buttons:", JSON.stringify(btns.slice(0,5)));
  await page.locator('button:has-text("Add")').first().click();
  await page.waitForTimeout(500);
  const body = await page.innerText("body");
  const i = body.indexOf("Your request");
  console.log("around 'Your request':", JSON.stringify(body.slice(i, i+220)));
  console.log("has indicator:", /in your request/.test(body));
  await browser.close();
})();
