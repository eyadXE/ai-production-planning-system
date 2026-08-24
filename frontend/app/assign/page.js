"use client";

import { useCallback, useEffect, useState } from "react";
import { UserCheck } from "lucide-react";
import AppShell from "../../components/AppShell";
import { api } from "../../lib/api";

export default function Assignments() {
  const [engineers, setEngineers] = useState([]);
  const [projects, setProjects] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    try {
      setEngineers(await api("/team/engineers"));
      const board = await api("/board");
      setProjects(board.columns["Production Planning"] || []);
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function assign(code, engineerId) {
    if (!engineerId) return;
    setBusy(code); setError(""); setMessage("");
    try {
      const out = await api(`/projects/${code}/assign`, {
        method: "POST", body: { engineer_id: Number(engineerId) },
      });
      setMessage(`${code} assigned to ${out.assigned_to}`);
      await load();
    } catch (e) { setError(e.message); } finally { setBusy(""); }
  }

  return (
    <AppShell active="Assign" title="Assign project engineers"
              subtitle="After the estimator approves a request, assign an engineer who follows it through every stage.">
      {error && <div className="text-destructive">{error}</div>}
      {message && <div className="font-mono text-xs text-primary">{message}</div>}

      <section className="border border-border bg-card p-5">
        <h3 className="mb-3 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
          Projects in planning · {projects.length}</h3>
        {projects.length === 0 && (
          <p className="font-mono text-xs text-muted-foreground">
            Nothing waiting for assignment.
          </p>
        )}
        <table className="w-full border-collapse">
          <tbody>
            {projects.map((p) => (
              <tr key={p.code} className="border-b border-border last:border-0">
                <td className="py-3 font-mono text-xs font-bold text-foreground">{p.code}</td>
                <td className="py-3 font-mono text-xs text-muted-foreground">{p.title}</td>
                <td className="w-64 py-3">
                  <select defaultValue=""
                          onChange={(e) => assign(p.code, e.target.value)}
                          disabled={busy === p.code}
                          className="w-full border border-border bg-background px-2 py-2 font-mono text-xs text-foreground disabled:opacity-50">
                    <option value="" disabled>Choose engineer…</option>
                    {engineers.map((e2) => (
                      <option key={e2.id} value={e2.id}>{e2.name}</option>
                    ))}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="border border-border bg-card p-5">
        <h3 className="mb-3 flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
          <UserCheck className="size-3.5" /> Engineers</h3>
        <div className="grid gap-3 sm:grid-cols-3">
          {engineers.map((e2) => (
            <div key={e2.id} className="border border-border p-3">
              <b className="font-mono text-xs text-foreground">{e2.name}</b>
              <p className="font-mono text-[10px] text-muted-foreground">{e2.email}</p>
            </div>
          ))}
        </div>
      </section>
    </AppShell>
  );
}
