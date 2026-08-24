const { chromium } = require("playwright");
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const logs = [];
  page.on("console", (m) => logs.push(m.type() + ": " + m.text().slice(0, 200)));
  page.on("pageerror", (e) => logs.push("PAGEERROR: " + String(e).slice(0, 300)));

  // login via API to keep it simple
  const login = await page.request.post("http://localhost:3100/api/auth/login", {
    data: { email: "client@oususapp.com", password: "demo1234" },
  });
  const { access_token, user } = await login.json();

  await page.goto("http://localhost:3100/login", { waitUntil: "networkidle" });
  await page.evaluate(([t, u]) => {
    localStorage.setItem("ousus_token", t);
    localStorage.setItem("ousus_user", JSON.stringify(u));
  }, [access_token, user]);

  await page.goto("http://localhost:3100/request", { waitUntil: "networkidle" });
  await page.waitForSelector("text=Carbon Steel", { timeout: 15000 });
  await page.waitForTimeout(1000);

  const fiber = await page.evaluate(() => {
    const btn = [...document.querySelectorAll("button")].find((b) => b.textContent.includes("Add"));
    if (!btn) return { found: false };
    const keys = Object.keys(btn).filter((k) => k.startsWith("__react"));
    return { found: true, keys, disabled: btn.disabled };
  });
  console.log("fiber:", fiber);

  await page.locator('button:has-text("Add")').first().click();
  await page.waitForTimeout(600);
  console.log("logs:", logs.slice(0, 8));
  const body = await page.innerText("body");
  console.log("indicator:", /in your request/.test(body));
  await browser.close();
})();
