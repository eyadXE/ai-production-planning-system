"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "../../lib/api";
import Nav from "../../components/Nav";

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
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function decide(id, approved) {
    setBusy(String(id));
    setError("");
    try {
      await api(`/approvals/${id}/decision`, {
        method: "POST",
        body: { approved, note },
      });
      setNote("");
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
        <h1>Approval Queue — the Release Gate</h1>
        <p style={{ color: "var(--muted)" }}>
          Nothing is released to fabrication and no material is ordered until
          you approve it here (clause 0.2).
        </p>
        {error && <div className="error">{error}</div>}

        {items.length === 0 && <div className="card">Queue is empty.</div>}
        {items.map((a) => (
          <div key={a.id} className="card" style={{ marginBottom: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <b>#{a.id} · {a.type.replace("_", " ")}</b>
                <div className="meta" style={{ color: "var(--muted)", marginTop: 4 }}>{a.note}</div>
              </div>
            </div>
            <label>Decision note (optional)</label>
            <input value={note} onChange={(e) => setNote(e.target.value)}
                   placeholder="e.g. materials verified, capacity confirmed" />
            <div style={{ marginTop: 10, display: "flex", gap: 8 }}>
              <button className="btn green" disabled={busy === String(a.id)}
                      onClick={() => decide(a.id, true)}>Approve &amp; release</button>
              <button className="btn red" disabled={busy === String(a.id)}
                      onClick={() => decide(a.id, false)}>Reject</button>
            </div>
          </div>
        ))}

        <h1 style={{ marginTop: 30 }}>Audit Trail</h1>
        <div className="card">
          <table>
            <thead>
              <tr><th>#</th><th>Type</th><th>Decision</th><th>Approver</th><th>When</th><th>Note</th></tr>
            </thead>
            <tbody>
              {audit.map((a) => (
                <tr key={a.id}>
                  <td>{a.id}</td><td>{a.type}</td>
                  <td>{a.decision}</td>
                  <td>{a.approver_id || "—"}</td>
                  <td>{(a.at || "").replace("T", " ").slice(0, 19)}</td>
                  <td>{a.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
