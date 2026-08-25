"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "../../components/AppShell";
import { api } from "../../lib/api";

export default function MyProjects() {
  const [data, setData] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    try {
      setData(await api("/my/projects"));
      setNotifications((await api("/notifications/mine")).notifications);
    } catch (e) { setError(e.message); }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function decide(code, accept) {
    setBusy(code);
    try {
      await api(`/my/projects/${code}/decision`, {
        method: "POST", body: { accept },
      });
      await load();
    } catch (e) { setError(e.message); } finally { setBusy(""); }
  }

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
      {notifications.length > 0 && (
        <section className="mb-5 border border-border bg-card p-5">
          <h3 className="mb-3 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Updates for you</h3>
          <ul className="flex flex-col gap-2">
            {notifications.map((n) => (
              <li key={n.id} className="font-mono text-[11px] leading-5 text-muted-foreground">
                <span className="text-primary">•</span> {n.subject}
              </li>
            ))}
          </ul>
        </section>
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
            <p className="mt-1 font-mono text-[10px] text-muted-foreground">
              {p.estimated_finish ? `Estimated finish: ${p.estimated_finish}` : "Estimated finish: pending planning"}
            </p>
            {p.release_status === "manager_approved" && (
              <div className="mt-3 flex gap-2">
                <button onClick={() => decide(p.code, true)} disabled={busy === p.code}
                        className="bg-primary px-3 py-2 font-mono text-[10px] font-bold text-primary-foreground hover:opacity-90 disabled:opacity-50">
                  Accept plan
                </button>
                <button onClick={() => decide(p.code, false)} disabled={busy === p.code}
                        className="border border-destructive/40 px-3 py-2 font-mono text-[10px] text-destructive disabled:opacity-50">
                  Decline
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </AppShell>
  );
}
