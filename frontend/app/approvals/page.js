"use client";

import { useCallback, useEffect, useState } from "react";
import { ShieldCheck } from "lucide-react";
import AppShell from "../../components/AppShell";
import { api } from "../../lib/api";

export default function Approvals() {
  const [items, setItems] = useState([]);
  const [audit, setAudit] = useState([]);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    try {
      setItems(await api("/approvals"));
      setAudit(await api("/audit"));
    } catch (e) { setError(e.message); }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function decide(id, approved) {
    setBusy(String(id)); setError("");
    try {
      await api(`/approvals/${id}/decision`, { method: "POST", body: { approved, note } });
      setNote(""); await load();
    } catch (e) { setError(e.message); } finally { setBusy(""); }
  }

  return (
    <AppShell active="Approvals" title="Approval queue — the release gate"
              subtitle="Nothing is released to fabrication and no material is ordered until you approve it here (clause 0.2).">
      {error && <div className="text-destructive">{error}</div>}

      <section>
        <p className="mb-3 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Pending · {items.length}</p>
        {items.length === 0 && (
          <div className="border border-border bg-card p-5 font-mono text-xs text-muted-foreground">Queue is empty.</div>
        )}
        <div className="flex flex-col gap-3">
          {items.map((a) => (
            <div key={a.id} className="border border-border bg-card p-5">
              <b className="font-mono text-xs text-foreground">#{a.id} · {a.type.replace("_", " ")}</b>
              <p className="mt-1 font-mono text-[10px] text-muted-foreground">{a.note}</p>
              <label className="mt-3 block font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Decision note</label>
              <input value={note} onChange={(e) => setNote(e.target.value)}
                     placeholder="materials verified, capacity confirmed…"
                     className="mt-1 w-full border border-border bg-background px-3 py-2 font-mono text-xs text-foreground" />
              <div className="mt-3 flex gap-2">
                <button disabled={busy === String(a.id)} onClick={() => decide(a.id, true)}
                        className="bg-primary px-4 py-2 font-mono text-xs font-bold text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
                  Approve &amp; release
                </button>
                <button disabled={busy === String(a.id)} onClick={() => decide(a.id, false)}
                        className="border border-destructive/40 px-4 py-2 font-mono text-xs text-destructive hover:bg-destructive/10 disabled:opacity-50">
                  Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section>
        <p className="mb-3 mt-2 flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          <ShieldCheck className="size-3.5" /> Audit trail</p>
        <div className="overflow-x-auto border border-border bg-card">
          <table className="w-full border-collapse">
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
