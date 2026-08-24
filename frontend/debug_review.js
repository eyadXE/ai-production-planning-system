const { chromium } = require("playwright");
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const login = await page.request.post("http://localhost:3100/api/auth/login", {
    data: { email: "engineer@oususapp.com", password: "demo1234" },
  });
  const { access_token } = await login.json();
  await page.goto("http://localhost:3100/login", { waitUntil: "networkidle" });
  await page.evaluate((t) => {
    localStorage.setItem("ousus_token", t);
    localStorage.setItem("ousus_user", JSON.stringify({ email: "engineer@oususapp.com", full_name: "Eng", role: "engineer" }));
  }, access_token);

  const pending = await page.evaluate(async (t) => {
    const r = await fetch("/api/requests/pending", { headers: { Authorization: `Bearer ${t}` } });
    return { status: r.status, body: await r.text() };
  }, access_token);
  console.log("pending:", pending.status, pending.body.slice(0, 200));

  await page.goto("http://localhost:3100/review", { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  console.log("review body:", (await page.innerText("body")).slice(0, 400).replace(/\n/g, " | "));
  await browser.close();
})();
