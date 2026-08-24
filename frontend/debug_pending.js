const { chromium } = require("playwright");
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const errs = [];
  page.on("pageerror", (e) => errs.push(String(e).slice(0, 150)));

  // fresh signup
  await page.goto("http://localhost:3100/login?mode=signup", { waitUntil: "networkidle" });
  const email = `dbg_${Date.now()}@test.com`;
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', "password123");
  await page.locator('form input:not([type="email"]):not([type="password"])').first().fill("Dbg User");
  await page.click('button:has-text("Create account")');
  await page.waitForURL("**/request", { timeout: 15000 });
  await page.waitForSelector("text=Carbon Steel", { timeout: 15000 });

  // add mapped product
  const card = page.locator("div.border", { hasText: "Railings" }).locator('button:has-text("Add")').first();
  await card.click();
  await page.fill('input[placeholder="Request title *"]', "Dbg railings");
  await page.fill('input[placeholder*="Deadline"]', "within 4 weeks");
  await page.click('button:has-text("Submit request for engineering review")');
  await page.waitForSelector("text=Request submitted", { timeout: 15000 });

  // now check as engineer
  const login2 = await page.request.post("http://localhost:3100/api/auth/login", {
    data: { email: "engineer@oususapp.com", password: "demo1234" },
  });
  console.log("eng login:", login2.status());
  const { access_token } = await login2.json();
  const pending = await page.evaluate(async (t) => {
    const r = await fetch("/api/requests/pending", { headers: { Authorization: `Bearer ${t}` } });
    return { status: r.status, body: (await r.text()).slice(0, 250) };
  }, access_token);
  console.log("pending:", pending.status, pending.body);
  console.log("pageerrors:", errs);
  await browser.close();
})();
