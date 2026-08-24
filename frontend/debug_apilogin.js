const { chromium } = require("playwright");
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const BASE = "http://localhost:3100";
  const r = await page.request.post(BASE + "/api/auth/login", {
    data: { email: "engineer@oususapp.com", password: "demo1234" },
  });
  console.log("login status:", r.status());
  const { access_token, user } = await r.json();
  console.log("token len:", access_token?.length, "role:", user?.role);
  await page.goto(BASE + "/login", { waitUntil: "networkidle" });
  await page.evaluate(([t, u]) => {
    localStorage.setItem("ousus_token", t);
    localStorage.setItem("ousus_user", JSON.stringify(u));
    console.log("stored:", localStorage.getItem("ousus_user"));
  }, [access_token, user]);
  const stored = await page.evaluate(() => localStorage.getItem("ousus_user"));
  console.log("verify stored:", stored);
  await page.goto(BASE + "/review", { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  const body = await page.innerText("body");
  console.log("is login page?", /EMAIL/.test(body));
  console.log("body head:", body.slice(0, 200).replace(/\n/g, " | "));
  await browser.close();
})();
