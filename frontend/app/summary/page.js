"use client";

import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import Nav from "../../components/Nav";

export default function Summary() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/summary/daily").then(setData).catch((e) => setError(e.message));
  }, []);

  if (error) return <><Nav /><div className="container"><div className="error">{error}</div></div></>;
  if (!data) return <><Nav /><div className="container">Loading…</div></>;

  return (
    <>
      <Nav />
      <div className="container">
        <h1>Daily Production Summary <span className="badge">DRAFT — queued for approval (4.4)</span></h1>

        <div className="stat-row">
          <div className="stat"><div className="num">{data.active_projects}</div><div className="lbl">Active projects</div></div>
          <div className="stat"><div className="num" style={{ color: "var(--red)" }}>{data.overdue.length}</div><div className="lbl">Overdue</div></div>
          <div className="stat"><div className="num" style={{ color: "var(--amber)" }}>{data.blocked_on_materials.length}</div><div className="lbl">Blocked on material</div></div>
          <div className="stat"><div className="num">{data.pending_approvals}</div><div className="lbl">Pending approvals</div></div>
        </div>

        <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", alignItems: "start" }}>
          <div className="card">
            <h3>Projects by stage</h3>
            {Object.entries(data.projects_by_stage).filter(([, n]) => n > 0).map(([s, n]) => (
              <div key={s} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
                <span>{s}</span><b>{n}</b>
              </div>
            ))}
          </div>

          <div>
            <div className="card" style={{ marginBottom: 12 }}>
              <h3 style={{ color: "var(--red)" }}>Overdue (named, with cause)</h3>
              {data.overdue.length === 0 && <span style={{ color: "var(--muted)" }}>None.</span>}
              {data.overdue.map((p) => (
                <div key={p.code} style={{ padding: "4px 0" }}>
                  <b>{p.code}</b> — {p.title} · stuck at {p.stage}
                  {p.planned_finish && <> · planned finish {p.planned_finish}</>}
                </div>
              ))}
            </div>

            <div className="card" style={{ marginBottom: 12 }}>
              <h3 style={{ color: "var(--amber)" }}>Blocked on materials</h3>
              {data.blocked_on_materials.length === 0 && <span style={{ color: "var(--muted)" }}>None.</span>}
              {data.blocked_on_materials.map((p) => (
                <div key={p.code} style={{ padding: "4px 0" }}><b>{p.code}</b> — {p.title} at {p.stage}</div>
              ))}
            </div>

            <div className="card">
              <h3>Coming capacity</h3>
              {data.capacity.fully_booked_weeks.length > 0 && (
                <div style={{ padding: "4px 0", color: "var(--amber)" }}>
                  Fully booked: {data.capacity.fully_booked_weeks.join(", ")}
                </div>
              )}
              {data.capacity.first_meaningful_free_week && (
                <div style={{ padding: "4px 0", color: "var(--green)" }}>
                  First meaningful free capacity: {data.capacity.first_meaningful_free_week}
                </div>
              )}
            </div>
          </div>
        </div>

        <p style={{ color: "var(--muted)", marginTop: 14 }}>{data.note}</p>
      </div>
    </>
  );
}
