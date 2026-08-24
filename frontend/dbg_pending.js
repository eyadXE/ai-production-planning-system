const { chromium } = require("playwright");
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const r = await page.request.post("http://localhost:3100/api/auth/login", {
    data: { email: "estimator@oususapp.com", password: "demo1234" },
  });
  console.log("login:", r.status());
  const { access_token } = await r.json();
  const p2 = await page.evaluate(async (t) => {
    const res = await fetch("/api/requests/pending", { headers: { Authorization: `Bearer ${t}` } });
    return { s: res.status, b: await res.text() };
  }, access_token);
  console.log(p2.s, p2.b.slice(0, 400));
  await browser.close();
})();
