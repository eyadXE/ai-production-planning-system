const { chromium } = require("playwright");
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  page.on("pageerror", (e) => console.log("PAGEERROR:", String(e).slice(0,150)));
  // login as engineer through UI with retry
  await page.goto("http://localhost:3100/login", { waitUntil: "networkidle" });
  for (let i = 0; i < 3; i++) {
    await page.fill('input[type="email"]', "engineer@oususapp.com");
    await page.fill('input[type="password"]', "demo1234");
    await page.click('button:has-text("Sign in")');
    try { await page.waitForURL("**/summary", { timeout: 6000 }); break; } catch {}
  }
  console.log("after login URL:", page.url());
  await page.goto("http://localhost:3100/review", { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  const body = await page.innerText("body");
  console.log("review has pending?:", /Approve → planning phase/.test(body));
  console.log("body snippet:", body.slice(0, 350).replace(/\n/g, " | "));
  await browser.close();
})();
