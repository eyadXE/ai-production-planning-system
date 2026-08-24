"use client";

import { useState } from "react";
import { Gauge } from "lucide-react";
import AppShell from "../../components/AppShell";
import { api } from "../../lib/api";

const SPEC_CODES = Array.from({ length: 27 }, (_, i) => `J-${String(i + 1).padStart(3, "0")}`);

export default function Estimate() {
  const [code, setCode] = useState("J-001");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function run(e) {
    e.preventDefault();
    setBusy(true); setError(""); setResult(null);
    try { setResult(await api(`/specs/${code}/estimate`, { method: "POST" })); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }

  return (
    <AppShell active="Estimator" title="Estimation runner"
              subtitle="Turn any spec into a clause-grounded plan: materials, hours, price, schedule.">
      <form onSubmit={run} className="flex items-end gap-3">
        <div>
          <label className="mb-1 block font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Spec</label>
          <select value={code} onChange={(e) => setCode(e.target.value)}
                  className="border border-border bg-background px-3 py-2.5 font-mono text-xs text-foreground">
            {SPEC_CODES.map((c) => <option key={c}>{c}</option>)}
          </select>
        </div>
        <button disabled={busy} className="flex items-center gap-2 bg-primary px-4 py-2.5 font-mono text-xs font-bold text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
          <Gauge className="size-4" />{busy ? "Running…" : "Run pipeline"}
        </button>
      </form>
      {error && <div className="text-destructive">{error}</div>}

      {result && (
        <section className="border border-border bg-card p-5">
          <div className="flex items-center gap-3">
            <h2 className="font-mono text-lg font-bold text-foreground">{result.spec} → {result.decision}</h2>
            <span className="border border-border px-1.5 py-0.5 font-mono text-[9px] text-muted-foreground">clause {result.key_clause}</span>
          </div>

          {result.fab_hours != null ? (
            <table className="mt-4 w-full border-collapse">
              <tbody>
                {[
                  ["Fabrication hours", `${result.fab_hours} h`],
                  ["Installation hours", `${result.install_hours} h`],
                  ...(result.final_price_egp ? [["Quoted price", `EGP ${Number(result.final_price_egp).toLocaleString()}`]] : []),
                  ...(result.schedule ? [["Starts", result.schedule.start_week]] : []),
                  ...(result.schedule ? [["Fab ends", result.schedule.fab_end_week]] : []),
                  ...(result.schedule ? [["Planned finish", result.schedule.planned_finish]] : []),
                  ["Release gate", result.approval_id
                    ? `queued as #${result.approval_id} (${result.release_status})`
                    : "refused — nothing queued"],
                ].map(([k, v]) => (
                  <tr key={k} className="border-b border-border last:border-0">
                    <th className="py-2 pr-4 text-left font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{k}</th>
                    <td className="py-2 font-mono text-xs text-foreground">{v}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="mt-3 font-mono text-xs text-muted-foreground">No plan figures — the request did not pass the gates.</p>
          )}

          <h3 className="mb-1 mt-5 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Why</h3>
          <ul className="list-disc pl-5 font-mono text-xs leading-6 text-muted-foreground">
            {(result.reasons || []).map((r, i) => <li key={i}>{r}</li>)}
            {(result.citations || []).map((r, i) => <li key={`c${i}`}>{r}</li>)}
          </ul>
        </section>
      )}
    </AppShell>
  );
}
