"use client";

import { useCallback, useEffect, useState } from "react";
import { api, getUser } from "../../lib/api";
import Nav from "../../components/Nav";

export default function Board() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const isManager = getUser()?.role === "manager";

  const load = useCallback(async () => {
    try {
      setData(await api("/board"));
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function advance(code) {
    setBusy(code);
    setError("");
    try {
      await api(`/projects/${code}/stage`, { method: "PATCH", body: {} });
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  }

  async function remove(code) {
    if (!confirm(`Delete project ${code}? This cannot be undone.`)) return;
    setBusy(code);
    setError("");
    try {
      await api(`/projects/${code}`, { method: "DELETE" });
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  }

  if (error && !data) return <><Nav /><div className="container"><div className="error">{error}</div></div></>;
  if (!data) return <><Nav /><div className="container">Loading…</div></>;

  return (
    <>
      <Nav />
      <div className="container">
        <h1>Production Board</h1>
        {error && <div className="error">{error}</div>}
        <div className="board-grid">
          {data.stages.map((stage) => (
            <div key={stage}>
              <h3>{stage} ({(data.columns[stage] || []).length})</h3>
              {(data.columns[stage] || []).map((p) => (
                <div key={p.code}
                     className={`project-card ${p.overdue ? "overdue" : ""} ${p.status === "blocked_material" ? "blocked" : ""} ${p.release_status === "released" ? "released" : ""}`}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span className="code">{p.code}</span>
                    {p.overdue && <span className="badge overdue">OVERDUE</span>}
                    {!p.overdue && p.status === "blocked_material" &&
                      <span className="badge blocked">BLOCKED</span>}
                    {!p.overdue && p.status !== "blocked_material" && p.release_status === "released" &&
                      <span className="badge released">RELEASED</span>}
                    {!p.overdue && p.status !== "blocked_material" && p.release_status === "queued" &&
                      <span className="badge queued">IN GATE</span>}
                  </div>
                  <div>{p.title}</div>
                  <div className="meta">
                    required: {p.required_date || "—"}
                  </div>
                  {p.stage !== "Closed" && (
                    <button className="btn secondary" style={{ marginTop: 8, padding: "5px 10px" }}
                            disabled={busy === p.code}
                            onClick={() => advance(p.code)}>
                      Advance →
                    </button>
                  )}
                  {isManager && (
                    <button className="btn red" style={{ marginTop: 8, padding: "5px 10px", marginLeft: 6 }}
                            disabled={busy === p.code}
                            onClick={() => remove(p.code)}>
                      Delete
                    </button>
                  )}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
