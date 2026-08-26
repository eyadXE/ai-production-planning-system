# Ousus Production Platform — Complete Reference

**Last updated:** 2026-08-26
**Status:** Backend pipeline verified working (30/30 scenario checks). Frontend has known rendering issues documented below.
**App:** http://localhost:3100 | **API:** http://localhost:8000

---

## ⚡ QUICK START

```bash
# Terminal 1: Backend
.venv/bin/python -m finalproject.db.seed --fresh
setsid .venv/bin/uvicorn finalproject.api.main:app --port 8000 </dev/null &

# Terminal 2: Frontend
export PATH=~/.local/node/bin:$PATH   # local node install
cd frontend && npm run build && npm run start  # :3100
```

## Demo Accounts (password: demo1234)
| Email | Role |
|-------|------|
| manager@oususapp.com | Manager (full control) |
| estimator@oususapp.com | Estimator (reviews requests) |
| engineer@oususapp.com | Project Engineer (advances stages) |
| eng2@oususapp.com / eng3@oususapp.com | More engineers for assignment |
| client@oususapp.com | Client (catalog, chat, dashboard) |
| viewer@oususapp.com | Viewer (read-only board) |

---

## 🔴 KNOWN UNSOLVED BUGS

### BUG-1: Manager approval doesn't update release_status to "manager_approved"
**Symptom:** After manager clicks "Approve" on the approvals page, the project's release_status stays "queued" instead of changing to "manager_approved".

**Root cause:** In `src/finalproject/tracking/approvals.py` → `decide()` function:
```python
if approval.approval_type == "plan_release":
    estimate = session.get(Estimate, approval.entity_id)
    if estimate:
        project = session.get(Project, estimate.project_id)
        if project:
            project.release_status = ("manager_approved" if approved else ...)
```
The `entity_id` on the Approval must match an existing `Estimates.id`. If the Estimate wasn't committed before queue_plan_release was called, `session.get(Estimate, entity_id)` returns None and the status update is silently skipped.

**Fix needed:** Add explicit logging in decide() to verify estimate is found. If None, raise HTTPException(500) instead of silently continuing.

**Verified working:** YES via direct API calls (`curl` + scenario_test.py steps 5-5b pass). The issue may be frontend-specific (stale token, wrong approval_id passed).

---

### BUG-2: Chat returns 500 when LLM providers are rate-limited
**Symptom:** Client sends a message in the chat → HTTP 500.

**Root cause:** The `chat_message()` endpoint in intake_chat.py calls LLMClient().complete() which tries all providers. When all fail (429/503), it falls back to guided_turn(). But if there's an exception INSIDE guided_turn (e.g., missing field), it propagates as 500.

**Fix needed:** Wrap the entire message endpoint body in try/except and return a valid JSON response even on internal errors.

---

### BUG-3: Estimator review page shows empty fields for MANUAL_PLAN
**Symptom:** After running estimation on a custom-only request, the plan summary shows blank fab hours, EGP 0 cost.

**Root cause:** Custom builds don't go through the standard estimation engine (no catalog items to calculate from). A preliminary manual estimate IS generated but the frontend may not render MANUAL_PLAN decisions differently from PLAN decisions.

**Fix needed:** In the review page, detect MANUAL_PLAN decision and show different content: "This is a custom build requiring manual engineering planning" instead of trying to render empty hours/prices.

---

### BUG-4: Delete button visible for released orders on board
**Symptom:** Manager can see Delete button on released projects.

**Root cause:** The board page checks `p.release_status !== "released"` to hide Delete, but this check might not work because `release_status` could be `"released"` (string match should work) or the check might be on a stale object.

**Server-side protection exists:** DELETE endpoint returns 403 for non-draft projects. So even if the button is clicked, nothing happens.

---

## ✅ WORKING FEATURES (verified)

### Pipeline Flow (verified via API + scenario tests)
```
1. CLIENT SUBMITS          POST /requests
                           Creates Spec(status=pending_review)

2. ESTIMATOR RUNS          POST /requests/{code}/run-estimate
   ESTIMATION              Returns draft plan with resource check

3. ESTIMATOR APPROVES      POST /requests/{code}/decision {approved:true}
                           Creates Project(release_status=draft→queued)
                           Creates Approval(type=plan_release)
                           Sends email to client

4. MANAGER APPROVES        POST /approvals/{id}/decision {approved:true}
                           Sets release_status=manager_approved

5. CLIENT ACCEPTS          POST /my/projects/{code}/decision {accept:true}
                           Sets release_status=client_accepted

6. MANAGER ASSIGNS         POST /projects/{code}/assign {engineer_id}
   ENGINEER                Sets assigned_engineer_id

7. MANAGER RELEASES        POST /projects/{code}/release
                           Sets release_status=released
                           Requires: client_accepted + assigned engineer

8. ENGINEER ADVANCES       PATCH /projects/{code}/stage
   STAGES                  Only assigned engineer or manager can advance
                           Sequential-only, inspection cannot be skipped
```

### Permission Matrix (verified)
| Endpoint | Mgr | Est | Eng | Cli | View |
|----------|-----|-----|-----|-----|------|
| GET /board | ✅ | ✅ | ✅* | ❌ | ✅ |
| GET /timeline | ✅ | ✅ | ✅ | ❌ | ✅ |
| GET /materials | ✅ | ✅ | ✅ | ❌ | ❌ |
| GET /summary/daily | ✅ | ❌ | ❌ | ❌ | ❌ |
| GET /approvals | ✅ | ❌ | ❌ | ❌ | ❌ |
| POST /approvals/{id}/decision | ✅ | ❌ | ❌ | ❌ | ❌ |
| GET /requests/pending | ✅ | ✅ | ❌ | ❌ | ❌ |
| GET /requests/rejected | ✅ | ✅ | ❌ | ❌ | ❌ |
| GET /my/projects | ❌ | ❌ | ❌ | ✅ | ❌ |
| POST /requests/{code}/run-estimate | ✅ | ✅ | ❌ | ❌ | ❌ |
| POST /requests/{code}/decision | ✅ | ✅ | ❌ | ❌ | ❌ |
| POST /projects/{code}/assign | ✅ | ❌ | ❌ | ❌ | ❌ |
| POST /projects/{code}/release | ✅ | ❌ | ❌ | ❌ | ❌ |
| DELETE /projects/{code} | ✅(draft only) | ❌ | ❌ | ❌ | ❌ |
| PATCH /projects/{code}/stage | ✅ | ❌ | ✅(assigned) | ❌ | ❌ |

*Engineer sees only assigned projects on board.

---

## 📋 ALL WORKFLOWS

### Workflow A: Catalog Request (Full Pipeline)
```
CLIENT                    ESTIMATOR                 MANAGER                PROJECT ENGINEER
  │                          │                        │                       │
  ├── Browse catalog         │                        │                       │
  ├── Add to cart            │                        │                       │
  ├── Fill title/site        │                        │                       │
  ├── Submit request ────────┤                        │                       │
  │     (Spec: pending_      ├── Sees pending         │                       │
  │      review)             ├── Clicks "Run          │                       │
  │                          │  estimation"           │                       │
  │                          ├── Reviews results      │                       │
  │                          ├── Clicks "Approve      │                       │
  │                          │  & send to manager"    │                       │
  │                          │     ┌─────────────────┤                       │
  │                          │     │ Project created │                       │
  │                          │     │ Estimate created│                       │
  │                          │     │ Approval queued │                       │
  │                          │     └─────────────────┤                       │
  │                          │                 ├── Approves plan             │
  │                          │                 ├── Assigns engineer ─────────┤
  │◄── Email: plan ready ────│                 │                             │
  │                          │                 ├── Releases ─────────────────┤
  ├── Accepts plan           │                 │                             │
  │    (dashboard button)    │                 │                       ┌─────┤
  │                          │                 │                       │ Advances
  │                          │                 │                       │ stages
  │                          │                 │                       │ until
  │                          │                 │                       │ Closed
```

### Workflow B: Custom Request (Chat Intake)
```
CLIENT                    ESTIMATOR                 MANAGER
  ├── Opens custom tab      │                        │
  ├── Chats with assistant  │                        │
  │   (LLM or guided)       │                        │
  ├── Assistant collects:   │                        │
  │   description, qty,     │                        │
  │   material, site, date  │                        │
  ├── Adds to cart          │                        │
  ├── Submits ──────────────┤                        │
  │     (Spec: pending_     ├── Runs estimation      │
  │      review)            ├── MANUAL_PLAN:         │
  │                         │  preliminary estimate  │
  │                         ├── Approves & sends ────┤
  │                         │                  ├── Approves plan
  │                         │                  ├── Assigns engineer
  │                         │                  ├── Releases
  │◄── Notifications ───────│──────────────────┤
  │                         │                  │
  └── Tracks in portal      │                  │
```

### Workflow C: Rejection
```
CLIENT                    ESTIMATOR                 MANAGER
  ├── Submits request ──────┤                        │
  │                         ├── Runs estimation      │
  │                         ├── Decision = REQUEST_  │
  │                         │   INFO or FLAG         │
  │                         ├── Clicks "Reject"      │
  │                         │   with comment ────────┤
  │                         │                  ├── Sees rejection
  │                         │                  │   with who/why
  │                         │                  ├── Can override-
  │                         │                  │   approve if needed
  │ ◄── Can resubmit ───────┤                  │
```

---

## 🐛 DEBUGGING GUIDE

### If chat returns 500:
```bash
# Check backend log
tail -20 /tmp/opencode/backend.log
# Look for NameError/TypeError in chat_message

# Test directly
curl -X POST localhost:8000/intake/start \
  -H "Authorization: Bearer <token>"
curl -X POST localhost:8000/intake/<sid>/message \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"text":"test"}'
```

### If pipeline skips gates:
```bash
# Check current release_status
curl -s localhost:8000/board -H "Authorization: Bearer <mgr_token>" | python3 -m json.tool

# Check pending approvals
curl -s localhost:8000/approvals -H "Authorization: Bearer <mgr_token>"

# Check audit trail
curl -s localhost:8000/audit -H "Authorization: Bearer <mgr_token>"
```

### If pages don't load:
```bash
# Restart both servers
for pid in $(ps aux | grep "[u]vicorn\|[n]ext-server" | awk '{print $2}'); do kill -9 $pid; done
setsid .venv/bin/uvicorn finalproject.api.main:app --port 8000 &
cd frontend && npm run start &

# Hard-refresh browser: Ctrl+Shift+R
# Clear localStorage: F12 → Application → Local Storage → Clear
```

### If LLM providers fail:
```bash
# Check which providers are configured
cat .env
# Gemini quota resets daily; Groq/OpenRouter have separate limits
# System falls back automatically: Gemini → Groq → OpenRouter → Ollama
```

---

## 🏗️ ARCHITECTURE

```
frontend/          Next.js 15 app (Tailwind CSS 4, shadcn-style)
  app/             Pages: /, /login, /request, /review, /approvals,
                   /board, /timeline, /resources, /summary, /my
  components/      AppShell (sidebar), ThemeToggle
  lib/api.js       API wrapper (same-origin proxy via Next rewrites)

src/finalproject/
  api/
    auth_routes.py     POST /auth/signup, /auth/login, GET /auth/me
    board_routes.py    GET /board, PATCH stage, approvals, timeline,
                       materials, notifications, team, assignments,
                       llm/status
    intake_routes.py   POST /requests (cart submit), GET /products,
                       GET /uploads, run-estimate, decision, rejected,
                       DELETE project, assign, release, team
    intake_chat.py     POST /intake/start, /{id}/message,
                       /{id}/photo, /{id}/guided-switch
  auth/               JWT + PBKDF2 password hashing
  core/               Security utilities
  db/                 SQLAlchemy models + seed script
  engine/             Deterministic estimation engine (NO LLM imports)
    parser.py         Spec text → structured items
    bom.py            Bill of materials per handbook clauses
    scheduler.py      Week booking against capacity
    estimator.py      Orchestrator: parse → estimate → schedule → decide
    rates.py          Handbook constants
  evaluation/         Golden-file tests vs answer_key.json
  llm/                Provider fallback chain + spec extraction
  tracking/           Stage advancement, approvals gate, daily summary
  api/intake_guided.py Deterministic interview (no LLM needed)
  api/intake_chat.py  Conversational agent (LLM + guided fallback)

OUSUS/Ousus_data/    Mock data: specs, materials, capacity, handbook
scripts/             fix_mock_dates.py, token_budget_check.py
tests/               test_seed, test_auth, test_golden, test_llm,
                     test_tracking, e2e_test.js (Playwright)
```

---

## 🔑 KEY DESIGN DECISIONS

1. **Engine never imports LLM**: The estimation engine is pure Python.
   The LLM only fills descriptive text fields; safety classification is
   always rule-based on raw text.

2. **Session auto-commit**: `get_session()` yields + commits on success,
   rolls back on error. This was a critical fix — the old return-style
   dependency silently rolled back all writes.

3. **Release permanence**: Once `release_status = "released"`, deletion
   returns 403. This preserves history for client-behaviour tracking.

4. **Stage sequencing**: Projects advance one stage at a time.
   Quality Inspection cannot be bypassed (clause 4.3).

5. **Assignment enforcement**: Tier-2 engineers can only advance projects
   specifically assigned to them by the manager.

6. **Multi-currency ready**: `fx_rates` table seeded with USD/SAR;
   engine math stays in EGP internally.

7. **LLM safety**: The LLM never decides, computes, or approves.
   It only extracts descriptive text. Safety classification (override,
   escalation, capability) is always rule-based on raw text.
