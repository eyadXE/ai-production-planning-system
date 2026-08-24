const BASE = "http://localhost:3100";
const { chromium } = require("playwright");
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const login = await page.request.post("http://localhost:3100/api/auth/login", {
    data: { email: "client@oususapp.com", password: "demo1234" },
  });
  const { access_token } = await login.json();

  async function api(url, opts = {}) {
    const res = await page.evaluate(async ([u, t, o]) => {
      const r = await fetch(u, {
        method: o.method || "GET",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${t}` },
        body: o.body ? JSON.stringify(o.body) : undefined,
      });
      return { s: r.status, b: await r.text() };
    }, [url, access_token, opts]);
    console.log(res.s, res.b.slice(0, 260));
    try { return JSON.parse(res.b); } catch { return null; }
  }

  const start = await api(BASE+"/api/intake/start", { method: "POST" });
  const sid = start.session_id;
  let out;
  out = await api(`${BASE}/api/intake/${sid}/message`, { method: "POST",
    body: { text: "A custom spiral staircase, black mild steel, 3m rise, one unit, villa in Katameya, within two months — please confirm and submit" } });
  console.log("complete?", out.complete, "| reply:", (out.reply || "").slice(0, 150));
  if (!out.complete) {
    out = await api(`${BASE}/api/intake/${sid}/message`, { method: "POST", body: { text: "yes confirmed, submit" } });
    console.log("complete?", out.complete, "| code:", out.code, "| reply:", (out.reply || "").slice(0, 150));
  }
  await browser.close();
})();
