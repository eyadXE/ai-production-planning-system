"use client";

import { useCallback, useEffect, useState } from "react";
import { Gauge, Hammer } from "lucide-react";
import AppShell from "../../components/AppShell";
import { api, getUser } from "../../lib/api";

export default function Review() {
  const [items, setItems] = useState([]);
  const [awaitingMgr, setAwaitingMgr] = useState([]);
  const [rejected, setRejected] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [draft, setDraft] = useState(null);      // ran-estimate result
  const [comment, setComment] = useState("");
  const [user, setUser] = useState(null);

  useEffect(() => { setUser(getUser()); }, []);
  const isManager = user?.role === "manager";

  const load = useCallback(async () => {
    try {
      const calls = [api("/requests/pending"), api("/requests/rejected")];
      if (getUser()?.role === "manager")
        calls.push(api("/requests/awaiting-decision"));
      const [pend, rej, awt] = await Promise.all(calls);
      setItems(pend);
      setRejected(rej);
      if (awt) setAwaitingMgr(awt);
    } catch (e) { setError(e.message); }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function runEstimate(code) {
    setBusy(code); setError(""); setDraft(null);
    try {
      const r = await api(`/requests/${code}/run-estimate`, { method: "POST" });
      r.code = code;
      setDraft(r);
    } catch (e) { setError(e.message); } finally { setBusy(""); }
  }

  async function decide(code, approved) {
    if (!approved && !comment.trim()) {
      setError("a rejection requires a comment explaining why");
      return;
    }
    setBusy(code); setError("");
    try {
      await api(`/requests/${code}/decision`, {
        method: "POST", body: { approved, comment },
      });
      setComment(""); setDraft(null);
      await load();
    } catch (e) { setError(e.message); } finally { setBusy(""); }
  }

  async function managerDecide(code, approved) {
    if (!approved && !comment.trim()) {
      setError("a rejection requires a comment explaining why");
      return;
    }
    setBusy(code); setError("");
    try {
      await api(`/requests/${code}/manager-decision`, {
        method: "POST", body: { approved, comment },
      });
      setComment("");
      await load();
    } catch (e) { setError(e.message); } finally { setBusy(""); }
  }

  return (
    <AppShell active="Requests" title="Engineering review"
              subtitle={isManager
                ? "Requests reviewed by engineering awaiting your approve/reject — then the client decides, then open the release gate in Approvals."
                : "Run the estimation on client requests, review the plan against our resources, then approve or reject with a reason."}>
      {error && <div className="text-destructive">{error}</div>}

      {isManager && (
        <section>
          <h3 className="mb-3 font-mono text-[10px] uppercase tracking-[0.18em] text-primary">
            Awaiting your decision · {awaitingMgr.length}</h3>
          {awaitingMgr.length === 0 && (
            <div className="border border-border bg-card p-5 font-mono text-xs text-muted-foreground">
              Nothing waiting — approved requests appear here after engineering review.
            </div>
          )}
          {awaitingMgr.map((r) => (
            <div key={r.code} className="mb-4 border border-primary/40 bg-card p-5">
              <div className="flex items-center gap-3">
                <Hammer className="size-4 text-primary" />
                <b className="font-mono text-sm text-foreground">{r.code} — {r.title}</b>
                <span className="ml-auto border border-border px-1.5 py-0.5 font-mono text-[9px] text-muted-foreground">{r.account}</span>
              </div>
              {(r.items || []).length > 0 && (
                <p className="mt-2 font-mono text-[11px] text-muted-foreground">
                  Catalog items: {r.items.map((i) => `${i.kind} ×${i.qty}`).join(", ")}
                </p>
              )}
              {(r.custom_items || []).length > 0 && (
                <p className="mt-2 font-mono text-[11px] text-muted-foreground">
                  Custom: {r.custom_items.map((c) => c.name).join(", ")}
                  {r.custom_items.some((c) => c.description) && (
                    <span> — {r.custom_items.map((c) => c.description).filter(Boolean).join(" | ")}</span>
                  )}
                </p>
              )}
              <table className="mt-3 w-full max-w-md border-collapse">
                <tbody>
                  <tr><td className="py-1 pr-3 font-mono text-[10px] uppercase text-muted-foreground">Decision</td><td className="font-mono text-xs">{r.decision}</td></tr>
                  <tr><td className="py-1 pr-3 font-mono text-[10px] uppercase text-muted-foreground">Fabrication</td><td className="font-mono text-xs">{r.fab_hours} h</td></tr>
                  <tr><td className="py-1 pr-3 font-mono text-[10px] uppercase text-muted-foreground">Installation</td><td className="font-mono text-xs">{r.install_hours} h</td></tr>
                  <tr><td className="py-1 pr-3 font-mono text-[10px] uppercase text-muted-foreground">Quoted price</td><td className="font-mono text-xs">EGP {Number(r.final_price_egp || 0).toLocaleString()}</td></tr>
                  <tr><td className="py-1 pr-3 font-mono text-[10px] uppercase text-muted-foreground">Est. completion</td><td className="font-mono text-xs">{r.estimated_finish || "—"}</td></tr>
                </tbody>
              </table>
              <label className="mb-1 mt-4 block font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                Comment (required on rejection)</label>
              <input value={comment} onChange={(e) => setComment(e.target.value)}
                     placeholder="e.g. capacity confirmed / over budget / blocked on materials"
                     className="w-full max-w-xl border border-border bg-background px-3 py-2.5 font-mono text-xs text-foreground" />
              <div className="mt-3 flex gap-2">
                <button onClick={() => managerDecide(r.code, true)} disabled={!!busy}
                        className="bg-primary px-4 py-2.5 font-mono text-xs font-bold text-primary-foreground hover:opacity-90 disabled:opacity-50">
                  Approve → send to client
                </button>
                <button onClick={() => managerDecide(r.code, false)} disabled={!!busy}
                        className="border border-destructive/40 px-4 py-2.5 font-mono text-xs text-destructive hover:bg-destructive/10 disabled:opacity-50">
                  Reject
                </button>
              </div>
            </div>
          ))}
        </section>
      )}

      <section>
        <h3 className="mb-3 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
          Pending · {items.length}</h3>
        {items.length === 0 && (
          <div className="border border-border bg-card p-5 font-mono text-xs text-muted-foreground">No pending requests.</div>
        )}
        {items.map((s) => (
          <div key={s.code} className="mb-4 border border-border bg-card p-5">
            <div className="flex items-center gap-3">
              <Hammer className="size-4 text-primary" />
              <b className="font-mono text-sm text-foreground">{s.code} — {s.title}</b>
              <span className="ml-auto border border-border px-1.5 py-0.5 font-mono text-[9px] text-muted-foreground">{s.account}</span>
            </div>

            {!draft || draft.code !== s.code ? (
              <button onClick={() => runEstimate(s.code)} disabled={busy === s.code}
                      className="mt-3 flex items-center gap-2 bg-primary px-4 py-2.5 font-mono text-xs font-bold text-primary-foreground hover:opacity-90 disabled:opacity-50">
                <Gauge className="size-4" />{busy === s.code ? "Running pipeline…" : "Run estimation"}
              </button>
            ) : (
              <>
                {/* plan review */}
                {draft.decision === "MANUAL_PLAN" && (
                  <div className="mt-4 border border-chart-2/40 bg-card p-4 font-mono text-[11px] leading-5 text-chart-2">
                    MANUAL_PLAN — this is a custom build outside our rate
                    table, requiring manual engineering planning. The figures
                    below are preliminary allowances; verify them before
                    approving. No catalog BOM applies.
                    {(draft.custom_items || []).length > 0 && (
                      <ul className="mt-2 list-disc pl-5 text-muted-foreground">
                        {draft.custom_items.map((c, i) => (
                          <li key={i}>
                            <b className="text-foreground">{c.name}</b>
                            {c.description ? ` — ${c.description}` : ""}
                            {c.photo && <>
                              {" "}
                              <img src={c.photo} alt={c.name}
                                   className="mt-1 inline-block h-16 border border-border" />
                            </>}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
                <div className="mt-4 grid gap-4 lg:grid-cols-2">
                  <div className="border border-border bg-background p-4">
                    <b className="font-mono text-xs text-primary">Plan summary</b>
                    <table className="mt-2 w-full border-collapse">
                      <tbody>
                        <tr><td className="py-1 pr-3 font-mono text-[10px] uppercase text-muted-foreground">Decision</td><td className="font-mono text-xs">{draft.decision} · clause {draft.key_clause}</td></tr>
                        {draft.decision !== "MANUAL_PLAN" ? <>
                          <tr><td className="py-1 pr-3 font-mono text-[10px] uppercase text-muted-foreground">Fabrication</td><td className="font-mono text-xs">{draft.fab_hours} h</td></tr>
                          <tr><td className="py-1 pr-3 font-mono text-[10px] uppercase text-muted-foreground">Installation</td><td className="font-mono text-xs">{draft.install_hours} h</td></tr>
                        </> : <>
                          <tr><td className="py-1 pr-3 font-mono text-[10px] uppercase text-muted-foreground">Fabrication (prelim.)</td><td className="font-mono text-xs">{draft.fab_hours} h</td></tr>
                          <tr><td className="py-1 pr-3 font-mono text-[10px] uppercase text-muted-foreground">Installation (prelim.)</td><td className="font-mono text-xs">{draft.install_hours} h</td></tr>
                        </>}
                        <tr><td className="py-1 pr-3 font-mono text-[10px] uppercase text-muted-foreground">Material cost</td><td className="font-mono text-xs">EGP {Number(draft.material_cost_egp || 0).toLocaleString()}</td></tr>
                        <tr><td className="py-1 pr-3 font-mono text-[10px] uppercase text-muted-foreground">Quoted price</td><td className="font-mono text-xs">EGP {Number(draft.final_price_egp || 0).toLocaleString()}</td></tr>
                        {draft.schedule && <>
                          <tr><td className="py-1 pr-3 font-mono text-[10px] uppercase text-muted-foreground">Starts</td><td className="font-mono text-xs">{draft.schedule.start_week || "TBD"}</td></tr>
                          <tr><td className="py-1 pr-3 font-mono text-[10px] uppercase text-muted-foreground">Est. completion</td><td className="font-mono text-xs">{draft.schedule.planned_finish}</td></tr>
                        </>}
                      </tbody>
                    </table>
                  </div>
                  <div className="border border-border bg-background p-4">
                    <b className="font-mono text-xs text-primary">
                      {draft.decision === "MANUAL_PLAN"
                        ? "Custom items (manual plan — no BOM)"
                        : "Resource check — materials vs stock"}
                    </b>
                    {(draft.bom_with_stock || []).length === 0 && (
                      <p className="mt-2 font-mono text-[11px] text-muted-foreground">
                        {draft.decision === "MANUAL_PLAN"
                          ? "Custom build — engineering will define materials during manual planning."
                          : "No material lines."}
                      </p>
                    )}
                    <table className="mt-2 w-full border-collapse">
                      <tbody>
                        {(draft.bom_with_stock || []).map((l, i) => (
                          <tr key={i} className="border-b border-border last:border-0">
                            <td className="py-1 pr-3 font-mono text-xs text-foreground">{l.code}</td>
                            <td className="py-1 font-mono text-xs text-muted-foreground">need {l.qty}</td>
                            <td className={`py-1 font-mono text-xs ${l.sufficient ? "text-chart-2" : "text-destructive"}`}>
                              stock {l.stock}{!l.sufficient && " ⚠"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {(draft.reasons || []).length > 0 && (
                  <ul className="mt-3 list-disc pl-5 font-mono text-[11px] leading-5 text-muted-foreground">
                    {draft.reasons.map((r, i) => <li key={i}>{r}</li>)}
                  </ul>
                )}

                <label className="mb-1 mt-4 block font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                  Comment (required on rejection)</label>
                <input value={comment} onChange={(e) => setComment(e.target.value)}
                       placeholder="e.g. capacity confirmed / missing site details"
                       className="w-full border border-border bg-background px-3 py-2.5 font-mono text-xs text-foreground" />
                <div className="mt-3 flex gap-2">
                  <button onClick={() => decide(s.code, true)} disabled={!!busy}
                          className="bg-primary px-4 py-2.5 font-mono text-xs font-bold text-primary-foreground hover:opacity-90 disabled:opacity-50">
                    Approve &amp; send to manager
                  </button>
                  <button onClick={() => decide(s.code, false)} disabled={!!busy}
                          className="border border-destructive/40 px-4 py-2.5 font-mono text-xs text-destructive hover:bg-destructive/10 disabled:opacity-50">
                    Reject
                  </button>
                </div>
              </>
            )}
          </div>
        ))}
      </section>

      <section>
        <h3 className="mb-3 font-mono text-sm font-bold text-destructive">
          Rejected requests — permanent record</h3>
        {rejected.length === 0 && (
          <div className="border border-border bg-card p-5 font-mono text-xs text-muted-foreground">None.</div>
        )}
        {rejected.map((r) => (
          <div key={r.code} className="mb-3 border border-border bg-card p-4">
            <b className="font-mono text-xs text-foreground">{r.code} — {r.title}</b>
            <span className="ml-2 border border-border px-1.5 py-0.5 font-mono text-[9px] text-muted-foreground">{r.account}</span>
            <p className="mt-1 font-mono text-[11px] text-destructive">Reason: {r.note || "—"}</p>
            <p className="font-mono text-[10px] text-muted-foreground">Reviewed by {r.reviewer}</p>
          </div>
        ))}
      </section>
    </AppShell>
  );
}
