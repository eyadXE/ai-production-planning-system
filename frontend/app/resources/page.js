"use client";

import { useEffect, useState } from "react";
import AppShell from "../../components/AppShell";
import Link from "next/link";
import { api } from "../../lib/api";

export default function Resources() {
  const [materials, setMaterials] = useState(null);
  const [capacity, setCapacity] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/materials")
      .then((d) => setMaterials(d.materials))
      .catch((e) => setError(e.message));
    api("/summary/daily").catch(() => {});
  }, []);

  useEffect(() => {
    // capacity comes from the summary endpoint's capacity block
    api("/summary/daily")
      .then(() => {})
      .catch(() => {});
    api("/timeline")
      .then((d) => {
        // derive capacity strip from timeline weeks
        const weeks = d.weeks || [];
        setCapacity({
          fullyBooked: weeks.filter((w) => w.free_hours === 0).map((w) => w.label),
          rows: weeks,
        });
      })
      .catch(() => {});
  }, []);

  if (error) return <AppShell active="Resources" title="Resources"><div className="text-destructive">{error}</div></AppShell>;
  if (!materials) return <AppShell active="Resources" title="Resources"><p className="font-mono text-xs text-muted-foreground">Loading…</p></AppShell>;

  return (
    <AppShell active="Resources" title="Resources"
              subtitle="Materials stock and workshop capacity — check availability before approving a plan.">
      {/* materials */}
      <section className="border border-border bg-card">
        <h3 className="border-b border-border px-5 py-4 font-mono text-sm font-bold text-foreground">
          Material stock</h3>
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b border-border">
              {["Code", "Name", "Unit", "Price (EGP)", "Stock", "Lead time"].map((h) => (
                <th key={h} className="px-4 py-3 text-left font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{h}</th>))}
            </tr>
          </thead>
          <tbody>
            {materials.map((m) => (
              <tr key={m.code} className="border-b border-border last:border-0">
                <td className="px-4 py-2.5 font-mono text-xs font-bold text-foreground">{m.code}</td>
                <td className="px-4 py-2.5 font-mono text-[11px] text-muted-foreground">{m.name}</td>
                <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground">per {m.unit}</td>
                <td className="px-4 py-2.5 font-mono text-xs text-foreground">{Number(m.price_egp).toLocaleString()}</td>
                <td className={`px-4 py-2.5 font-mono text-xs ${m.stock <= 0 ? "text-destructive" : m.stock < 40 ? "text-chart-3" : "text-chart-2"}`}>
                  {m.stock}{m.stock <= 0 ? " ⚠ out of stock" : ""}
                </td>
                <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground">
                  {m.lead_time_weeks ? `${m.lead_time_weeks} wk` : "in stock"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* capacity */}
      {capacity && (
        <section className="border border-border bg-card">
          <h3 className="border-b border-border px-5 py-4 font-mono text-sm font-bold text-foreground">
            Workshop capacity — coming weeks</h3>
          <div className="grid gap-3 p-5 sm:grid-cols-3 lg:grid-cols-6">
            {capacity.rows.map((w) => {
              const pct = Math.round((w.free_hours / (w.total_hours || 320)) * 100);
              return (
                <div key={w.label}
                     className={`border p-3 ${w.free_hours <= 0 ? "border-destructive/40" : w.free_hours < 80 ? "border-chart-3/40" : "border-chart-2/40"}`}>
                  <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{w.label}</p>
                  <p className={`mt-1 font-mono text-lg font-bold ${w.free_hours <= 0 ? "text-destructive" : w.free_hours >= 160 ? "text-chart-2" : "text-chart-3"}`}>
                    {w.free_hours}h
                  </p>
                  <p className="font-mono text-[9px] text-muted-foreground">free of {w.total_hours}h</p>
                </div>
              );
            })}
          </div>
          <p className="border-t border-border px-5 py-3 font-mono text-[10px] leading-5 text-muted-foreground">
            A week needs ≥50% free hours to host a new fabrication run.
            Fully-booked weeks push plans later (clause 3.1).
          </p>
        </section>
      )}

      <Link href="/timeline" className="inline-block font-mono text-xs text-primary hover:underline">
        → Open the full production calendar
      </Link>
    </AppShell>
  );
}
