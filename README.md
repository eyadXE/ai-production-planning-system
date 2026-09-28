# AI Production Planning System

AI-assisted production planning & tracking platform, built for **Ousus**, a
steel fabrication company. A client's written request becomes a complete
production plan — materials, labour hours, price, schedule — reviewed by
engineers and released only with management sign-off. Every figure is traced
to a handbook clause; the LLM never computes or approves anything.

**Repo:** github.com/eyadXE/ai-production-planning-system

---

## ⚡ Current state — where we are (session resume notes)

**Last updated:** 2026-08-24. Backend + frontend are feature-complete for P0
and running locally. All 64 tests pass.

### What works end-to-end
1. **Landing page `/`** — Ousus branding (logo pulled from ousus.com), tagline,
   real product catalog overview, About section with photos from their site,
   process timeline.
2. **Auth** — signup is **clients only** (no company code needed: new
   customers get an auto-provisioned direct retail account `AC-xx`;
   existing companies may enter their code). Staff roles
   (engineer/manager/viewer) come only from seeding. JWT auth, PBKDF2 hashes,
   CORS-proof: frontend calls same-origin `/api/*` proxied by Next rewrites.
3. **Services catalog `/request`** (replaced the chat) — 24 seeded products in
   4 categories with images, add-to-request cart with quantities, downloadable
   catalogue PDFs (served from `/catalogs/*.pdf`), **custom objects** with
   description + reference photo upload (`POST /api/uploads` → `data/uploads`).
4. **Engineering review `/review`** — pending requests; approve runs the
   deterministic pipeline on standard items; **custom-only requests route as
   `MANUAL_PLAN`** onto the board for manual engineering.
5. **Estimation engine** (`src/finalproject/engine/`) — pure Python, zero LLM:
   BOM per handbook clauses 1.1–1.5 (waste 8%/10%, consumables 4%), rates §2
   (fab/install +25%, EGP 95/120 h, tier margin floor), scheduler books whole
   weeks (host week ≥50% free, top-up ≤25%, galvanising +2 wk then install
   week), decisions PLAN / REQUEST_INFO / FLAG / DELAY_RISK /
   REFUSE_OVERRIDE / ESCALATE. **27/27 golden tests match answer_key.json.**
6. **LLM layer** (`src/finalproject/llm/`) — extraction-only fallback chain:
   Gemini 2.5-flash → Groq qwen3.6-27b → OpenRouter free → Ollama local.
   Keys live in `.env` (project root, auto-loaded via dotenv).
   Wired into `POST /specs/{code}/estimate` (response has `parsed_by`
   = `llm:gemini` etc., badge shown in UI). Safety classification
   (override/escalation/capability) is ALWAYS rule-based on raw text.
7. **Tracking & gate** — 10-stage kanban (`/board`) with advance (sequential
   only, inspection can't be skipped), overdue/blocked badges; manager-only
   delete; approval queue (`/approvals`) manager-only release gate with audit
   trail; daily summary (`/summary`) matches the DAILY-SUMMARY golden content.
8. **Email notifications** — rich plan details sent from
   `eyadmagdy56@gmail.com` via Gmail SMTP **once `OUSUS_SMTP_PASS` holds a
   Gmail app password** (https://myaccount.google.com/apppasswords). Until
   then emails fall back to `data/email_outbox.log`.
9. **UI** — v0.dev design system merged in (Tailwind 4, shadcn-style tokens),
   sidebar shell, light/dark toggle (persisted), Ousus logo + teal #1cbac8.

### Demo accounts (after seed)
`manager@oususapp.com`, `engineer@oususapp.com`, `client@oususapp.com`,
`viewer@oususapp.com` — password `demo1234`.

---

## Running it

Backend (Python 3.13, standalone `.venv` — parent folder has a broken uv
workspace, so use pip not `uv sync`):

```bash
.venv/bin/pip install -e . pytest python-dotenv python-multipart email-validator
.venv/bin/python -m finalproject.db.seed --fresh     # loads mock data + demo users
setsid .venv/bin/uvicorn finalproject.api.main:app --port 8000 &
```

Frontend (Node 22 lives at ~/.local/node — no sudo on this machine):

```bash
export PATH=~/.local/node/bin:$PATH
cd frontend && npm install && npm run build && npm run start   # :3100
```

Tests: `.venv/bin/python -m pytest tests/ -q` (64 passing)

Kill servers safely: `for pid in $(ps aux | grep "[u]vicorn\|[n]ext" | awk '{print $2}'); do kill -9 $pid; done`
(never `pkill -f uvicorn` — it matches the wrapper shell and hangs the session)

---

## Gotchas learned so far

- Mock data dates were shifted **+7 weeks** (capacity now 2026-W35..W43,
  fully-booked block W37–W40) by `scripts/fix_mock_dates.py` (idempotent);
  spec dates → 2026-08-17. Answer-key rationales remapped consistently.
- LLM model IDs expire fast — if you get 404s, query each provider's
  `/models` endpoint and update `src/finalproject/llm/base.py`.
- `scripts/token_budget_check.py` verifies free-tier quota vs full eval run
  (~17.5k tokens / 27 requests — every free tier covers it alone).
- Golden rule: `engine/` never imports `llm/`. The engine is deterministic;
  the LLM only fills descriptive fields.

---

## Remaining backlog (agreed priorities)

**P0 leftovers**
- [ ] Gmail app password → real email sending (user action)
- [ ] Optional: product-specific photos per catalog item

**Done since last update**
- [x] Estimator (type-1 engineer) vs Project Engineer (type-2) roles:
      estimator reviews requests; manager assigns projects to engineers
      (/assign); engineers follow stages via /my-assignments
- [x] Released/approved orders can never be deleted — permanent history
- [x] Estimated completion computed by the pipeline, shown in client
      portal + emails; client deadline now optional everywhere
- [x] Manager Timeline page (/timeline): capacity-week calendar with every
      project's fabrication/install bars, assigned engineer, est. finish
- [x] Chat hardening: server-side field memory (no re-asking), name derived
      from description, heuristic extraction from the client's own words,
      <think>-stripping JSON parser, auto-switch to deterministic guided
      interview when all LLM providers fail ("Quick form" button too)
- [x] Error boundaries (error.js / global-error.js) — page crashes now show
      a recoverable error with Try Again instead of the dead app screen
- [x] Playwright e2e suite (frontend/e2e_test.js): 20 real-browser checks
      covering signup → catalog → cart → chat → review → gate → board
- [x] Daily summary includes full project register (client, stage,
      status, assigned engineer)
- [x] Rules & escalation scenarios documented: OUSUS/rules_and_escalations.md

**Latest session**
- [x] NEW 5-gate workflow: Client submits → **Estimator** reviews/approves
      (draft plan) → submits to Manager → **Manager approves + assigns
      Project Engineer** → **Client accepts/declines from dashboard** →
      **Manager releases** → Engineer walks stages to closure
- [x] Roles split: estimator (type-1) vs project engineer (type-2);
      role-scoped sidebars (each role sees only its own actions)
- [x] Release protection: released/approved orders can never be deleted
- [x] Estimated completion shown to client everywhere (deadline optional)
- [x] Timeline calendar page (/timeline): capacity weeks × projects grid
- [x] Daily summary now includes full project register (client/stage/status/
      engineer per row); estimator sees resources/timeline view-only
- [x] Real product photos for all 24 catalog items (from ousus.com)
- [x] Chat hardening final: heuristic extraction from client's own words,
      guided-mode fallback that cannot dead-end, auto-derivation of item names

**Known issues / notes**
- Gemini free-tier daily quota exhausts under heavy testing (resets daily);
  Groq/OpenRouter/Ollama carry the load automatically meanwhile
- Browser e2e (frontend/e2e_test.js) covers ~21 checks; staff-login steps
  can be timing-flaky headless — rerun or use curl flows if needed
- If pages ever show stale behavior after rebuilds: fully kill next-server
  and restart (`npm run start` serves the build present AT START TIME)

**P1**
- [ ] Multi-currency quote display (fx_rates table already seeded USD/SAR)
- [ ] CSV export of board/estimates

**P2**
- [ ] Chat-with-plan (ask questions about a released plan)
- [ ] 3D preview of estimated items

## Docs elsewhere in repo
- `OUSUS/data_schema.md` — full DB schema explanation (15 tables)
- `OUSUS/supervisor_answers_decisions.md` — supervisor Q&A + locked decisions
- `OUSUS/supervisor_questions.md` — original question list
- `OUSUS/EPP_W4_FinalProject_Ousus_Production_Platform.docx` — official brief
