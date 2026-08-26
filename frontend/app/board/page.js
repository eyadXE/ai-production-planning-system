"use client";

import { useCallback, useEffect, useState } from "react";
import { ArrowRight } from "lucide-react";
import AppShell from "../../components/AppShell";
import { api, getUser } from "../../lib/api";

export default function Board() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setUser(getUser());
    setReady(true);
  }, []);

  // only project engineers act on the board — manager is view-only here
  const canAct = user?.role === "engineer";

  const load = useCallback(async () => {
    try {
      setData(await api("/board"));
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function advance(code) {
    setBusy(code); setError("");
    try {
      await api(`/projects/${code}/stage`, { method: "PATCH", body: {} });
      await load();
    } catch (e) { setError(e.message); } finally { setBusy(""); }
  }

  if (!ready || !user) return null;

  function badgeFor(p) {
    if (p.overdue)
      return <span className="border border-destructive/40 px-1.5 py-0.5 font-mono text-[9px] text-destructive">OVERDUE</span>;
    if (p.status === "blocked_material")
      return <span className="border border-chart-2/40 px-1.5 py-0.5 font-mono text-[9px] text-chart-2">BLOCKED</span>;
    if (p.release_status === "released")
      return <span className="border border-primary/40 px-1.5 py-0.5 font-mono text-[9px] text-primary">RELEASED</span>;
    if (p.release_status === "pending_manager_review")
      return <span className="border border-border px-1.5 py-0.5 font-mono text-[9px] text-muted-foreground">MANAGER REVIEW</span>;
    if (p.release_status === "queued")
      return <span className="border border-chart-2/40 px-1.5 py-0.5 font-mono text-[9px] text-chart-2">AWAITING CLIENT</span>;
    if (p.release_status === "client_accepted")
      return <span className="border border-primary/40 px-1.5 py-0.5 font-mono text-[9px] text-primary">READY TO RELEASE</span>;
    return null;
  }

  return (
    <AppShell active="Projects" title="Projects"
              subtitle={canAct ? "Live pipeline — advance stages as work completes." : "View-only board."}>
      {error && <div className="text-destructive">{error}</div>}
      {!data ? (
        <p className="font-mono text-xs text-muted-foreground">Loading…</p>
      ) : (
        <div className="overflow-x-auto border border-border bg-card">
          <div className="grid min-w-[1240px] grid-cols-10 gap-px bg-border">
            {data.stages.map((stage) => (
              <div key={stage} className="bg-card">
                <div className="flex items-center justify-between border-b border-border px-3 py-3">
                  <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{stage}</span>
                  <span className="font-mono text-[10px] text-primary">
                    {String((data.columns[stage] || []).length).padStart(2, "0")}
                  </span>
                </div>
                <div className="flex min-h-[430px] flex-col gap-2 p-2">
                  {(data.columns[stage] || []).map((p) => {
                    const canAdvanceThis =
                      canAct && p.stage !== "Closed" &&
                      (p.assigned_engineer === user?.full_name ||
                       !p.assigned_engineer);
                    return (
                      <div key={p.code} className="border border-border bg-secondary p-3">
                        <div className="flex items-start justify-between gap-2">
                          {badgeFor(p)}
                        </div>
                        <p className="mt-3 font-mono text-[11px] font-bold leading-relaxed text-foreground">{p.code}</p>
                        <p className="mt-1 font-mono text-[9px] text-muted-foreground">{p.title}</p>
                        <div className="mt-2 font-mono text-[9px] text-muted-foreground">
                          req: {p.required_date || "—"}
                          {p.assigned_engineer && <div>eng: {p.assigned_engineer}</div>}
                        </div>
                        {canAdvanceThis && p.stage !== "Closed" && (
                          <button onClick={() => advance(p.code)} disabled={busy === p.code}
                                  className="mt-3 flex w-full items-center justify-center gap-1 border border-border py-1.5 font-mono text-[9px] text-muted-foreground hover:border-primary hover:text-primary disabled:opacity-50">
                            Advance <ArrowRight className="size-3" />
                          </button>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </AppShell>
  );
}
