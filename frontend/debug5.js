const { chromium } = require("playwright");
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const logs = [];
  page.on("console", (m) => logs.push(m.type() + ": " + m.text().slice(0, 120)));
  page.on("pageerror", (e) => logs.push("PAGEERROR: " + String(e).slice(0, 200)));

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

  // find the RAILINGS card specifically (has est_kind=railing)
  const card = page.locator("div.border", { hasText: "Railings" })
                   .locator('button:has-text("Add")').first();
  const propsOnClick = await page.evaluate(() => {
    const btn = [...document.querySelectorAll("button")].find((b) => b.textContent.includes("Add"));
    const propsKey = Object.keys(btn).find((k) => k.startsWith("__reactProps$"));
    return { hasOnClick: !!(propsKey && btn[propsKey] && btn[propsKey].onClick),
             propKeys: Object.keys(btn[propsKey] || {}) };
  });
  console.log("onClick present:", propsOnClick.hasOnClick, propsOnClick.propKeys);

  await card.click();
  await page.waitForTimeout(800);
  console.log("logs:", logs);
  const body = await page.innerText("body");
  console.log("indicator:", /in your request/.test(body));
  console.log("cart table has Railings:", /Railings/.test(body.slice(body.indexOf("Your request"))));
  await browser.close();
})();
