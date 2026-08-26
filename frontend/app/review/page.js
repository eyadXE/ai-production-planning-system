"use client";

import { useCallback, useEffect, useState } from "react";
import { Gauge, Hammer } from "lucide-react";
import AppShell from "../../components/AppShell";
import { api, getUser } from "../../lib/api";

const isCustomOnly = (s) => {
  const st = s.structured || {};
  return (st.custom || []).length > 0 && !(st.items || []).length;
};

export default function Review() {
  const [items, setItems] = useState([]);
  const [awaitingMgr, setAwaitingMgr] = useState([]);
  const [rejected, setRejected] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [draft, setDraft] = useState(null);      // ran-estimate result (catalog)
  const [comment, setComment] = useState("");
  const [user, setUser] = useState(null);
  // per-card state
  const [customForm, setCustomForm] = useState({});
  const [mgrForm, setMgrForm] = useState({});
  const [mgrComments, setMgrComments] = useState({});

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

  const catalogItems = items.filter((s) => !isCustomOnly(s));
  const customItems = items.filter(isCustomOnly);

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

  async function submitCustomPlan(code) {
    const f = customForm[code] || {};
    if (!f.fab_hours || Number(f.fab_hours) <= 0) {
      setError("enter fabrication hours first"); return;
    }
    setBusy(code); setError("");
    try {
      await api(`/requests/${code}/custom/estimator-info`, {
        method: "POST",
        body: {
          scope: f.scope || "",
          materials_note: f.materials_note || "",
          fab_hours: Number(f.fab_hours),
          install_hours: Number(f.install_hours || 0),
        },
      });
      setCustomForm((m) => ({ ...m, [code]: undefined }));
      await load();
    } catch (e) { setError(e.message); } finally { setBusy(""); }
  }

  async function managerDecide(code, approved) {
    const note = (mgrComments[code] || "").trim();
    const f = mgrForm[code] || {};
    if (!approved && !note) {
      setError("a rejection requires a comment explaining why");
      return;
    }
    setBusy(code); setError("");
    try {
      const body = { approved, comment: note };
      if (approved && f.material_cost_egp) {
        body.material_cost_egp = Number(f.material_cost_egp);
        body.margin_applied = Number(f.margin_applied || 22);
        body.planned_finish = f.planned_finish || "";
      }
      await api(`/requests/${code}/manager-decision`, {
        method: "POST", body,
      });
      setMgrComments((m) => ({ ...m, [code]: "" }));
      setMgrForm((m) => ({ ...m, [code]: {} }));
      await load();
    } catch (e) { setError(e.message); } finally { setBusy(""); }
  }

  const inputCls = "border border-border bg-background px-3 py-2 font-mono text-xs text-foreground w-full";
  const labelCls = "mb-1 block font-mono text-[10px] uppercase tracking-wider text-muted-foreground";

  return (
    <AppShell active="Requests" title="Engineering review"
              subtitle={isManager
                ? "Approve or reject reviewed requests — for custom builds complete pricing & schedule before approving. After the client accepts, release from the Release page."
                : "Catalog requests: run estimation then approve or reject. Custom requests: fill your engineering plan in the Custom section."}>
      {error && <div className="text-destructive">{error}</div>}

      {/* ---- ESTIMATOR: custom two-level planning ----------------------- */}
      {!isManager && customItems.length > 0 && (
        <section>
          <h3 className="mb-3 font-mono text-[10px] uppercase tracking-[0.18em] text-primary">
            Custom · needs your engineering input · {customItems.length}</h3>
          {customItems.map((s) => {
            const f = customForm[s.code] || {};
            const customs = (s.structured?.custom || []);
            return (
              <div key={s.code} className="mb-4 border border-primary/40 bg-card p-5">
                <div className="flex items-center gap-3">
                  <Hammer className="size-4 text-primary" />
                  <b className="font-mono text-sm text-foreground">{s.code} — {s.title}</b>
                  <span className="ml-auto border border-border px-1.5 py-0.5 font-mono text-[9px] text-muted-foreground">{s.account}</span>
                </div>
                {customs.map((c, i) => (
                  <p key={i} className="mt-2 font-mono text-[11px] text-muted-foreground">
                    <b className="text-foreground">{c.name}</b>
                    {c.description ? ` — ${c.description}` : ""}
                    {c.photo && <>
                      {" "}
                      <img src={c.photo} alt={c.name}
                           className="mt-1 inline-block h-16 border border-border" />
                    </>}
                  </p>
                ))}
                <p className="mt-2 font-mono text-[10px] text-muted-foreground">
                  Site: {s.structured?.site || "—"}
                </p>
                <div className="mt-3 grid max-w-2xl gap-3 sm:grid-cols-2">
                  <div className="sm:col-span-2">
                    <label className={labelCls}>Scope of work (your notes)</label>
                    <textarea rows={2} value={f.scope || ""}
                              onChange={(e) => setCustomForm((m) => ({ ...m, [s.code]: { ...f, scope: e.target.value } }))}
                              placeholder="what will be built, key dimensions, approach…"
                              className={inputCls} />
                  </div>
                  <div className="sm:col-span-2">
                    <label className={labelCls}>Materials note</label>
                    <input value={f.materials_note || ""}
                           onChange={(e) => setCustomForm((m) => ({ ...m, [s.code]: { ...f, materials_note: e.target.value } }))}
                           placeholder="e.g. SHS frame + mesh infill, shop paint"
                           className={inputCls} />
                  </div>
                  <div>
                    <label className={labelCls}>Fabrication hours *</label>
                    <input type="number" min="1" value={f.fab_hours || ""}
                           onChange={(e) => setCustomForm((m) => ({ ...m, [s.code]: { ...f, fab_hours: e.target.value } }))}
                           placeholder="e.g. 80" className={inputCls} />
                  </div>
                  <div>
                    <label className={labelCls}>Installation hours</label>
                    <input type="number" min="0" value={f.install_hours || ""}
                           onChange={(e) => setCustomForm((m) => ({ ...m, [s.code]: { ...f, install_hours: e.target.value } }))}
                           placeholder="e.g. 20" className={inputCls} />
                  </div>
                </div>
                <button onClick={() => submitCustomPlan(s.code)} disabled={!!busy}
                        className="mt-3 bg-primary px-4 py-2.5 font-mono text-xs font-bold text-primary-foreground hover:opacity-90 disabled:opacity-50">
                  Send to management for pricing →
                </button>
              </div>
            );
          })}
        </section>
      )}

      {/* ---- MANAGER: awaiting decision --------------------------------- */}
      {isManager && (
        <section>
          <h3 className="mb-3 font-mono text-[10px] uppercase tracking-[0.18em] text-primary">
            Awaiting your decision · {awaitingMgr.length}</h3>
          {awaitingMgr.length === 0 && (
            <div className="border border-border bg-card p-5 font-mono text-xs text-muted-foreground">
              Nothing waiting — approved requests appear here after engineering review.
            </div>
          )}
          {awaitingMgr.map((r) => {
            const f = mgrForm[r.code] || {};
            const ep = r.estimator_plan || {};
            return (
              <div key={r.code} className="mb-4 border border-primary/40 bg-card p-5">
                <div className="flex items-center gap-3">
                  <Hammer className="size-4 text-primary" />
                  <b className="font-mono text-sm text-foreground">{r.code} — {r.title}</b>
                  <span className="ml-auto border border-border px-1.5 py-0.5 font-mono text-[9px] text-muted-foreground">{r.account}</span>
                </div>
                {(r.custom_items || []).length > 0 && (
                  <p className="mt-2 font-mono text-[11px] text-muted-foreground">
                    Custom: {r.custom_items.map((c) => c.name).join(", ")}
                    {r.custom_items.some((c) => c.description) && (
                      <span> — {r.custom_items.map((c) => c.description).filter(Boolean).join(" | ")}</span>
                    )}
                  </p>
                )}
                {(r.items || []).length > 0 && (
                  <p className="mt-2 font-mono text-[11px] text-muted-foreground">
                    Catalog items: {r.items.map((i) => `${i.kind} ×${i.qty}`).join(", ")}
                  </p>
                )}
                <table className="mt-3 w-full max-w-md border-collapse">
                  <tbody>
                    <tr><td className="py-1 pr-3 font-mono text-[10px] uppercase text-muted-foreground">Decision</td><td className="font-mono text-xs">{r.decision}</td></tr>
                    <tr><td className="py-1 pr-3 font-mono text-[10px] uppercase text-muted-foreground">Fabrication</td><td className="font-mono text-xs">{r.fab_hours} h</td></tr>
                    <tr><td className="py-1 pr-3 font-mono text-[10px] uppercase text-muted-foreground">Installation</td><td className="font-mono text-xs">{r.install_hours} h</td></tr>
                    {ep.scope && <tr><td className="py-1 pr-3 font-mono text-[10px] uppercase text-muted-foreground">Eng. scope</td><td className="font-mono text-xs">{ep.scope}</td></tr>}
                    {ep.materials_note && <tr><td className="py-1 pr-3 font-mono text-[10px] uppercase text-muted-foreground">Materials</td><td className="font-mono text-xs">{ep.materials_note}</td></tr>}
                  </tbody>
                </table>

                {r.needs_pricing && (
                  <div className="mt-3 border border-chart-2/40 bg-background p-3">
                    <b className="font-mono text-[10px] uppercase tracking-wider text-chart-2">
                      Your part — pricing &amp; schedule (required)</b>
                    <div className="mt-2 grid max-w-2xl gap-3 sm:grid-cols-3">
                      <div>
                        <label className={labelCls}>Material cost EGP *</label>
                        <input type="number" min="0" value={f.material_cost_egp || ""}
                               onChange={(e) => setMgrForm((m) => ({ ...m, [r.code]: { ...f, material_cost_egp: e.target.value } }))}
                               placeholder="e.g. 12000" className={inputCls} />
                      </div>
                      <div>
                        <label className={labelCls}>Margin %</label>
                        <input type="number" min="0" step="0.5" value={f.margin_applied ?? ""}
                               onChange={(e) => setMgrForm((m) => ({ ...m, [r.code]: { ...f, margin_applied: e.target.value } }))}
                               placeholder="22" className={inputCls} />
                      </div>
                      <div>
                        <label className={labelCls}>Completion date</label>
                        <input type="date" value={f.planned_finish || ""}
                               onChange={(e) => setMgrForm((m) => ({ ...m, [r.code]: { ...f, planned_finish: e.target.value } }))}
                               className={inputCls} />
                      </div>
                    </div>
                  </div>
                )}

                <label className={labelCls + " mt-4"}>
                  Comment (required on rejection)</label>
                <input value={mgrComments[r.code] || ""}
                       onChange={(e) => setMgrComments((m) => ({ ...m, [r.code]: e.target.value }))}
                       placeholder="e.g. capacity confirmed / over budget / blocked on materials"
                       className={inputCls + " max-w-xl"} />
                <div className="mt-3 flex gap-2">
                  <button onClick={() => managerDecide(r.code, true)} disabled={!!busy}
                          className="bg-primary px-4 py-2.5 font-mono text-xs font-bold text-primary-foreground hover:opacity-90 disabled:opacity-50">
                    Approve → send offer to client
                  </button>
                  <button onClick={() => managerDecide(r.code, false)} disabled={!!busy}
                          className="border border-destructive/40 px-4 py-2.5 font-mono text-xs text-destructive hover:bg-destructive/10 disabled:opacity-50">
                    Reject
                  </button>
                </div>
              </div>
            );
          })}
        </section>
      )}

      {/* ---- ESTIMATOR: catalog pipeline -------------------------------- */}
      <section className="mt-8">
        <h3 className="mb-3 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
          Catalog · pending review · {catalogItems.length}</h3>
        {catalogItems.length === 0 && (
          <div className="border border-border bg-card p-5 font-mono text-xs text-muted-foreground">No pending catalog requests.</div>
        )}
        {catalogItems.map((s) => (
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
                <div className="mt-4 grid gap-4 lg:grid-cols-2">
                  <div className="border border-border bg-background p-4">
                    <b className="font-mono text-xs text-primary">Plan summary</b>
                    <table className="mt-2 w-full border-collapse">
                      <tbody>
                        <tr><td className="py-1 pr-3 font-mono text-[10px] uppercase text-muted-foreground">Decision</td><td className="font-mono text-xs">{draft.decision} · clause {draft.key_clause}</td></tr>
                        <tr><td className="py-1 pr-3 font-mono text-[10px] uppercase text-muted-foreground">Fabrication</td><td className="font-mono text-xs">{draft.fab_hours} h</td></tr>
                        <tr><td className="py-1 pr-3 font-mono text-[10px] uppercase text-muted-foreground">Installation</td><td className="font-mono text-xs">{draft.install_hours} h</td></tr>
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
                    <b className="font-mono text-xs text-primary">Resource check — materials vs stock</b>
                    {(draft.bom_with_stock || []).length === 0 && (
                      <p className="mt-2 font-mono text-[11px] text-muted-foreground">No material lines.</p>
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

      <section className="mt-8">
        <h3 className="mb-3 font-mono text-sm font-bold text-destructive">
          Rejected / blocked — permanent record</h3>
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
