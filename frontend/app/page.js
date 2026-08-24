"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, Factory } from "lucide-react";
import { getUser } from "../lib/api";

const SERVICES = [
  ["Mezzanine decks", "Structural steel decks with chequer-plate flooring, edge protection included."],
  ["Staircases", "Straight flights with landings; balustrades measured separately."],
  ["Railings & balustrades", "SHS posts with flat-bar infill, any run length, painted any RAL."],
  ["Gates & doors", "Swing or sliding gates with mesh/plate infill; security doors."],
  ["Access ladders", "Caged ladders for plant and fire-escape routes."],
  ["Racking", "Heavy-duty storage racking, priced per bay."],
  ["Canopies", "Entrance canopies with RHS frames and plate soffits."],
  ["Support frames", "Machine support and press-line framing."],
];

const STEPS = [
  ["01 · Request", "Tell our assistant what you need — it collects every detail."],
  ["02 · Engineering review", "An Ousus engineer checks the request before planning."],
  ["03 · Plan & schedule", "Materials, hours, price and a realistic completion date."],
  ["04 · Manager release", "Nothing starts without management sign-off."],
  ["05 · Build & install", "Track your project stage by stage, with email updates."],
];

export default function Landing() {
  const [user, setUser] = useState(null);
  useEffect(() => setUser(getUser()), []);

  const appHref = user ? (user.role === "client" ? "/my" : "/summary") : "/login";

  return (
    <div className="min-h-screen bg-background text-foreground">
      <nav className="flex items-center justify-between border-b border-border px-6 py-4 sm:px-10">
        <div className="flex items-center gap-3">
          <div className="grid size-8 place-items-center bg-primary text-primary-foreground"><Factory className="size-4" /></div>
          <p className="font-mono text-base font-bold tracking-tight">OUSUS</p>
        </div>
        <div className="flex items-center gap-3">
          {user ? (
            <Link href={appHref} className="bg-primary px-4 py-2 font-mono text-xs font-bold text-primary-foreground hover:bg-primary/90">Open app</Link>
          ) : (
            <>
              <Link href="/login" className="font-mono text-xs text-muted-foreground hover:text-foreground">Sign in</Link>
              <Link href="/login?mode=signup" className="bg-primary px-4 py-2 font-mono text-xs font-bold text-primary-foreground hover:bg-primary/90">Create account</Link>
            </>
          )}
        </div>
      </nav>

      <section className="mx-auto max-w-[1440px] px-6 py-20 text-center sm:px-10">
        <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-primary">Steel fabrication · planned with discipline</p>
        <h1 className="mx-auto mt-4 max-w-2xl font-mono text-3xl font-bold leading-tight tracking-tight sm:text-5xl">
          Your request in. A production plan out.
        </h1>
        <p className="mx-auto mt-5 max-w-xl font-mono text-xs leading-6 text-muted-foreground">
          Ousus turns a written description into a complete plan — materials,
          labour hours, price and a realistic schedule — reviewed by engineers
          and released only with management sign-off.
        </p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Link href="/request" className="flex items-center gap-2 bg-primary px-5 py-3 font-mono text-xs font-bold text-primary-foreground hover:bg-primary/90">
            Request a service <ArrowRight className="size-4" />
          </Link>
          {!user && (
            <Link href="/login" className="border border-border px-5 py-3 font-mono text-xs text-muted-foreground hover:border-primary hover:text-primary">
              Client sign in
            </Link>
          )}
        </div>
      </section>

      <section className="mx-auto max-w-[1440px] px-6 pb-16 sm:px-10">
        <p className="mb-4 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">What we fabricate</p>
        <div className="grid gap-px bg-border sm:grid-cols-2 lg:grid-cols-4">
          {SERVICES.map(([name, desc]) => (
            <div key={name} className="bg-card p-5">
              <b className="font-mono text-xs text-foreground">{name}</b>
              <p className="mt-2 font-mono text-[11px] leading-5 text-muted-foreground">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-[1440px] px-6 pb-24 sm:px-10">
        <p className="mb-4 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">How it works</p>
        <div className="grid gap-px bg-border sm:grid-cols-2 lg:grid-cols-5">
          {STEPS.map(([t, d]) => (
            <div key={t} className="bg-card p-5">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-primary">{t}</p>
              <p className="mt-2 font-mono text-[11px] leading-5 text-muted-foreground">{d}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="border-t border-border px-6 py-8 text-center sm:px-10">
        <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Ousus Production Platform — people stay in control of what reaches the workshop floor.
        </p>
      </footer>
    </div>
  );
}
