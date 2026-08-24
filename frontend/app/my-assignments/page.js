"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "../../components/AppShell";
import { api, getUser } from "../../lib/api";

export default function MyAssignments() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/my-assignments").then(setData).catch((e) => setError(e.message));
  }, []);

  if (error) return <AppShell active="My Assignments" title="My assignments"><div className="text-destructive">{error}</div></AppShell>;
  if (!data) return <AppShell active="My Assignments" title="My assignments"><p className="font-mono text-xs text-muted-foreground">Loading…</p></AppShell>;

  return (
    <AppShell active="My Assignments" title="My assignments"
              subtitle="Projects the manager assigned to you — follow them through every stage on the board.">
      {data.projects.length === 0 && (
        <div className="border border-border bg-card p-5 font-mono text-xs text-muted-foreground">
          Nothing assigned yet — the manager assigns projects from the Assign page.
        </div>
      )}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {data.projects.map((p) => (
          <Link key={p.code} href="/board"
                className={`block border border-l-2 border-border bg-card p-5 hover:border-primary ${p.overdue ? "border-l-destructive" : ""}`}>
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs font-bold text-foreground">{p.code}</span>
              {p.overdue && <span className="border border-destructive/40 px-1.5 py-0.5 font-mono text-[9px] text-destructive">OVERDUE</span>}
            </div>
            <p className="mt-2 font-mono text-xs text-foreground">{p.title}</p>
            <p className="mt-3 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">At {p.stage}</p>
            <p className="mt-1 font-mono text-[10px] text-muted-foreground">
              Est. finish: {p.estimated_finish || p.required_date || "pending planning"}
            </p>
          </Link>
        ))}
      </div>
    </AppShell>
  );
}
