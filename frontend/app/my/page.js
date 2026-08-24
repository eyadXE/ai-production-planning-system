"use client";

import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import Nav from "../../components/Nav";

export default function MyProjects() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/my/projects").then(setData).catch((e) => setError(e.message));
  }, []);

  if (error) return <><Nav /><div className="container"><div className="error">{error}</div></div></>;
  if (!data) return <><Nav /><div className="container">Loading…</div></>;

  const stageLabel = (p) =>
    p.release_status === "queued" ? "Plan awaiting management approval"
    : p.status === "blocked_material" ? "Waiting on materials"
    : `In ${p.stage}`;

  return (
    <>
      <Nav />
      <div className="container">
        <h1>My Projects</h1>
        {data.projects.length === 0 && (
          <div className="card">No projects yet — request one through our team.</div>
        )}
        <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))" }}>
          {data.projects.map((p) => (
            <div key={p.code} className={`project-card ${p.overdue ? "overdue" : ""}`}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span className="code">{p.code}</span>
                {p.overdue && <span className="badge overdue">DELAYED</span>}
                {p.release_status === "released" && <span className="badge released">APPROVED</span>}
                {p.release_status === "queued" && <span className="badge queued">IN REVIEW</span>}
              </div>
              <div>{p.title}</div>
              <div className="meta">{stageLabel(p)}</div>
              <div className="meta">Target: {p.required_date || "—"}</div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
