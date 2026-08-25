"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, Box, CircleDashed, Clock3, Timer, PackageCheck } from "lucide-react";
import AppShell from "../../components/AppShell";
import { api } from "../../lib/api";

function StatCard({ label, value, detail, icon: Icon, tone }) {
  return (
    <div className="border border-border bg-card p-5">
      <div className="flex items-start justify-between">
        <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">{label}</p>
        <Icon className={`size-4 ${tone}`} />
      </div>
      <p className="mt-4 font-mono text-3xl font-bold tracking-tight text-foreground">{value}</p>
      <p className="mt-2 font-mono text-[11px] text-muted-foreground">{detail}</p>
    </div>
  );
}

function IssueList({ title, icon: Icon, items, empty, tone }) {
  return (
    <section className="border border-border bg-card">
      <div className="flex items-center gap-3 border-b border-border p-5">
        <Icon className={`size-4 ${tone}`} />
        <h2 className="font-mono text-sm font-bold text-foreground">{title}</h2>
        <span className="ml-auto font-mono text-[10px] text-muted-foreground">{items.length} items</span>
      </div>
      <div className="flex flex-col">
        {items.length === 0 && (
          <p className="px-5 py-4 font-mono text-xs text-muted-foreground">{empty}</p>
        )}
        {items.map((it) => (
          <div key={it.code} className="flex items-center gap-4 border-b border-border px-5 py-4 last:border-0">
            <div className={`size-1.5 ${tone.replace("text-", "bg-")}`} />
            <div className="min-w-0 flex-1">
              <p className="truncate font-mono text-xs font-semibold text-foreground">{it.code} — {it.title}</p>
              <p className="mt-1 font-mono text-[10px] text-muted-foreground">at {it.stage}</p>
            </div>
            <span className={`font-mono text-[10px] ${tone}`}>{it.detail || ""}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function Summary() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/summary/daily").then(setData).catch((e) => setError(e.message));
  }, []);

  if (error) return <AppShell active="Overview" title="Daily summary"><div className="text-destructive">{error}</div></AppShell>;
  if (!data) return <AppShell active="Overview" title="Daily summary"><p className="font-mono text-xs text-muted-foreground">Loading…</p></AppShell>;

  const maxFree = Math.max(1, ...data.capacity.weeks.map((w) => w.total_hours));

  return (
    <AppShell active="Overview" title="Daily production summary"
              subtitle={data.note}>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Active projects" value={String(data.active_projects)} detail="Across all stages" icon={Box} tone="text-primary" />
        <StatCard label="Overdue" value={String(data.overdue.length)} detail="Needs attention today" icon={AlertTriangle} tone="text-destructive" />
        <StatCard label="Blocked" value={String(data.blocked_on_materials.length)} detail="Waiting on materials" icon={CircleDashed} tone="text-chart-2" />
        <StatCard label="Pending approvals" value={String(data.pending_approvals)} detail="In the release gate" icon={Clock3} tone="text-chart-3" />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.3fr_0.7fr]">
        <section className="border border-border bg-card">
          <div className="border-b border-border p-5">
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Portfolio</p>
            <h2 className="mt-1 font-mono text-lg font-bold text-foreground">Projects by stage</h2>
          </div>
          <div className="grid grid-cols-2 gap-px bg-border sm:grid-cols-5">
            {Object.entries(data.projects_by_stage).filter(([, n]) => n > 0).map(([stage, count], i) => (
              <div key={stage} className="bg-card p-4">
                <div className="mb-5 flex items-center justify-between">
                  <span className="font-mono text-[10px] text-muted-foreground">{String(i + 1).padStart(2, "0")}</span>
                  <span className={`size-2 ${i % 3 === 0 ? "bg-primary" : i % 3 === 1 ? "bg-chart-2" : "bg-chart-3"}`} />
                </div>
                <p className="font-mono text-2xl font-bold text-foreground">{String(count).padStart(2, "0")}</p>
                <p className="mt-1 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{stage}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="border border-border bg-card">
          <div className="border-b border-border p-5">
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Capacity / coming weeks</p>
            <h2 className="mt-1 font-mono text-lg font-bold text-foreground">Fabrication load</h2>
          </div>
          <div className="flex h-48 items-end gap-3 px-6 py-5">
            {data.capacity.weeks.map((w) => {
              const booked = w.booked_hours ?? (w.total_hours - w.free_hours);
              const pct = Math.round((booked / maxFree) * 100);
              const full = w.free_hours <= 0;
              return (
                <div key={w.week} className="flex flex-1 flex-col items-center gap-2" title={`${w.week}: ${w.free_hours}h free`}>
                  <div className={`w-full ${full ? "bg-primary" : "bg-secondary"}`} style={{ height: `${Math.max(pct, 4)}%` }} />
                  <span className="font-mono text-[9px] text-muted-foreground">{w.week.split("-W")[1]}</span>
                </div>
              );
            })}
          </div>
          <div className="flex items-center gap-4 border-t border-border px-5 py-3 font-mono text-[10px] text-muted-foreground">
            <span><i className="mr-1 inline-block size-2 bg-primary" />Fully booked</span>
            <span><i className="mr-1 inline-block size-2 bg-secondary" />Available</span>
            {data.capacity.first_meaningful_free_week && (
              <span className="ml-auto">First free: <b className="text-primary">{data.capacity.first_meaningful_free_week}</b></span>
            )}
          </div>
        </section>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <section className="border border-border bg-card p-5">
          <h3 className="mb-3 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Project register — every active project</h3>
          <table className="w-full border-collapse">
            <thead><tr className="border-b border-border">
              {["Code","Title","Client","Stage","Status","Engineer"].map((h) => (
                <th key={h} className="px-3 py-2 text-left font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{h}</th>))}
            </tr></thead>
            <tbody>
              {(data.projects_detail || []).map((d) => (
                <tr key={d.code} className="border-b border-border last:border-0">
                  <td className="px-3 py-2 font-mono text-xs font-bold text-foreground">{d.code}</td>
                  <td className="px-3 py-2 font-mono text-xs text-foreground">{d.title}</td>
                  <td className="px-3 py-2 font-mono text-[11px] text-muted-foreground">{d.client}</td>
                  <td className="px-3 py-2 font-mono text-[11px] text-muted-foreground">{d.stage}</td>
                  <td className={`px-3 py-2 font-mono text-[11px] ${d.status === "overdue" ? "text-destructive" : d.status === "blocked_material" ? "text-chart-2" : "text-muted-foreground"}`}>{d.status}</td>
                  <td className="px-3 py-2 font-mono text-[11px] text-muted-foreground">{d.engineer || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <IssueList title="Overdue projects" icon={Timer}
                   tone="text-destructive" empty="Nothing overdue."
                   items={data.overdue.map((p) => ({ ...p, detail: p.planned_finish ? `was due ${p.planned_finish}` : "" }))} />
        <IssueList title="Blocked by materials" icon={PackageCheck}
                   tone="text-chart-2" empty="Nothing blocked."
                   items={data.blocked_on_materials.map((p) => ({ ...p, detail: "material lead time" }))} />
      </div>
    </AppShell>
  );
}
