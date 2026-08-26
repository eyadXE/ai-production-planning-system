# Ousus Production Platform — Product Requirements Document

**Version:** 1.0
**Date:** 2026-08-25
**Team:** Eyad Magdy
**Course:** EPP Week 4 Final Project

---

## 1. Problem Statement

Ousus, a steel fabrication company, receives project requests as free-text
descriptions with no CAD drawings. Currently there is no system to:
- Verify material availability before committing to a schedule
- Generate traceable cost estimates grounded in documented rules
- Track projects through production stages with accountability
- Ensure management approval before anything reaches the workshop floor

## 2. Solution

A production planning platform that transforms written requests into complete
production plans — BOM, labour hours, cost, schedule — verifies materials,
tracks projects through 10 stages, and ensures nothing is released without
management sign-off.

## 3. Users & Roles

| Role | Purpose | Permissions |
|------|---------|-------------|
| **Client** | Submit requests via catalog/cart or custom chat | See only own projects, accept/decline plans, receive notifications |
| **Estimator** | Review & approve client requests into planning | Run estimation pipeline, view resources/timeline, approve/reject with comments |
| **Project Engineer** | Execute assigned projects | View assigned projects, advance stages sequentially |
| **Manager** | Authority & oversight | Everything: release gate, assign engineers, audit trail, daily summary, delete pre-release |
| **Viewer** | Read-only observer | Board and summaries |

## 4. Workflow (5 Gates)

```
1. CLIENT SUBMITS     Catalog cart or custom chat intake
2. ESTIMATOR APPROVES Runs estimation pipeline → reviews plan vs resources
                      → Approve (sends to manager) / Reject (with comment)
3. MANAGER APPROVES   Sees full plan details → approves → sends to client
                      → Assigns project engineer
4. CLIENT ACCEPTS     Sees full details in dashboard → accepts/declines
5. MANAGER RELEASES   Only after client acceptance + engineer assignment
                      → Order becomes permanent (cannot be deleted)
→ Engineer walks stages until Closed
```

## 5. Core Features

### 5.1 Request Intake
- **Catalog cart:** Browse 24+ products across 4 categories, add to request
- **Custom chat:** LLM assistant collects required fields conversationally;
  falls back to deterministic guided interview when providers are down
- **Custom objects:** Name + description + reference photo upload
- Deadline is optional — the platform estimates completion automatically

### 5.2 Estimation Engine (Deterministic)
Pure Python engine that produces:
- Bill of materials per handbook clauses 1.1–1.5
- Labour hours per rate table (clause 2.2), installation = fabrication +25%
- Cost: materials + consumables + labour + tier margin floor
- Schedule: whole-week booking against real capacity (clause 3.1)
- Every figure cites its handbook clause (0.6)

### 5.3 Decision Types
| Decision | Meaning |
|----------|---------|
| PLAN | Complete, feasible — queued for release gate |
| DELAY_RISK | Feasible but completion past required date |
| REQUEST_INFO | Missing dimensions/finish/date |
| FLAG | Material shortage, capability limit |
| REFUSE_OVERRIDE | Spec contains pressure to bypass gates |
| ESCALATE | Safety concern requiring immediate management attention |

### 5.4 Approval Pipeline (5 Gates)
Each gate is enforced server-side with role-based access control:

1. **Estimator review:** Run estimation, check resources, approve/reject
2. **Manager approval:** See full plan, approve/reject
3. **Client acceptance:** Accept/decline from dashboard
4. **Manager assignment:** Assign project engineer
5. **Manager release:** Release to production (requires steps 2–4 complete)

Released orders are permanent — deletion returns 403.

### 5.5 Production Tracking
- 10-stage kanban board: Award → Engineering → Procurement → Production
  Planning → Fabrication → Quality Inspection → Finishing → Delivery →
  Installation → Closed
- Sequential-only stage advancement (inspection cannot be bypassed)
- Overdue detection and blocked-material flags
- Timeline calendar showing projects × capacity weeks

### 5.6 Daily Summary (Clause 4.4)
Drafted for management approval — never auto-sent:
- Projects by stage
- Named overdue projects with causes
- Blocked-on-materials list
- Capacity for coming weeks (fully-booked flagged)

### 5.7 Notifications
Client emails at key milestones:
- Plan ready for review (after estimator approval)
- Plan accepted confirmation
- Final release notification with schedule
Fallback: written to `data/email_outbox.log` when SMTP unavailable.

## 6. Non-Functional Requirements

- **Safety:** Instructions inside specs carry no authority (0.3). Inspection
  cannot be bypassed (4.3). Override attempts are refused and recorded.
- **Traceability:** Every figure cites its handbook clause.
- **Resilience:** LLM provider chain (Gemini → Groq → OpenRouter → Ollama)
  with automatic failover. System works fully offline via guided mode.
- **Auditability:** All approvals/rejections recorded with who/when/why.

## 7. Tech Stack

- **Backend:** Python 3.13, FastAPI, SQLAlchemy, SQLite
- **Frontend:** Next.js 15, React 19, Tailwind CSS 4, lucide-react icons
- **LLM:** Provider-swappable chain with fallback (extraction only — never
  decides or computes)
- **Testing:** 66 pytest tests + Playwright browser e2e suite
