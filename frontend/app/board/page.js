"use client";

import { useCallback, useEffect, useState } from "react";
import { ArrowRight, MoreHorizontal } from "lucide-react";
import AppShell from "../../components/AppShell";
import { api, getUser } from "../../lib/api";

const BADGE = {
  overdue: "border border-destructive/40 text-destructive",
  blocked: "border border-chart-2/40 text-chart-2",
  released: "border border-primary/40 text-primary",
  queued: "border border-border text-muted-foreground",
};

export default function Board() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const isManager = getUser()?.role === "manager";

  const load = useCallback(async () => {
    try { setData(await api("/board")); } catch (e) { setError(e.message); }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function advance(code) {
    setBusy(code); setError("");
    try { await api(`/projects/${code}/stage`, { method: "PATCH", body: {} }); await load(); }
    catch (e) { setError(e.message); } finally { setBusy(""); }
  }

  async function remove(code) {
    if (!confirm(`Delete project ${code}? This cannot be undone.`)) return;
    setBusy(code); setError("");
    try { await api(`/projects/${code}`, { method: "DELETE" }); await load(); }
    catch (e) { setError(e.message); } finally { setBusy(""); }
  }

  const badgeFor = (p) => {
    if (p.overdue) return <span className={`px-1.5 py-0.5 font-mono text-[9px] ${BADGE.overdue}`}>OVERDUE</span>;
    if (p.status === "blocked_material") return <span className={`px-1.5 py-0.5 font-mono text-[9px] ${BADGE.blocked}`}>BLOCKED</span>;
    if (p.release_status === "released") return <span className={`px-1.5 py-0.5 font-mono text-[9px] ${BADGE.released}`}>RELEASED</span>;
    if (p.release_status === "queued") return <span className={`px-1.5 py-0.5 font-mono text-[9px] ${BADGE.queued}`}>IN GATE</span>;
    return null;
  };

  return (
    <AppShell active="Projects" title="Projects"
              subtitle="Live pipeline across the ten production stages.">
      {error && <div className="text-destructive">{error}</div>}
      {!data ? <p className="font-mono text-xs text-muted-foreground">Loading…</p> : (
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
                  {(data.columns[stage] || []).map((p) => (
                    <div key={p.code} className="border border-border bg-secondary p-3">
                      <div className="flex items-start justify-between gap-2">
                        {badgeFor(p)}
                        <MoreHorizontal className="size-3 text-muted-foreground" />
                      </div>
                      <p className="mt-3 font-mono text-[11px] font-bold leading-relaxed text-foreground">{p.code}</p>
                      <p className="mt-1 font-mono text-[9px] text-muted-foreground">{p.title}</p>
                      <div className="mt-2 flex items-center justify-between font-mono text-[9px] text-muted-foreground">
                        <span>req: {p.required_date || "—"}</span>
                      </div>
                      {p.stage !== "Closed" && (
                        <button onClick={() => advance(p.code)} disabled={busy === p.code}
                                className="mt-3 flex w-full items-center justify-center gap-1 border border-border py-1.5 font-mono text-[9px] text-muted-foreground hover:border-primary hover:text-primary disabled:opacity-50">
                          Advance <ArrowRight className="size-3" />
                        </button>
                      )}
                      {isManager && (
                        <button onClick={() => remove(p.code)} disabled={busy === p.code}
                                className="mt-1 flex w-full items-center justify-center border border-destructive/30 py-1.5 font-mono text-[9px] text-destructive hover:bg-destructive/10 disabled:opacity-50">
                          Delete
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </AppShell>
  );
}
