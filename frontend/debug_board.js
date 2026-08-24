const { chromium } = require("playwright");
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const errs = [];
  page.on("pageerror", (e) => errs.push(String(e).slice(0, 200)));
  const login = await page.request.post("http://localhost:3100/api/auth/login", {
    data: { email: "engineer@oususapp.com", password: "demo1234" },
  });
  const { access_token } = await login.json();
  await page.goto("http://localhost:3100/login", { waitUntil: "networkidle" });
  await page.evaluate((t) => {
    localStorage.setItem("ousus_token", t);
    localStorage.setItem("ousus_user", JSON.stringify({ email: "engineer@oususapp.com", full_name: "Eng", role: "engineer" }));
  }, access_token);
  await page.goto("http://localhost:3100/board", { waitUntil: "networkidle" });
  await page.waitForTimeout(3000);
  console.log("errors:", errs);
  console.log("body:", (await page.innerText("body")).slice(0, 300).replace(/\n/g, " | "));
  await browser.close();
})();
