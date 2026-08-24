# Ousus Frontend (Next.js)

```bash
export PATH=~/.local/node/bin:$PATH   # if using the local node install
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev   # http://localhost:3100
```

Demo accounts (after seeding the backend): `manager@oususapp.com`,
`engineer@oususapp.com`, `client@oususapp.com`, `viewer@oususapp.com`
— password `demo1234`.

Pages by role:
- **Board** (engineer/manager/viewer): 10-stage kanban, overdue/blocked/release badges, stage advance
- **Estimate** (engineer/manager): run any spec through the pipeline, see decision, hours, price, schedule, clause citations
- **Approvals** (manager): release gate + audit trail
- **Daily Summary** (engineer/manager): DRAFT_SUMMARY with named overdue/blocked projects and capacity ahead
- **My Projects** (client): own-account status portal only
