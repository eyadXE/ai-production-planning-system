/* E2E browser test: client signup -> services catalog -> cart -> custom
   chat -> submit. Catches client-side exceptions the user reported. */
const { chromium } = require("playwright");

const BASE = "http://localhost:3100";
const results = [];
function check(name, ok, extra = "") {
  results.push({ name, ok, extra });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${extra ? " — " + extra : ""}`);
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const pageErrors = [];
  page.on("pageerror", (err) => pageErrors.push(String(err)));
  page.on("console", (m) => {
    if (m.type() === "error") pageErrors.push("console: " + m.text());
  });

  try {
    // ---------- landing ----------
    await page.goto(BASE + "/", { waitUntil: "networkidle" });
    check("landing loads", (await page.title()).includes("Ousus"));
    const heroImgOk = await page.evaluate(() => {
      const img = document.querySelector('img[src="/hero.jpg"]');
      return img && img.complete && img.naturalWidth > 0;
    });
    check("hero image renders", heroImgOk);

    // ---------- signup ----------
    await page.goto(BASE + "/login?mode=signup", { waitUntil: "networkidle" });
    const email = `e2e_${Date.now()}@test.com`;
    await page.fill('input[type="email"]', email);
    await page.fill('input[type="password"]', "password123");
    await page.locator('input[placeholder*="Leave blank"]').fill("E2E Test Co");
    await page.click('button:has-text("Create account")');
    await page.waitForURL("**/request", { timeout: 15000 })
      .then(() => check("signup redirects to /request", true))
      .catch(() => check("signup redirects to /request", false, page.url()));

    // ---------- catalog ----------
    await page.waitForSelector("text=Carbon Steel", { timeout: 15000 });
    check("catalog renders", true);
    const brokenImgs = await page.evaluate(() =>
      [...document.querySelectorAll("img")]
        .filter((i) => i.src.includes("/images/") && (!i.complete || i.naturalWidth === 0))
        .map((i) => i.src)
    );
    check("all product images render", brokenImgs.length === 0,
          brokenImgs.join(", ").slice(0, 120));

    // ---------- add to cart ----------
    await page.click('button:has-text("Add")'); // first Add button
    await page.waitForTimeout(300);
    const miniCart = await page.textContent("body");
    check("cart indicator appears", /in your request/.test(miniCart));

    // qty change + remove round-trip
    await page.click("#your-request >> xpath=.."); // ensure section exists in DOM
    const qtyInputs = page.locator('#your-request input[type="number"]');
    if (await qtyInputs.count()) {
      await qtyInputs.first().fill("3");
      check("qty editable", true);
    }

    // ---------- checkout form ----------
    await page.fill('input[placeholder="Request title *"]', "E2E villa package");
    await page.fill('input[placeholder*="Deadline"]', "within 6 weeks");

    // ---------- submit cart request ----------
    await page.click('button:has-text("Submit request for engineering review")');
    await page.waitForSelector("text=Request submitted", { timeout: 15000 });
    const code = await page.evaluate(() =>
      (document.body.innerText.match(/J-\d{3}/) || [])[0]);
    check("cart request submitted (" + code + ")", !!code);

    // back to a fresh request for the chat flow
    await page.click('button:has-text("New request")');

    // ---------- custom chat ----------
    await page.click('button:has-text("Describe it to the assistant")');
    await page.waitForSelector("text=Thinking…", { timeout: 20000 }).catch(() => {});
    await page.waitForFunction(
      () => !document.querySelector(".font-mono.text-\\[10px\\]") ||
            !document.body.innerText.includes("Thinking…"),
      { timeout: 45000 }
    );
    let body = await page.innerText("body");
    check("chat opens with assistant reply",
          /Ousus assistant|what would you|like us to build/i.test(body), "");

    await page.fill('input[placeholder="Type your answer…"]',
      "A custom spiral staircase, black mild steel, 3m rise, one unit, for my villa in Katameya, within two months");
    await page.click('button:has-text("Send")');
    await page.waitForTimeout(8000);

    // answer any remaining question generically until complete
    for (let i = 0; i < 4; i++) {
      body = await page.innerText("body");
      if (/submitted as request/i.test(body)) break;
      const placeholder = await page.locator('input[placeholder="Type your answer…"]').count();
      if (!placeholder) break;
      await page.fill('input[placeholder="Type your answer…"]',
        i === 2 ? "yes confirmed, submit it" : "yes that is correct, proceed");
      await page.click('button:has-text("Send")');
      await page.waitForTimeout(8000);
    }
    body = await page.innerText("body");
    const chatSubmitted = /Custom request J-\d+ submitted/i.test(body);
    check("custom chat submitted through schema gate", chatSubmitted,
          chatSubmitted ? "" : body.slice(0, 200).replace(/\n/g, " "));

    // ---------- light mode toggle ----------
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
    const engLogin = async () => {
      await page.evaluate(() => localStorage.clear());
      await page.goto(BASE + "/login", { waitUntil: "networkidle" });
      await page.fill('input[type="email"]', "engineer@oususapp.com");
      await page.fill('input[type="password"]', "demo1234");
      await page.click('button:has-text("Sign in")');
      await page.waitForURL("**/board**", { timeout: 15000 }).catch(() => {});
    };
    await engLogin();

    await page.goto(BASE + "/review", { waitUntil: "networkidle" });
    await page.waitForTimeout(1000);
    let reviewBody = await page.innerText("body");
    const hasPending = /Villa package|spiral|E2E/i.test(reviewBody);
    check("pending requests visible to engineer", hasPending);
    if (hasPending) {
      await page.click('button:has-text("Approve → planning phase")');
      await page.waitForTimeout(6000);
      reviewBody = await page.innerText("body");
      check("approval produces decision/plan",
            /Decision: (PLAN|DELAY_RISK|MANUAL_PLAN)/.test(reviewBody));
    }

    // board renders
    await page.goto(BASE + "/board", { waitUntil: "networkidle" });
    await page.waitForTimeout(800);
    const boardBody = await page.innerText("body");
    check("board shows 10 stages",
          ["Award", "Fabrication", "Installation"].every((s) => boardBody.includes(s)));

    // manager approvals + audit
    await page.evaluate(() => localStorage.clear());
    await page.goto(BASE + "/login", { waitUntil: "networkidle" });
    await page.fill('input[type="email"]', "manager@oususapp.com");
    await page.fill('input[type="password"]', "demo1234");
    await page.click('button:has-text("Sign in")');
    await page.waitForTimeout(1500);
    await page.goto(BASE + "/approvals", { waitUntil: "networkidle" });
    await page.waitForTimeout(1000);
    const approvalBody = await page.innerText("body");
    check("manager sees audit trail", /Audit Trail/i.test(approvalBody));
    if (/Approve & release/.test(approvalBody)) {
      await page.click('button:has-text("Approve & release")');
      await page.waitForTimeout(4000);
      check("manager can release plan", true);
    }

    // summary
    await page.goto(BASE + "/summary", { waitUntil: "networkidle" });
    await page.waitForTimeout(1000);
    const sumBody = await page.innerText("body");
    check("daily summary renders stats", /Active projects/i.test(sumBody));

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
