"use client";

import { useEffect, useState } from "react";
import { CalendarDays } from "lucide-react";
import AppShell from "../../components/AppShell";
import { api } from "../../lib/api";

export default function Timeline() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/timeline").then(setData).catch((e) => setError(e.message));
  }, []);

  if (error) return <AppShell active="Timeline" title="Timeline"><div className="text-destructive">{error}</div></AppShell>;
  if (!data) return <AppShell active="Timeline" title="Timeline"><p className="font-mono text-xs text-muted-foreground">Loading…</p></AppShell>;

  const weekLabels = data.weeks.map((w) => w.label);

  // which weeks each project occupies
  function barsFor(p) {
    const fabWeeks = p.fab_weeks || [];           // [[label, hours], ...]
    const labels = fabWeeks.map(([w]) => w);
    if (p.install_week && !labels.includes(p.install_week)) labels.push(p.install_week);
    return labels;
  }

  return (
    <AppShell active="Timeline" title="Production timeline"
              subtitle="Every project mapped over the coming capacity weeks — who builds what, and when.">
      <div className="overflow-x-auto border border-border bg-card">
        <table className="w-full border-collapse min-w-[1100px]">
          <thead>
            <tr className="border-b border-border">
              <th className="sticky left-0 z-10 bg-card px-4 py-3 text-left font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                Project / Client</th>
              <th className="px-3 py-3 text-left font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Engineer</th>
              <th className="px-3 py-3 text-left font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Stage</th>
              {weekLabels.map((w) => {
                const free = data.weeks.find((x) => x.label === w)?.free_hours ?? 0;
                return (
                  <th key={w}
                      title={`${w} · ${free}h free`}
                      className={`px-2 py-3 text-center font-mono text-[10px] ${free <= 0 ? "text-destructive" : "text-muted-foreground"}`}>
                    {w.split("-W")[1]}
                  </th>
                );
              })}
              <th className="px-3 py-3 text-left font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Est. finish</th>
            </tr>
          </thead>
          <tbody>
            {data.projects.map((p) => {
              const occupied = new Set(barsFor(p));
              return (
                <tr key={p.code} className={`border-b border-border last:border-0 ${p.overdue ? "bg-destructive/5" : ""}`}>
                  <td className="sticky left-0 z-10 bg-card px-4 py-3">
                    <span className="font-mono text-xs font-bold text-foreground">{p.code}</span>
                    <span className="ml-2 font-mono text-[10px] text-muted-foreground">{p.client || p.title}</span>
                    {p.release_status === "released" &&
                      <span className="ml-1 border border-primary/40 px-1 py-0.5 font-mono text-[8px] text-primary">REL</span>}
                    {p.overdue && <span className="ml-1 border border-destructive/40 px-1 py-0.5 font-mono text-[8px] text-destructive">OD</span>}
                  </td>
                  <td className="px-3 py-3 font-mono text-[11px]">
                    {p.engineer ? (
                      <span className="flex items-center gap-1 text-chart-2"><UserCheck className="size-3" />{p.engineer}</span>
                    ) : <span className="text-muted-foreground">—</span>}
                  </td>
                  <td className="px-3 py-3 font-mono text-[10px] text-muted-foreground">{p.stage}</td>
                  {weekLabels.map((w) => {
                    const isFab = (p.fab_weeks || []).some(([fw]) => fw === w);
                    const isInstall = p.install_week === w;
                    return (
                      <td key={w} className="px-1 py-2 text-center">
                        {isFab ? <div className="mx-auto h-4 w-full bg-primary" title="Fabrication"
                                     style={{ maxWidth: 34 }} />
                              : isInstall ? <div className="mx-auto h-4 w-full bg-chart-2" title="Delivery/install"
                                                  style={{ maxWidth: 34 }} />
                                          : <div className="mx-auto h-4" />}
                      </td>
                    );
                  })}
                  <td className="px-3 py-3 font-mono text-[11px] text-foreground">
                    {p.planned_finish || "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="flex items-center gap-5 font-mono text-[10px] text-muted-foreground">
        <CalendarDays className="size-3.5" />
        <span><i className="mr-1 inline-block size-2 bg-primary" />Fabrication week</span>
        <span><i className="mr-1 inline-block size-2 bg-chart-2" />Delivery / installation</span>
        <span><i className="mr-1 inline-block size-2 bg-destructive" />Fully-booked column header = no capacity</span>
      </div>
      <p className="font-mono text-[10px] leading-5 text-muted-foreground">
        Bars come from the released plans&apos; schedules. Projects without a plan
        yet appear once engineering approves them. Red headers are weeks with
        zero remaining capacity.
      </p>
    </AppShell>
  );
}
