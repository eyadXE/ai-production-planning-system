"use client";

import { useCallback, useEffect, useState } from "react";
import { Hammer } from "lucide-react";
import AppShell from "../../components/AppShell";
import { api } from "../../lib/api";

export default function Review() {
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [results, setResults] = useState({});
  const [decisionLog, setDecisionLog] = useState([]);

  const load = useCallback(async () => {
    try { setItems(await api("/requests/pending")); } catch (e) { setError(e.message); }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function review(code, approve) {
    setBusy(code); setError("");
    try {
      const r = await api(`/requests/${code}/review?approve=${approve}`, { method: "POST" });
      setResults((p) => ({ ...p, [code]: r }));
      setDecisionLog((prev) => [{
        code, decision: r.decision, key_clause: r.key_clause,
        reasons: r.reasons || [], fab_hours: r.fab_hours,
        install_hours: r.install_hours, price: r.final_price_egp,
        approval_id: r.approval_id,
      }, ...prev]);
      await load();
    } catch (e) { setError(e.message); } finally { setBusy(""); }
  }

  return (
    <AppShell active="Requests" title="Engineering review"
              subtitle="Client requests waiting to enter the planning phase.">
      {error && <div className="text-destructive">{error}</div>}

      {decisionLog.length > 0 && (
        <section>
          <h3 className="mb-3 mt-2 font-mono text-sm font-bold uppercase tracking-wider text-muted-foreground">Decisions this session</h3>
          {decisionLog.map((d) => (
            <div key={d.code} className="mb-3 border border-border bg-card p-4">
              <b className="font-mono text-xs text-foreground">{d.code} — Decision: {d.decision}</b>
              <span className="ml-2 border border-border px-1.5 py-0.5 font-mono text-[9px] text-muted-foreground">clause {d.key_clause}</span>
              {d.fab_hours != null && (
                <span className="ml-2 font-mono text-[10px] text-muted-foreground">
                  {d.fab_hours} h fab · {d.install_hours} h install
                  {d.price ? ` · EGP ${Number(d.price).toLocaleString()}` : ""}
                  {d.approval_id ? ` · gate #${d.approval_id}` : ""}
                </span>
              )}
              <ul className="mt-1 list-disc pl-5 font-mono text-[10px] leading-5 text-muted-foreground">
                {d.reasons.map((r, i) => <li key={i}>{r}</li>)}
              </ul>
            </div>
          ))}
        </section>
      )}

      {items.length === 0 && (
        <div className="border border-border bg-card p-5 font-mono text-xs text-muted-foreground">No requests waiting for review.</div>
      )}
      <div className="flex flex-col gap-4">
        {items.map((s) => (
          <section key={s.code} className="border border-border bg-card p-5">
            <div className="flex items-center gap-3">
              <Hammer className="size-4 text-primary" />
              <b className="font-mono text-sm text-foreground">{s.code} — {s.title}</b>
              <span className="ml-auto border border-border px-1.5 py-0.5 font-mono text-[9px] text-muted-foreground">{s.account}</span>
            </div>
            <table className="mt-3 w-full border-collapse">
              <tbody>
                {(s.structured?.items || []).map((it, i) => (
                  <tr key={i} className="border-b border-border last:border-0">
                    <th className="py-1.5 pr-4 text-left font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{it.kind}</th>
                    <td className="py-1.5 font-mono text-xs text-foreground">{it.qty}{it.note ? ` (${it.note})` : ""}</td>
                  </tr>
                ))}
                {[["Finish", s.structured?.finish || "unstated"], ["Site", s.structured?.site || "—"], ["Required", s.structured?.required_raw]].map(([k, v]) => (
                  <tr key={k} className="border-b border-border last:border-0">
                    <th className="py-1.5 pr-4 text-left font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{k}</th>
                    <td className="py-1.5 font-mono text-xs text-muted-foreground">{v}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            {results[s.code] && (
              <div className="mt-3 border border-border bg-background p-4">
                <b className="font-mono text-xs text-foreground">Decision: {results[s.code].decision}</b>
                {results[s.code].fab_hours != null && (
                  <p className="mt-2 font-mono text-[11px] text-muted-foreground">
                    {results[s.code].fab_hours} h fab / {results[s.code].install_hours} h install
                    {results[s.code].final_price_egp ? ` · EGP ${Number(results[s.code].final_price_egp).toLocaleString()}` : ""}
                    {" · "}approval #{results[s.code].approval_id ?? "—"}
                  </p>
                )}
                <ul className="mt-2 list-disc pl-5 font-mono text-[11px] leading-6 text-muted-foreground">
                  {(results[s.code].reasons || []).map((r, i) => <li key={i}>{r}</li>)}
                </ul>
              </div>
            )}

            {!results[s.code] && (
              <div className="mt-4 flex gap-2">
                <button disabled={busy === s.code} onClick={() => review(s.code, true)}
                        className="bg-primary px-4 py-2 font-mono text-xs font-bold text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
                  Approve & send plan to manager
                </button>
                <button disabled={busy === s.code} onClick={() => review(s.code, false)}
                        className="border border-destructive/40 px-4 py-2 font-mono text-xs text-destructive hover:bg-destructive/10 disabled:opacity-50">
                  Reject
                </button>
              </div>
            )}
          </section>
        ))}
      </div>
    </AppShell>
  );
}
