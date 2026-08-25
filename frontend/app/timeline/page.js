"use client";

import { useEffect, useState } from "react";
import { CalendarDays } from "lucide-react";
import AppShell from "../../components/AppShell";
import { api } from "../../lib/api";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function weekLabelToDate(label) {
  const [y, w] = label.split("-W").map(Number);
  // Monday of ISO week
  const jan4 = new Date(Date.UTC(y, 0, 4));
  const day = jan4.getUTCDay() || 7;
  const monday = new Date(jan4);
  monday.setUTCDate(jan4.getUTCDate() - day + 1 + (w - 1) * 7);
  return monday;
}

export default function Timeline() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/timeline").then(setData).catch((e) => setError(e.message));
  }, []);

  if (error) return <AppShell active="Timeline" title="Timeline"><div className="text-destructive">{error}</div></AppShell>;
  if (!data) return <AppShell active="Timeline" title="Timeline"><p className="font-mono text-xs text-muted-foreground">Loading…</p></AppShell>;

  // build a continuous list of weeks: from earliest capacity week to +12 months
  const start = data.weeks.length
    ? weekLabelToDate(data.weeks[0].week)
    : new Date();
  const totalWeeks = Math.max(data.weeks.length, 60); // scroll ~14 months
  const allWeeks = [];
  for (let i = 0; i < totalWeeks; i++) {
    const d = new Date(start);
    d.setUTCDate(d.getUTCDate() + i * 7);
    const y = d.getUTCFullYear();
    const jan4 = new Date(Date.UTC(y, 0, 4));
    const day = jan4.getUTCDay() || 7;
    const w = Math.ceil(((d - jan4) / 86400000 + day) / 7);
    const label = `${y}-W${String(w).padStart(2, "0")}`;
    const cap = data.weeks.find((x) => x.label === label);
    allWeeks.push({
      label,
      month: MONTHS[d.getUTCMonth()],
      year: y,
      free: cap ? cap.free_hours : null,   // null = beyond known capacity
      total: cap ? cap.total_hours : 320,
    });
  }

  // per project: set of fab weeks + install week
  const rows = data.projects.map((p) => ({
    ...p,
    fabSet: new Set((p.fab_weeks || []).map(([w]) => w)),
    install: p.install_week,
  }));

  let lastMonth = "";
  const runningCount = rows.filter((r) =>
    r.fabSet.size > 0 || r.install).length;

  return (
    <AppShell active="Timeline" title="Production calendar"
              subtitle={`${rows.length} projects · ${allWeeks.length} weeks · scroll sideways through the months. Empty columns are open capacity.`}>
      <div className="overflow-x-auto border border-border bg-card">
        {/* header */}
        <div className="min-w-[1400px]">
          <div className="flex border-b border-border">
            <div className="sticky left-0 z-20 w-64 shrink-0 bg-card px-4 py-3 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
              Project / Client
            </div>
            {allWeeks.map((w, i) => {
              const showMonth = w.month !== lastMonth;
              lastMonth = showMonth ? w.month : lastMonth;
              return (
                <div key={w.label}
                     title={`${w.label} — ${w.free != null ? w.free + "h free" : "beyond current plan"}`}
                     className={`w-12 shrink-0 border-l border-border px-1 pt-2 text-center ${showMonth ? "border-t-2 border-t-primary" : ""}`}>
                  {showMonth && (
                    <p className="font-mono text-[9px] font-bold text-primary">{w.month} {String(w.year).slice(2)}</p>
                  )}
                  <p className={`mt-1 font-mono text-[9px] ${w.free === 0 ? "text-destructive" : "text-muted-foreground"}`}>
                    W{w.label.split("-W")[1]}
                  </p>
                  <div className={`mx-auto mt-1 h-1 w-full ${w.free === 0 ? "bg-destructive" : w.free != null && w.free < w.total * 0.25 ? "bg-chart-3" : "bg-border"}`} />
                </div>
              );
            })}
          </div>

          {/* rows */}
          {rows.map((p) => (
            <div key={p.code} className="flex border-b border-border last:border-0 hover:bg-secondary/30">
              <div className="sticky left-0 z-10 w-64 shrink-0 bg-card px-4 py-3">
                <span className="font-mono text-xs font-bold text-foreground">{p.code}</span>
                {p.overdue && <span className="ml-1 border border-destructive/40 px-1 py-0.5 font-mono text-[8px] text-destructive">OD</span>}
                <p className="font-mono text-[9px] leading-4 text-muted-foreground">{p.title}</p>
                <p className="font-mono text-[9px] text-chart-2">{p.engineer || "unassigned"}</p>
              </div>
              {allWeeks.map((w) => {
                const fab = p.fabSet.has(w.label);
                const inst = p.install === w.label;
                return (
                  <div key={w.label} className="w-12 shrink-0 border-l border-border/50 py-3">
                    {fab ? (
                      <div className="mx-auto h-5 w-[85%] rounded-sm bg-primary"
                           title={`${p.code} fabrication (${w.label})`} />
                    ) : inst ? (
                      <div className="mx-auto h-5 w-[85%] rounded-sm bg-chart-2"
                           title={`${p.code} delivery & installation (${w.label})`} />
                    ) : null}
                  </div>
                );
              })}
            </div>
          ))}

          {/* empty capacity strip */}
          <div className="flex border-t-2 border-border">
            <div className="sticky left-0 z-10 w-64 shrink-0 bg-card px-4 py-2 font-mono text-[9px] uppercase tracking-wider text-muted-foreground">
              Open slots (free hours)
            </div>
            {allWeeks.map((w) => {
              const cap = data.weeks.find((x) => x.label === w.label);
              return (
                <div key={w.label}
                     className={`w-12 shrink-0 border-l border-border/40 py-2 text-center font-mono text-[8px] ${cap && cap.free_hours <= 0 ? "text-destructive" : "text-muted-foreground"}`}
                     title={cap ? `${cap.free_hours}h free` : "not yet planned"}>
                  {cap ? cap.free_hours : "—"}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-5 font-mono text-[10px] text-muted-foreground">
        <span><i className="mr-1 inline-block size-2 bg-primary" />Fabrication</span>
        <span><i className="mr-1 inline-block size-2 bg-chart-2" />Delivery &amp; installation</span>
        <span><i className="mr-1 inline-block size-2 bg-destructive" />Fully booked week</span>
        <span>Scroll right → into next year</span>
      </div>
    </AppShell>
  );
}
