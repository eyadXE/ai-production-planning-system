# Ousus Production Platform — Entity Relationship Diagram

## Overview

15 tables in SQLite, managed by SQLAlchemy ORM.

```
┌──────────────┐     ┌──────────────┐
│   accounts   │     │    users     │
│──────────────│     │──────────────│
│ id (PK)      │◄────│ id (PK)      │
│ code         │     │ email        │
│ name         │     │ password_hash│
│ tier         │     │ full_name    │
│ margin_floor │     │ role         │
└──────┬───────┘     │ account_id(FK)│
       │             └──────────────┘
       │ 1..*
       ▼
┌──────────────┐     ┌──────────────┐
│   projects   │     │    specs     │
│──────────────│     │──────────────│
│ id (PK)      │     │ id (PK)      │
│ code         │     │ code         │
│ account_id FK│     │ account_id FK│
│ spec_id FK   │────►│ title        │
│ title        │     │ raw_text     │
│ stage        │     │ structured_  │
│ status       │     │   json       │
│ release_     │     │ source       │
│   status     │     │ status       │
│ required_date│     │ rejection_   │
│ estimated_   │     │   note       │
│   finish     │     │ reviewed_by  │
│ assigned_    │     └──────────────┘
│   engineer_id│
└──────┬───────┘
       │ 1..*
       ├──►┌──────────────┐
       │   │ stage_events │
       │   │──────────────│
       │   │ id (PK)      │
       │   │ project_id FK│
       │   │ stage        │
       │   │ started_at   │
       │   │ planned_     │
       │   │   finish_at  │
       │   │ finished_at  │
       │   └──────────────┘
       │
       ├──►┌──────────────┐     ┌──────────────┐
       │   │  estimates   │     │  bom_lines   │
       │   │──────────────│     │──────────────│
       │   │ id (PK)      │────►│ id (PK)      │
       │   │ project_id FK│     │ estimate_idFK│
       │   │ version      │     │ material_idFK│
       │   │ decision     │     │ qty          │
       │   │ material_cost│     │ waste_pct    │
       │   │ consumables  │     │ line_cost    │
       │   │ fab_hours    │     │ citation     │
       │   │ install_hours│     └──────────────┘
       │   │ labour_cost  │
       │   │ margin       │     ┌──────────────┐
       │   │ final_price  │     │  materials   │
       │   │ citations_   │     │──────────────│
       │   │   json       │     │ id (PK)      │
       │   │ created_by FK│     │ code         │
       │   └──────────────┘     │ name         │
       │                        │ unit         │
       ├──►┌──────────────┐     │ price_egp    │
       │   │ schedule_    │     │ stock_qty    │
       │   │   bookings   │     │ lead_time_wks│
       │   │──────────────│     └──────────────┘
       │   │ id (PK)      │
       │   │ project_id FK│
       │   │ capacity_    │
       │   │   week_id FK │
       │   │ hours        │
       │   │ kind         │
       │   └──────────────┘
       │
       └──►┌──────────────┐
           │  approvals   │
           │──────────────│
           │ id (PK)      │
           │ approval_type│
           │ entity_id    │
           │ approver_idFK│
           │ decision     │
           │ note         │
           │ created_at   │
           └──────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│capacity_weeks│     │notifications │     │chat_sessions │
│──────────────│     │──────────────│     │──────────────│
│ id (PK)      │     │ id (PK)      │     │ id (PK)      │
│ week_label   │     │ user_id FK   │     │ account_id FK│
│ start_date   │     │ account_id FK│     │ user_id FK   │
│ total_hours  │     │ to_email     │     │ purpose      │
│ booked_hours │     │ template     │     │ collected_   │
└──────────────┘     │ payload_json │     │   json       │
                     │ status       │     │ status       │
┌──────────────┐     │ sent_at      │     └──────┬───────┘
│  materials   │     └──────────────┘            │ 1..*
│──────────────│                                 ▼
│ id (PK)      │                      ┌──────────────┐
│ code         │                      │chat_messages │
│ name         │                      │──────────────│
│ category     │                      │ id (PK)      │
│ unit         │                      │ session_id FK│
│ price_egp    │                      │ role         │
│ stock_qty    │                      │ content      │
│ lead_time_   │                      │ created_at   │
│   weeks      │                      └──────────────┘
└──────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ fx_rates     │     │  products    │     │handbook_     │
│──────────────│     │──────────────│     │   clauses    │
│ id (PK)      │     │ id (PK)      │     │──────────────│
│ currency     │     │ category     │     │ id (PK)      │
│ egp_per_unit │     │ name         │     │ clause_no    │
│ updated_at   │     │ description  │     │ title        │
└──────────────┘     │ image        │     │ body_text    │
                     │ est_kind     │     │ section      │
                     │ unit         │     └──────────────┘
                     └──────────────┘
```

## Table Descriptions

### accounts
Client companies. `tier` drives the margin floor: key=18%, standard=22%, retail=28%.

### users
All authenticated users. `role` determines permissions. Clients have `account_id` linking to their company. Staff roles (estimator/engineer/manager/viewer) have NULL account_id.

### materials
Steel inventory. `stock_qty` is checked against BOM demand at planning time (clause 3.4). `lead_time_weeks` blocks scheduling when out of stock.

### capacity_weeks
Weekly fabrication capacity. `booked_hours` grows as plans are scheduled. The scheduler books whole weeks forward from earliest available (clause 3.1).

### specs
Client requests — both file-based and chat-intake. `structured_json` holds extracted fields. `status` tracks: draft → pending_review → approved/rejected/info_requested. `rejection_note` records why rejected and by whom.

### projects
Kanban board entities. `release_status` tracks the 5-gate chain:
`draft` → `queued` → `manager_approved` → `client_accepted` → `released`.
Once `released`, deletion is blocked permanently (403).

### estimates
Versioned production plans. Each has a `decision`, cost breakdown, hours, price, and full clause citations in `citations_json`.

### bom_lines
Bill of materials per estimate. Each line cites its handbook clause with waste percentage.

### schedule_bookings
Which project occupies which capacity week, for how many hours, of what kind (fab/install/galvanising).

### approvals
The safety gate record (clause 0.2). Every plan release requires a manager approval row. `approver_id` + `created_at` form the audit trail.

### notifications
Email queue for client milestones. Delivered via SMTP or written to `data/email_outbox.log`.

### chat_sessions / chat_messages
Intake conversations. `collected_json` holds fields gathered so far.

### products
Catalog items with images, descriptions, and optional estimation mapping (`est_kind`). Unmapped products route as custom manual-plan requests.

### fx_rates
Currency conversion for display only. Engine math stays in EGP.

### handbook_clauses
27 rules parsed from markdown files. Used by RAG search and cited in every estimate figure.
