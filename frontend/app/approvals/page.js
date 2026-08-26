"use client";

import { useCallback, useEffect, useState } from "react";
import AppShell from "../../components/AppShell";
import { api, getUser } from "../../lib/api";

export default function Approvals() {
  const [items, setItems] = useState([]);
  const [audit, setAudit] = useState([]);
  const [awaitingClient, setAwaitingClient] = useState([]);
  const [readyToRelease, setReadyToRelease] = useState([]);
  const [engineers, setEngineers] = useState([]);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    try {
      setItems(await api("/approvals"));
      setAudit(await api("/audit"));
      const [board, engs] = await Promise.all([
        api("/board"), api("/team/engineers")]);
      setEngineers(engs);
      const all = Object.values(board.columns).flat();
      setAwaitingClient(all.filter((p) => p.release_status === "manager_approved"));
      setReadyToRelease(all.filter((p) => p.release_status === "client_accepted"));
    } catch (e) { setError(e.message); }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function decide(id, approved) {
    setBusy(String(id)); setError("");
    try {
      await api(`/approvals/${id}/decision`, {
        method: "POST", body: { approved, note },
      });
      setNote(""); await load();
    } catch (e) { setError(e.message); } finally { setBusy(""); }
  }

  async function release(code) {
    setBusy(code); setError("");
    try {
      await api(`/projects/${code}/release`, { method: "POST" });
      await load();
    } catch (e) { setError(e.message); } finally { setBusy(""); }
  }

  return (
    <AppShell active="Approvals & Release" title="Approvals & Release"
              subtitle="Gate 1: approve the estimator's plan. Gate 2: release after the client accepts.">
      {error && <div className="text-destructive">{error}</div>}

      <section>
        <h3 className="mb-3 font-mono text-[10px] uppercase tracking-[0.18em] text-primary">
          GATE 1 · Plans awaiting your approval · {items.length}</h3>
        {items.length === 0 ? (
          <div className="border border-border bg-card p-5 font-mono text-xs text-muted-foreground">
            Nothing in the queue. Approved plans move to “Awaiting client”.
          </div>
        ) : items.map((a) => (
          <div key={a.id} className="mb-4 border border-border bg-card p-5">
            <b className="font-mono text-xs text-foreground">#{a.id} · {a.type.replace(/_/g, " ")}</b>
            <p className="mt-1 font-mono text-[10px] text-muted-foreground">{a.note}</p>
            <label className="mb-1 mt-3 block font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Decision note</label>
            <input value={note} onChange={(e) => setNote(e.target.value)}
                   placeholder="materials verified / capacity confirmed…"
                   className="w-full border border-border bg-background px-3 py-2.5 font-mono text-xs text-foreground" />
            <div className="mt-3 flex flex-wrap gap-2 items-end">
              <div>
                <label className="mb-1 block font-mono text-[9px] uppercase text-muted-foreground">Assign engineer</label>
                <select id={"assign-" + a.id} defaultValue=""
                        className="border border-border bg-background px-2 py-2 font-mono text-[11px] text-foreground w-44">
                  <option value="" disabled>Choose…</option>
                  {engineers.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
                </select>
              </div>
              <button disabled={busy === String(a.id)} onClick={() => {
                  const sel = document.getElementById("assign-" + a.id);
                  const eid = sel ? Number(sel.value) : null;
                  if (!eid) { setError("assign an engineer first"); return; }
                  Promise.all([
                    api(`/projects/${a.note.split(" ")[2]}/assign`, { method: "POST", body: { engineer_id: eid } }),
                    decide(a.id, true),
                  ]).catch((e) => setError(e.message));
                }}
                className="bg-primary px-4 py-2.5 font-mono text-xs font-bold text-primary-foreground hover:opacity-90 disabled:opacity-50 self-end">
                Approve &amp; assign → client
              </button>
              <button disabled={busy === String(a.id)} onClick={() => decide(a.id, false)}
                      className="border border-destructive/40 px-4 py-2.5 font-mono text-xs text-destructive hover:bg-destructive/10 disabled:opacity-50 self-end">
                Reject
              </button>
            </div>
          </div>
        ))}
      </section>

      <section className="mt-8">
        <h3 className="mb-3 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
          Awaiting client decision · {awaitingClient.length}</h3>
        {awaitingClient.length === 0 ? (
          <p className="font-mono text-[11px] text-muted-foreground">No plans waiting on clients.</p>
        ) : awaitingClient.map((p) => (
          <div key={p.code} className="mb-2 border border-border bg-card p-3 font-mono text-xs text-muted-foreground">
            {p.code} — {p.title}
          </div>
        ))}
        <p className="mt-2 font-mono text-[10px] leading-5 text-muted-foreground">
          The client sees the full plan (price, hours, schedule) and accepts or
          declines from their dashboard.
        </p>
      </section>

      <section className="mt-8">
        <h3 className="mb-3 font-mono text-[10px] uppercase tracking-[0.18em] text-primary">
          Ready to release · client accepted · {readyToRelease.length}</h3>
        {readyToRelease.length === 0 ? (
          <p className="font-mono text-[11px] text-muted-foreground">Nothing ready yet.</p>
        ) : readyToRelease.map((p) => (
          <div key={p.code} className="mb-3 flex items-center justify-between border border-primary/40 bg-card p-4">
            <span className="font-mono text-xs text-foreground">{p.code} — {p.title}</span>
            <button onClick={() => release(p.code)} disabled={busy === p.code}
                    className="bg-primary px-4 py-2.5 font-mono text-xs font-bold text-primary-foreground hover:opacity-90 disabled:opacity-50">
              Release to production
            </button>
          </div>
        ))}
        <p className="mt-2 font-mono text-[10px] leading-5 text-destructive">
          Released orders are permanent — they can never be deleted.
        </p>
      </section>

      <section className="mt-10">
        <h3 className="mb-3 font-mono text-sm font-bold text-foreground">Audit Trail</h3>
        <div className="overflow-x-auto border border-border bg-card">
          <table className="w-full border-collapse min-w-[700px]">
            <thead><tr className="border-b border-border">
              {["#", "Type", "Decision", "Approver ID", "When (UTC)", "Note"].map((h) => (
                <th key={h} className="px-4 py-3 text-left font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{h}</th>))}
            </tr></thead>
            <tbody>
              {audit.map((a) => (
                <tr key={a.id} className="border-b border-border last:border-0">
                  <td className="px-4 py-3 font-mono text-xs text-foreground">{a.id}</td>
                  <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{a.type}</td>
                  <td className={`px-4 py-3 font-mono text-xs ${a.decision === "approved" ? "text-primary" : a.decision === "rejected" ? "text-destructive" : "text-muted-foreground"}`}>{a.decision}</td>
                  <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{a.approver_id || "—"}</td>
                  <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{(a.at || "").replace("T", " ").slice(0, 19)}</td>
                  <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{a.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </AppShell>
  );
}
