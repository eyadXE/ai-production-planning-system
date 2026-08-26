"use client";

import { useCallback, useEffect, useState } from "react";
import AppShell from "../../components/AppShell";
import { api } from "../../lib/api";

export default function Release() {
  const [awaitingClient, setAwaitingClient] = useState([]);
  const [readyToRelease, setReadyToRelease] = useState([]);
  const [engineers, setEngineers] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [releasedMsg, setReleasedMsg] = useState("");

  const load = useCallback(async () => {
    try {
      const [board, engs] = await Promise.all([
        api("/board"), api("/team/engineers")]);
      setEngineers(engs);
      const all = Object.values(board.columns).flat();
      // the Release page shows ONLY orders the client has accepted
      setReadyToRelease(all.filter((p) => p.release_status === "client_accepted"));
      setAwaitingClient(all.filter((p) => p.release_status === "queued"));
    } catch (e) { setError(e.message); }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function release(code) {
    const sel = document.getElementById("assign-" + code);
    const eid = sel ? Number(sel.value) : null;
    if (!eid) { setError("assign a project engineer first"); return; }
    setBusy(code); setError(""); setReleasedMsg("");
    try {
      await api(`/projects/${code}/assign`, {
        method: "POST", body: { engineer_id: eid },
      });
      await api(`/projects/${code}/release`, { method: "POST" });
      const eng = engineers.find((e) => e.id === eid);
      setReleasedMsg(`${code} released to production — assigned to ${eng ? eng.name : "engineer"}. It is now on the timeline.`);
      await load();
    } catch (e) { setError(e.message); } finally { setBusy(""); }
  }

  return (
    <AppShell active="Release" title="Release to production"
              subtitle="Only offers ACCEPTED by the client appear here. Assign a project engineer and release — released orders join the timeline permanently.">
      {error && <div className="text-destructive">{error}</div>}
      {releasedMsg && <div className="border border-primary/40 bg-card p-3 font-mono text-xs text-primary">{releasedMsg}</div>}

      <section>
        <h3 className="mb-3 font-mono text-[10px] uppercase tracking-[0.18em] text-primary">
          Accepted by client · ready to release · {readyToRelease.length}</h3>
        {readyToRelease.length === 0 ? (
          <div className="border border-border bg-card p-5 font-mono text-xs text-muted-foreground">
            Nothing ready — offers appear here once the client accepts them.
          </div>
        ) : readyToRelease.map((p) => (
          <div key={p.code} className="mb-4 border border-primary/40 bg-card p-5">
            <div className="flex flex-wrap items-center gap-3">
              <b className="font-mono text-sm text-foreground">{p.code} — {p.title}</b>
              <span className="border border-chart-2/40 px-1.5 py-0.5 font-mono text-[9px] text-chart-2">CLIENT ACCEPTED</span>
            </div>
            <div className="mt-3 flex flex-wrap items-end gap-3">
              <div>
                <label className="mb-1 block font-mono text-[9px] uppercase text-muted-foreground">Assign project engineer</label>
                <select id={"assign-" + p.code} defaultValue=""
                        className="border border-border bg-background px-2 py-2 font-mono text-[11px] text-foreground w-52">
                  <option value="" disabled>Choose…</option>
                  {engineers.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
                </select>
              </div>
              <button onClick={() => release(p.code)} disabled={busy === p.code}
                      className="bg-primary px-4 py-2.5 font-mono text-xs font-bold text-primary-foreground hover:opacity-90 disabled:opacity-50">
                Assign &amp; release to production
              </button>
            </div>
          </div>
        ))}
        <p className="mt-2 font-mono text-[10px] leading-5 text-destructive">
          Released orders are permanent — they can never be deleted.
        </p>
      </section>

      <section className="mt-8">
        <h3 className="mb-3 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
          Awaiting client decision · {awaitingClient.length}</h3>
        {awaitingClient.length === 0 ? (
          <p className="font-mono text-[11px] text-muted-foreground">No offers waiting on clients.</p>
        ) : awaitingClient.map((p) => (
          <div key={p.code} className="mb-2 border border-border bg-card p-3 font-mono text-xs text-muted-foreground">
            {p.code} — {p.title}
          </div>
        ))}
        <p className="mt-2 font-mono text-[10px] leading-5 text-muted-foreground">
          The client sees the full offer (price, hours, schedule) and accepts or
          declines from their dashboard. Only accepted orders reach the release list above.
        </p>
      </section>
    </AppShell>
  );
}
