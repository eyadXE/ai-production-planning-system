"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "../../lib/api";
import Nav from "../../components/Nav";

export default function Review() {
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [results, setResults] = useState({});

  const load = useCallback(async () => {
    try {
      setItems(await api("/requests/pending"));
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function review(code, approve) {
    setBusy(code);
    setError("");
    try {
      const r = await api(`/requests/${code}/review?approve=${approve}`, { method: "POST" });
      setResults((prev) => ({ ...prev, [code]: r }));
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  }

  return (
    <>
      <Nav />
      <div className="container">
        <h1>Engineering Review — client requests</h1>
        {error && <div className="error">{error}</div>}
        {items.length === 0 && <div className="card">No requests waiting for review.</div>}

        {items.map((s) => (
          <div key={s.code} className="card" style={{ marginBottom: 12 }}>
            <b>{s.code}</b> — {s.title}
            <span className="badge queued" style={{ marginLeft: 8 }}>{s.account}</span>
            <table style={{ marginTop: 10 }}>
              <tbody>
                {(s.structured?.items || []).map((it, i) => (
                  <tr key={i}><th>{it.kind}</th><td>{it.qty}{it.note ? ` (${it.note})` : ""}</td></tr>
                ))}
                <tr><th>Finish</th><td>{s.structured?.finish || "unstated"}</td></tr>
                <tr><th>Site</th><td>{s.structured?.site || "—"}</td></tr>
                <tr><th>Required</th><td>{s.structured?.required_raw}</td></tr>
              </tbody>
            </table>
            {results[s.code] && (
              <div className="card" style={{ marginTop: 10, background: "var(--bg)" }}>
                <b>Decision: {results[s.code].decision}</b>
                {results[s.code].fab_hours != null && (
                  <div style={{ color: "var(--muted)", marginTop: 6 }}>
                    {results[s.code].fab_hours} h fab / {results[s.code].install_hours} h install
                    {results[s.code].final_price_egp
                      ? ` · EGP ${Number(results[s.code].final_price_egp).toLocaleString()}`
                      : ""} · approval #{results[s.code].approval_id ?? "—"}
                  </div>
                )}
                <ul style={{ margin: "6px 0 0", paddingLeft: 18, color: "var(--muted)", lineHeight: 1.6 }}>
                  {(results[s.code].reasons || []).map((r, i) => <li key={i}>{r}</li>)}
                </ul>
              </div>
            )}
            {!results[s.code] && (
              <div style={{ marginTop: 10, display: "flex", gap: 8 }}>
                <button className="btn green" disabled={busy === s.code}
                        onClick={() => review(s.code, true)}>
                  Approve → planning phase
                </button>
                <button className="btn red" disabled={busy === s.code}
                        onClick={() => review(s.code, false)}>Reject</button>
              </div>
            )}
          </div>
        ))}
      </div>
    </>
  );
}
