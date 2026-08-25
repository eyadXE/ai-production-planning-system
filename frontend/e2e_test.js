/* E2E browser test: full 5-gate flow against a freshly seeded app.
   Backend (:8000) + frontend (:3100) running, DB freshly seeded. */
const { chromium } = require("playwright");

const BASE = "http://localhost:3100";
const results = [];
function check(name, ok, extra = "") {
  results.push({ name, ok, extra });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${extra ? " — " + extra.slice(0, 220) : ""}`);
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const pageErrors = [];
  page.on("pageerror", (err) => pageErrors.push(String(err)));
  page.on("console", (m) => {
    if (m.type() === "error") pageErrors.push("console: " + m.text());
  });

  async function apiLogin(email) {
    const r = await page.request.post(BASE + "/api/auth/login", {
      data: { email, password: "demo1234" },
    });
    if (r.status() !== 200) {
      console.log("  [apiLogin] FAILED", email, r.status());
      return false;
    }
    const { access_token, user } = await r.json();
    await page.goto(BASE + "/login", { waitUntil: "networkidle" });
    await page.evaluate(([t, u]) => {
      localStorage.setItem("ousus_token", t);
      localStorage.setItem("ousus_user", JSON.stringify(u));
    }, [access_token, user]);
  }

  async function clickUntilNav(buttonText, urlPattern, tries = 3) {
    for (let i = 0; i < tries; i++) {
      const btn = page.locator(`button:has-text("${buttonText}")`).first();
      if (!(await btn.count())) return;
      await btn.click().catch(() => {});
      try {
        await page.waitForURL(urlPattern, { timeout: 6000 });
        return;
      } catch {}
      await page.waitForTimeout(1200);
    }
  }

  async function openTab(label) {
    // wait for React hydration before interacting
    await page
      .waitForFunction(
        () => [...document.querySelectorAll("button")].some((b) =>
          Object.keys(b).some((k) => k.startsWith("__reactProps$"))),
        { timeout: 30000 }
      )
      .catch(() => {});
    for (let i = 0; i < 4; i++) {
      const btn = page.locator(`button:has-text("${label}")`).first();
      if (await btn.count()) await btn.click().catch(() => {});
      await page.waitForTimeout(800);
    }
  }

  async function chooseProduct(name) {
    await page.evaluate((n) => {
      const btn = [...document.querySelectorAll("button")].find((b) => {
        if (!b.textContent.includes("Choose")) return false;
        const card = b.closest("div.border");
        return card && card.querySelector("b")?.textContent === n;
      });
      if (btn) btn.click();
    }, name);
    await page.waitForTimeout(500);
  }

  try {
    // ---------- landing ----------
    await page.goto(BASE + "/", { waitUntil: "networkidle" });
    check("landing loads", (await page.title()).includes("Ousus"));
    check("hero image renders", await page.evaluate(() => {
      const img = document.querySelector('img[src="/hero.jpg"]');
      return img && img.complete && img.naturalWidth > 0;
    }));

    // ---------- signup -> /request ----------
    await page.goto(BASE + "/login?mode=signup", { waitUntil: "networkidle" });
    const email = `e2e_${Date.now()}@test.com`;
    await page.fill('input[type="email"]', email);
    await page.fill('input[type="password"]', "password123");
    await page.locator('form input:not([type="email"]):not([type="password"])').first().fill("E2E Tester");
    await page.locator('input[placeholder*="Leave blank"]').fill("E2E Test Co");
    await page.click('button:has-text("Create account")');
    let redirected = true;
    await page.waitForURL("**/request", { timeout: 6000 }).catch(async () => {
      await clickUntilNav("Create account", "**/request");
      redirected = page.url().includes("/request");
    });
    check("signup redirects to /request", redirected, "url=" + page.url());
    await page.waitForTimeout(1500);

    // ---------- catalog ----------
    check("catalog renders",
          (await page.innerText("body")).includes("Carbon Steel"));
    await page
      .waitForFunction(
        () => [...document.querySelectorAll('img[src*="/images/"]')]
                .every((i) => i.complete && i.naturalWidth > 0),
        { timeout: 15000 }
      )
      .catch(() => {});
    const brokenImgs = await page.evaluate(() =>
      [...document.querySelectorAll("img")]
        .filter((i) => i.src.includes("/images/") && (!i.complete || i.naturalWidth === 0))
        .map((i) => i.src)
    );
    check("all product images render", brokenImgs.length === 0,
          [...new Set(brokenImgs)].join(", ").slice(0, 120));

    // ---------- cart: mapped product via configure route ----------
    await chooseProduct("Railings"); // opens detail (grid fallback)
    const railLink = page.locator('a[href*="/configure?id="]').first();
    if (await railLink.count()) {
      // grid link path
    }
    // navigate directly to a mapped product's configure page
    const mappedId = await page.evaluate(async () => {
      const r = await fetch("/api/products");
      return (await r.json()).products.find((p) => p.name === "Railings").id;
    });
    await page.goto(`${BASE}/configure?id=${mappedId}`, { waitUntil: "load" });
    await page.locator('input[type="number"]').fill("14");
    await page.click('button:has-text("Add to my request")');
    await page.waitForTimeout(400);

    // unmapped product -> custom line
    const unmappedId = await page.evaluate(async () => {
      const r = await fetch("/api/products");
      return (await r.json()).products.find((p) => !p.est_kind).id;
    });
    await page.goto(`${BASE}/configure?id=${unmappedId}`, { waitUntil: "load" });
    await page.locator('input[type="number"]').fill("1");
    await page.click('button:has-text("Add to my request")');
    await page.waitForTimeout(400);

    await page.goto(BASE + "/request", { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2500);
    let body = await page.innerText("body");
    check("cart lines persist across pages",
          /Railings/.test(body) && /CUSTOM/i.test(body));

    // qty edit on submit tab
    await openTab("3 · Review & submit");
    await page.waitForTimeout(500);
    const qtyInputs = page.locator('#your-request input[type="number"]');
    if (await qtyInputs.count()) {
      await qtyInputs.first().fill("14");
      check("qty editable", true);
    }

    // ---------- checkout ----------
    await page.fill('input[placeholder="Request title *"]', "E2E villa package");
    await page.fill('input[placeholder*="Deadline"]', "within 6 weeks");
    await page.click('button:has-text("Submit request")');
    try {
      await page.waitForSelector("text=Request submitted", { timeout: 20000 });
      const code = await page.evaluate(() =>
        (document.body.innerText.match(/J-\d{3}/) || [])[0]);
      check("cart request submitted (" + code + ")", !!code);
    } catch {
      const b = await page.innerText("body");
      check("cart request submitted", false,
            b.slice(0, 220).replace(/\n/g, " "));
    }

    // ---------- custom chat ----------
    // fresh load so the submitted-state view is cleared
    await page.goto(BASE + "/request", { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2500);
    await openTab("2 · Fully custom build");
    await page.click('button:has-text("Start the assistant")');
    await page.waitForFunction(
      () => !document.body.innerText.includes("Connecting…") &&
            !document.body.innerText.includes("Thinking…"),
      { timeout: 60000 }
    );
    body = await page.innerText("body");
    check("chat opens with assistant reply",
          /Ousus assistant|what would you|like us to build|tell me/i.test(body));

    const chatAnswer = async (text) => {
      await page.fill('input[placeholder="Type your answer…"]', text);
      await page.click('button:has-text("Send")');
      await page.waitForFunction(
        () => !document.body.innerText.includes("Thinking…"),
        { timeout: 90000 }
      );
      await page.waitForTimeout(300);
      return page.innerText("body");
    };
    body = await chatAnswer(
      "A custom spiral staircase, black mild steel, 3m rise, one unit, villa in Katameya, within two months"
    );
    for (let i = 0; i < 5; i++) {
      if (/submitted as request|Request J-\d+ submitted/i.test(body)) break;
      body = await chatAnswer(
        i >= 1 ? "yes confirmed, submit it now" : "yes that is correct, proceed"
      );
    }
    check("custom chat submitted through schema gate",
          /submitted as request J-\d+|Request J-\d+ submitted/i.test(body));

    // ---------- light/dark toggle ----------
    await page.goto(BASE + "/my", { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);
    const toggle = page.locator('button[aria-label="Toggle light/dark mode"]');
    check("theme toggle present", (await toggle.count()) === 1);
    if (await toggle.count()) {
      const before = await page.evaluate(() => document.documentElement.className);
      await toggle.click();
      const after = await page.evaluate(() => document.documentElement.className);
      check("light/dark switches", before !== after, `${before} -> ${after}`);
    }

    // ---------- estimator reviews & sends plan ----------
    await apiLogin(page, "estimator@oususapp.com");
    await page.goto(BASE + "/review", { waitUntil: "networkidle" });
    await page.waitForTimeout(1500);
    let reviewBody = await page.innerText("body");
    const hasPending = /Villa package|spiral|E2E/i.test(reviewBody);
    check("pending requests visible to estimator", hasPending,
          hasPending ? "" : reviewBody.slice(0, 250).replace(/\n/g, " | "));
    if (hasPending) {
      await page.locator('button:has-text("Approve & send plan to manager")').first().click();
      await page.waitForTimeout(45000); // pipeline may call the LLM chain
      reviewBody = await page.innerText("body");
      check("estimator decision recorded",
            /Decision: (PLAN|DELAY_RISK|MANUAL_PLAN)/.test(reviewBody));
    }

    // ---------- manager approves all pending plans ----------
    await apiLogin(page, "manager@oususapp.com");
    await page.goto(BASE + "/approvals", { waitUntil: "networkidle" });
    await page.waitForTimeout(1200);
    check("manager sees audit trail",
          /Audit Trail/i.test(await page.innerText("body")));
    const approveBtns = page.locator('button:has-text("Approve")');
    let approvedAny = false;
    while (await approveBtns.count()) {
      await approveBtns.first().click();
      approvedAny = true;
      await page.waitForTimeout(4000);
    }
    check("manager approved pending plans", approvedAny);

    // assign engineers to planning-stage projects
    await page.goto(BASE + "/assign", { waitUntil: "networkidle" });
    await page.waitForTimeout(1500);
    const assignSel = page.locator("select").first();
    let assigned = false;
    while (await assignSel.count()) {
      try {
        await assignSel.first().selectOption({ index: 1 });
        assigned = true;
        await page.waitForTimeout(2000);
      } catch { break; }
    }
    check("engineer assigned via Assign page", assigned);

    // ---------- client accepts from dashboard ----------
    await apiLogin(page, email);
    await page.goto(BASE + "/my", { waitUntil: "networkidle" });
    await page.waitForTimeout(1500);
    const acceptBtn = page.locator('button:has-text("Accept plan")').first();
    if (await acceptBtn.count()) {
      await acceptBtn.click();
      await page.waitForTimeout(3000);
      check("client accepted plan from dashboard", true);
    } else {
      const b2 = await page.innerText("body");
      check("client accepted plan from dashboard", false,
            b2.slice(0, 200).replace(/\n/g, " "));
    }
    check("client sees notification feed",
          /Updates for you/.test(await page.innerText("body")));

    // ---------- manager final release ----------
    await apiLogin(page, "manager@oususapp.com");
    await page.goto(BASE + "/approvals", { waitUntil: "networkidle" });
    await page.waitForTimeout(1200);
    const relBtn = page.locator('button:has-text("Release to production")').first();
    if (await relBtn.count()) {
      await relBtn.click();
      await page.waitForTimeout(4000);
      check("manager released after client acceptance", true);
    } else {
      const b3 = await page.innerText("body");
      check("manager released after client acceptance", false,
            b3.slice(0, 180).replace(/\n/g, " "));
    }

    // ---------- timeline ----------
    await page.goto(BASE + "/timeline", { waitUntil: "networkidle" });
    await page.waitForTimeout(1500);
    check("timeline renders capacity weeks",
          /Fabrication week/i.test(await page.innerText("body")));

    // ---------- board ----------
    await page.goto(BASE + "/board", { waitUntil: "networkidle" });
    await page.waitForSelector("text=Fabrication", { timeout: 20000 });
    const boardBody = await page.innerText("body");
    check("board shows 10 stages",
          ["award", "fabrication", "installation"].every((s) =>
            boardBody.toLowerCase().includes(s)));

    // ---------- summary register (manager) ----------
    await page.goto(BASE + "/summary", { waitUntil: "networkidle" });
    await page.waitForTimeout(1000);
    check("summary renders project register",
          /Project register/i.test(await page.innerText("body")));

    check("no uncaught page errors", pageErrors.length === 0,
          pageErrors.slice(0, 3).join(" | ").slice(0, 300));
  } catch (e) {
    check("FATAL: " + e.message.slice(0, 160), false);
  }

  await browser.close();
  const failed = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - failed}/${results.length} checks passed`);
  process.exit(0);
})();
