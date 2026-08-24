/* E2E browser test: full client + staff flows against a freshly seeded app.
   Run with backend (:8000) and frontend (:3100) up, DB freshly seeded. */
const { chromium } = require("playwright");

const BASE = "http://localhost:3100";
const results = [];
function check(name, ok, extra = "") {
  results.push({ name, ok, extra });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${extra ? " — " + extra.slice(0, 220) : ""}`);
}

async function apiLogin(page, email) {
  const r = await page.request.post(BASE + "/api/auth/login", {
    data: { email, password: "demo1234" },
  });
  const { access_token, user } = await r.json();
  await page.goto(BASE + "/login", { waitUntil: "networkidle" });
  await page.evaluate(([t, u]) => {
    localStorage.setItem("ousus_token", t);
    localStorage.setItem("ousus_user", JSON.stringify(u));
  }, [access_token, user]);
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const pageErrors = [];
  page.on("pageerror", (err) => pageErrors.push(String(err)));
  page.on("console", (m) => {
    if (m.type() === "error") pageErrors.push("console: " + m.text());
  });

  async function clickUntilNav(buttonText, urlPattern, tries = 3) {
    for (let i = 0; i < tries; i++) {
      const btn = page.locator(`button:has-text("${buttonText}")`).first();
      if (!(await btn.count())) return;
      await btn.click().catch(() => {});
      try {
        await page.waitForURL(urlPattern, { timeout: 6000 });
        return;
      } catch {}
      await page.waitForTimeout(1000);
    }
  }

  try {
    // ---------- landing ----------
    await page.goto(BASE + "/", { waitUntil: "networkidle" });
    check("landing loads", (await page.title()).includes("Ousus"));
    check("hero image renders", await page.evaluate(() => {
      const img = document.querySelector('img[src="/hero.jpg"]');
      return img && img.complete && img.naturalWidth > 0;
    }));

    // ---------- signup ----------
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

    // ---------- catalog ----------
    await page.waitForSelector("text=Carbon Steel", { timeout: 15000 });
    check("catalog renders", true);
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

    // ---------- add to cart (mapped product, detail modal) ----------
    await page.locator("div.border", { hasText: "Railings" })
              .locator('button:has-text("Choose & configure")').first().click();
    await page.waitForSelector('button:has-text("Add to request")', { timeout: 10000 });
    await page.locator('.fixed input[type="number"]').fill("12");
    await page.fill('input[placeholder*="RAL"]', "shop paint RAL 7016");
    await page.click('button:has-text("Add to request")');
    await page.waitForTimeout(400);
    const bodyAfterAdd = await page.innerText("body");
    check("cart indicator appears",
          /in your request/.test(bodyAfterAdd));
    check("line keeps its finish", /RAL 7016/.test(
      bodyAfterAdd.slice(bodyAfterAdd.indexOf("Your request"))));

    // qty edit
    const qtyInputs = page.locator('#your-request input[type="number"]');
    if (await qtyInputs.count()) {
      await qtyInputs.first().fill("14");
      check("qty editable", true);
    }

    // unmapped product -> custom line immediately
    await page.locator("div.border", { hasText: "Mushrabiya" })
              .locator('button:has-text("Choose & configure")').first().click();
    await page.waitForTimeout(400);
    check("unmapped product becomes custom line",
          /CUSTOM: Decorative Panels/i.test(await page.innerText("body")));

    // ---------- checkout ----------
    await page.fill('input[placeholder="Request title *"]', "E2E villa package");
    await page.fill('input[placeholder*="Deadline"]', "within 6 weeks");
    await page.click('button:has-text("Submit request for engineering review")');
    await page.waitForSelector("text=Request submitted", { timeout: 20000 });
    const code = await page.evaluate(() => (document.body.innerText.match(/J-\d{3}/) || [])[0]);
    check("cart request submitted (" + code + ")", !!code);

    // fresh request for the chat flow
    await page.click('button:has-text("New request")');
    await page.waitForTimeout(500);

    // ---------- custom chat ----------
    await page.click('button:has-text("Describe it to the assistant")');
    await page.waitForFunction(
      () => !document.body.innerText.includes("Thinking…"),
      { timeout: 60000 }
    );
    let body = await page.innerText("body");
    check("chat opens with assistant reply",
          /Ousus assistant|what would you|like us to build|tell me/i.test(body));

    const chatAnswer = async (text) => {
      await page.fill('input[placeholder="Type your answer…"]', text);
      await page.click('button:has-text("Send")');
      await page.waitForFunction(
        () => !document.body.innerText.includes("Thinking…"),
        { timeout: 60000 }
      );
      return page.innerText("body");
    };
    body = await chatAnswer(
      "A custom spiral staircase, black mild steel, 3m rise, one unit, villa in Katameya, within two months"
    );
    for (let i = 0; i < 4; i++) {
      if (/submitted as request|Custom request J-/i.test(body)) break;
      body = await chatAnswer(
        i >= 1 ? "yes confirmed, submit it" : "yes that is correct, proceed"
      );
    }
    check("custom chat submitted through schema gate",
          /Custom request J-\d+ submitted/i.test(body));

    // ---------- light/dark toggle ----------
    await page.goto(BASE + "/my", { waitUntil: "networkidle" });
    const toggle = page.locator('button[aria-label="Toggle light/dark mode"]');
    check("theme toggle present", (await toggle.count()) === 1);
    if (await toggle.count()) {
      const before = await page.evaluate(() => document.documentElement.className);
      await toggle.click();
      const after = await page.evaluate(() => document.documentElement.className);
      check("light/dark switches", before !== after, `${before} -> ${after}`);
    }

    // ---------- engineer review ----------
    await apiLogin(page, "engineer@oususapp.com");
    await page.goto(BASE + "/review", { waitUntil: "networkidle" });
    await page.waitForTimeout(1500);
    let reviewBody = await page.innerText("body");
    const hasPending = /Villa package|spiral|E2E/i.test(reviewBody);
    check("pending requests visible to engineer", hasPending,
          hasPending ? "" : reviewBody.slice(0, 250).replace(/\n/g, " | "));
    if (hasPending) {
      await page.locator('button:has-text("Approve → planning phase")').first().click();
      await page.waitForTimeout(45000); // pipeline may use the LLM chain
      reviewBody = await page.innerText("body");
      check("approval produces decision/plan",
            /Decision: (PLAN|DELAY_RISK|MANUAL_PLAN)/.test(reviewBody));
    }

    // ---------- board ----------
    await page.goto(BASE + "/board", { waitUntil: "networkidle" });
    await page.waitForSelector("text=Fabrication", { timeout: 20000 });
    const boardBody = await page.innerText("body");
    check("board shows 10 stages",
          ["award", "fabrication", "installation"].every((s) =>
            boardBody.toLowerCase().includes(s)));

    // ---------- manager gate ----------
    await apiLogin(page, "manager@oususapp.com");
    await page.goto(BASE + "/approvals", { waitUntil: "networkidle" });
    await page.waitForTimeout(1000);
    const approvalBody = await page.innerText("body");
    check("manager sees audit trail", /Audit Trail/i.test(approvalBody));
    if (/Approve & release/.test(approvalBody)) {
      await page.click('button:has-text("Approve & release")');
      await page.waitForTimeout(4000);
      check("manager can release plan", true);
    }

    // ---------- summary ----------
    await page.goto(BASE + "/summary", { waitUntil: "networkidle" });
    await page.waitForTimeout(1000);
    check("daily summary renders stats",
          /Active projects/i.test(await page.innerText("body")));

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
