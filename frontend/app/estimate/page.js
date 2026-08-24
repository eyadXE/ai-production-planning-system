"use client";

import { useState } from "react";
import { api } from "../../lib/api";
import Nav from "../../components/Nav";

const SPEC_CODES = Array.from({ length: 27 }, (_, i) => `J-${String(i + 1).padStart(3, "0")}`);

export default function Estimate() {
  const [code, setCode] = useState("J-001");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function run(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setResult(null);
    try {
      setResult(await api(`/specs/${code}/estimate`, { method: "POST" }));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Nav />
      <div className="container">
        <h1>Run Estimation Pipeline</h1>
        <form onSubmit={run} style={{ display: "flex", gap: 10, alignItems: "end", maxWidth: 420 }}>
          <div style={{ flex: 1 }}>
            <label>Spec</label>
            <select value={code} onChange={(e) => setCode(e.target.value)}>
              {SPEC_CODES.map((c) => <option key={c}>{c}</option>)}
            </select>
          </div>
          <button className="btn" disabled={busy}>{busy ? "Running…" : "Estimate"}</button>
        </form>
        {error && <div className="error">{error}</div>}

        {result && (
          <div className="card" style={{ marginTop: 20 }}>
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 10 }}>
              <h3 style={{ margin: 0 }}>{result.spec} → {result.decision}</h3>
              <span className={`badge ${result.decision === "PLAN" ? "released" :
                    result.decision === "DELAY_RISK" ? "blocked" : ""}`}>
                clause {result.key_clause}
              </span>
            </div>

            {result.fab_hours != null && (
              <table>
                <tbody>
                  <tr><th>Fabrication hours</th><td>{result.fab_hours} h</td></tr>
                  <tr><th>Installation hours</th><td>{result.install_hours} h</td></tr>
                  {result.final_price_egp &&
                    <tr><th>Quoted price</th><td>EGP {result.final_price_egp.toLocaleString()}</td></tr>}
                  {result.schedule && <>
                    <tr><th>Starts</th><td>{result.schedule.start_week}</td></tr>
                    <tr><th>Fabrication ends</th><td>{result.schedule.fab_end_week}</td></tr>
                    <tr><th>Planned finish</th><td>{result.schedule.planned_finish}</td></tr>
                  </>}
                  <tr><th>Approval</th><td>
                    {result.approval_id
                      ? `queued as #${result.approval_id} (${result.release_status})`
                      : "— refused — no release queued"}
                  </td></tr>
                </tbody>
              </table>
            )}

            {result.reasons?.length > 0 && (
              <>
                <h3 style={{ marginTop: 14 }}>Why</h3>
                <ul style={{ margin: 0, paddingLeft: 18, lineHeight: 1.7 }}>
                  {result.reasons.map((r, i) => <li key={i}>{r}</li>)}
                </ul>
              </>
            )}
          </div>
        )}
      </div>
    </>
  );
}
