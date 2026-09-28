# AI Production Planning System

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-frontend-000000?style=flat-square&logo=next.js&logoColor=white)](https://nextjs.org)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-ORM-D71F00?style=flat-square)]()
[![Tests](https://img.shields.io/badge/tests-68%20passing-brightgreen?style=flat-square)](#tests)

A full-stack AI-assisted production planning and tracking platform, built for
**Ousus**, a steel fabrication company. A client's plain-language request
becomes a complete, auditable production plan — materials, labour hours,
price, schedule — reviewed by engineers and released only with management
sign-off. The interesting engineering decision: **the LLM never computes or
approves anything.** Every number is produced by a deterministic rules engine
and traced back to a specific handbook clause; the LLM's only job is turning
messy natural-language requests into structured input for that engine.

**Repo:** github.com/eyadXE/ai-production-planning-system

---

## The problem

Steel fabrication quoting is normally a slow, manual back-and-forth: a client
describes what they need in plain language, an estimator manually works out
materials, labour, and schedule against a pricing handbook, and nothing is
auditable end-to-end. This platform automates the *structuring* and
*computation* while keeping a human in the loop for every decision that
actually commits the business — that split is the core design constraint the
whole system is built around.

## What it does end-to-end

1. **Landing & catalog** — a public storefront with a real 24-product catalog
   across 4 categories, downloadable spec PDFs, and a cart-style request flow
   supporting both standard products and free-text custom items with photo
   uploads.
2. **Auth** — JWT-based, PBKDF2 password hashing, role-scoped access
   (client / engineer / estimator / manager / viewer). New retail clients
   self-provision on signup; staff roles are seeded, not self-assigned.
3. **Estimation engine** (`src/finalproject/engine/`) — pure Python, **zero
   LLM in the decision path**. Computes a full bill of materials against
   handbook clauses (waste %, consumables %), labour rates, and a scheduler
   that books production capacity by whole weeks against real constraints
   (galvanising lead time, top-up thresholds). Outputs one of six decisions
   (`PLAN` / `REQUEST_INFO` / `FLAG` / `DELAY_RISK` / `REFUSE_OVERRIDE` /
   `ESCALATE`) — never a bare number with no rationale.
4. **LLM layer** (`src/finalproject/llm/`) — extraction only. A 4-provider
   fallback chain (Gemini → Groq → OpenRouter → local Ollama) turns a client's
   free-text request into structured fields for the engine to consume. Safety
   classification (override attempts, escalation triggers) is **always**
   rule-based on the raw text, never delegated to the model.
5. **5-gate workflow** — Client submits → Estimator reviews and drafts a plan
   → Manager approves and assigns a project engineer → Client accepts or
   declines → Manager releases → Engineer walks the job through a 10-stage
   kanban board with sequential, non-skippable inspection gates.
6. **Tracking, audit & notifications** — approval queue with a full audit
   trail, manager-only release/delete controls, daily summary matching a
   golden reference output, and email notifications (Gmail SMTP, with a local
   file fallback when unconfigured).

## Architecture

```
Client request (free text or catalog cart)
        │
        ▼
  Next.js frontend  ──/api/*──►  FastAPI backend
  (same-origin proxy,                 │
   no CORS)                   ┌───────┴────────┐
                               ▼                ▼
                       LLM extraction     Deterministic engine
                       (4-provider          (engine/) — pricing,
                       fallback chain,       scheduling, decisions
                       structured fields         │
                       only — never              ▼
                       computes/approves)   SQLite via SQLAlchemy
                                             (accounts, specs, projects,
                                              stage events, handbook)
```

## Skills demonstrated

- **Full-stack ownership** across a Next.js/Tailwind frontend, a FastAPI
  backend, and a SQLAlchemy data layer, wired together with a same-origin API
  proxy to avoid CORS entirely.
- **Deliberately constraining where AI is allowed to act** — the estimation
  engine is 100% deterministic and unit-tested against a golden answer key;
  the LLM is scoped to extraction only, with a hard architectural rule that
  `engine/` never imports `llm/`.
- **Resilient LLM integration**: a 4-provider fallback chain (Gemini → Groq →
  OpenRouter → local Ollama) so the app degrades gracefully instead of
  failing when one provider's free tier is exhausted or a model ID retires.
- **Golden-file / regression testing methodology** — engine output is
  checked against a fixed answer key covering all decision paths, not just
  spot-checked manually.
- **Multi-stage, role-scoped workflow design** — a 5-gate approval pipeline
  with distinct client/estimator/manager/engineer views, enforced
  server-side, not just hidden in the UI.
- **JWT auth with PBKDF2 hashing**, audit-trailed approvals, and
  irreversible-by-design safeguards (released orders can never be deleted).
- **Debugging a real, easy-to-miss production bug**: a `.gitignore` rule
  meant for Python packaging output (`lib/`) was silently excluding
  `frontend/lib/` from every commit, which meant `npm run build` failed on
  *any* fresh clone of the repository. Diagnosed and fixed, and the three
  missing modules were reconstructed from how every page in the app actually
  called them.

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js, Tailwind CSS 4, shadcn-style component tokens |
| Backend | FastAPI, Pydantic |
| Data | SQLAlchemy ORM, SQLite |
| Auth | PyJWT, PBKDF2 password hashing |
| LLM providers | Gemini 2.5-flash, Groq, OpenRouter (free tier), Ollama (local fallback) |
| Testing | pytest, golden-file regression tests, Playwright e2e |

## Screenshots

*(Screenshots coming soon)*

## Running it

```powershell
python -m venv .venv
.venv\Scripts\pip install -e . pytest python-dotenv python-multipart email-validator
copy .env.example .env
.venv\Scripts\python -m finalproject.db.seed --fresh
.venv\Scripts\uvicorn finalproject.api.main:app --port 8000
# in a second terminal:
cd frontend && npm install && npm run build && npm run start
```

Open `http://localhost:3100`. Full setup, demo account credentials, and a
note on the (synthetic, since the original business data was never pushed to
GitHub) demo dataset: see [`HOW_TO_RUN.md`](HOW_TO_RUN.md).

## Tests

```powershell
.venv\Scripts\python -m pytest tests/ -q
```

68 tests passing: 27 golden-file evaluations of the estimation engine against
a fixed answer key, seeding, auth, tracking-gate enforcement, and LLM-fallback
safety behavior.

## Remaining backlog

**P0**
- [ ] Gmail app password configured → real email sending (currently falls
      back to a local log file)
- [ ] Product-specific photos per catalog item (optional polish)

**P1**
- [ ] Multi-currency quote display (fx_rates table already seeded USD/SAR)
- [ ] CSV export of board/estimates

**P2**
- [ ] Chat-with-plan (ask questions about a released plan)
- [ ] 3D preview of estimated items

## Docs elsewhere in this repo

- [`HOW_TO_RUN.md`](HOW_TO_RUN.md) / [`RUN_COMMANDS.txt`](RUN_COMMANDS.txt) — full local setup
- `OUSUS/data_schema.md` — full DB schema explanation (15 tables)
- `OUSUS/supervisor_answers_decisions.md` — supervisor Q&A + locked decisions
- `OUSUS/EPP_W4_FinalProject_Ousus_Production_Platform.docx` — original project brief
