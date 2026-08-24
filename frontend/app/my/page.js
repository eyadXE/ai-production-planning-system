"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "../../components/AppShell";
import { api } from "../../lib/api";

export default function MyProjects() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/my/projects").then(setData).catch((e) => setError(e.message));
  }, []);

  if (error) return <AppShell active="My Projects" title="My projects"><div className="text-destructive">{error}</div></AppShell>;
  if (!data) return <AppShell active="My Projects" title="My projects"><p className="font-mono text-xs text-muted-foreground">Loading…</p></AppShell>;

  const stageLabel = (p) =>
    p.release_status === "queued" ? "Plan awaiting management approval"
    : p.status === "blocked_material" ? "Waiting on materials"
    : `In ${p.stage}`;

  return (
    <AppShell active="My Projects" title="My projects"
              subtitle="Every project you have with Ousus, tracked stage by stage.">
      <Link href="/request"
            className="inline-flex items-center gap-2 self-start bg-primary px-4 py-2.5 font-mono text-xs font-bold text-primary-foreground hover:bg-primary/90">
        + New request
      </Link>
      {data.projects.length === 0 && (
        <div className="border border-border bg-card p-5 font-mono text-xs text-muted-foreground">
          No projects yet — request one through the assistant.
        </div>
      )}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {data.projects.map((p) => (
          <div key={p.code} className={`border border-l-2 border-border bg-card p-5 ${p.overdue ? "border-l-destructive" : p.release_status === "released" ? "border-l-primary" : ""}`}>
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs font-bold text-foreground">{p.code}</span>
              {p.overdue && <span className="border border-destructive/40 px-1.5 py-0.5 font-mono text-[9px] text-destructive">DELAYED</span>}
              {p.release_status === "released" && <span className="border border-primary/40 px-1.5 py-0.5 font-mono text-[9px] text-primary">APPROVED</span>}
              {p.release_status === "queued" && <span className="border border-border px-1.5 py-0.5 font-mono text-[9px] text-muted-foreground">IN REVIEW</span>}
            </div>
            <p className="mt-2 font-mono text-xs text-foreground">{p.title}</p>
            <p className="mt-3 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{stageLabel(p)}</p>
            <p className="mt-1 font-mono text-[10px] text-muted-foreground">Target: {p.required_date || "—"}</p>
          </div>
        ))}
      </div>
    </AppShell>
  );
}
