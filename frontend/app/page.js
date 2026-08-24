"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import Image from "next/image";
import { ArrowRight } from "lucide-react";
import { getUser } from "../lib/api";

const CATEGORIES = [
  {
    name: "Carbon Steel Products",
    items: ["Railings", "Staircases", "Ladders & Rungs", "Walkways", "Trench Covers", "Fences", "Gates", "Technical Rooms", "Car Sheds", "Claddings"],
  },
  {
    name: "Structural Steel Works",
    items: ["Warehouses", "Heavy-Duty Staircases", "Signal Light Posts"],
  },
  {
    name: "Aluminium Decorative",
    items: ["Decorative Panels / Mushrabiya", "Sandtrap Louvers", "Ship Ladders", "Aluminium Partitions"],
  },
  {
    name: "Stainless Steel Products",
    items: ["Railings", "Claddings", "Gratings", "Green Walls", "Water Tank Ladders", "Roof Walkways", "Technical Room Louvers"],
  },
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
      <nav className="flex items-center justify-between border-b border-border px-6 py-3 sm:px-10">
        <Link href="/">
          <img src="/ousus-logo.png" alt="Ousus" className="h-12 w-auto" />
        </Link>
        <div className="flex items-center gap-3">
          {user ? (
            <Link href={appHref} className="bg-primary px-4 py-2 font-mono text-xs font-bold text-primary-foreground hover:opacity-90">Open app</Link>
          ) : (
            <>
              <Link href="/login" className="font-mono text-xs text-muted-foreground hover:text-foreground">Sign in</Link>
              <Link href="/login?mode=signup" className="bg-primary px-4 py-2 font-mono text-xs font-bold text-primary-foreground hover:opacity-90">Create account</Link>
            </>
          )}
        </div>
      </nav>

      {/* hero */}
      <section className="relative border-b border-border">
        <div className="absolute inset-0">
          <img src="/hero.jpg" alt="" className="h-full w-full object-cover opacity-25" />
          <div className="absolute inset-0 bg-gradient-to-b from-background/60 via-background/70 to-background" />
        </div>
        <div className="relative mx-auto max-w-[1440px] px-6 py-24 text-center sm:px-10">
          <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-primary">
            The trusted name in steel fabrication in the region
          </p>
          <h1 className="mx-auto mt-5 max-w-2xl font-mono text-3xl font-bold leading-tight tracking-tight sm:text-5xl">
            Your request in. A production plan out.
          </h1>
          <p className="mx-auto mt-5 max-w-xl font-mono text-xs leading-6 text-muted-foreground">
            Ousus turns a written description into a complete production plan —
            materials, labour hours, price and a realistic schedule — reviewed
            by engineers and released only with management sign-off.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Link href="/request" className="flex items-center gap-2 bg-primary px-5 py-3 font-mono text-xs font-bold text-primary-foreground hover:opacity-90">
              Request a service <ArrowRight className="size-4" />
            </Link>
            {!user && (
              <Link href="/login" className="border border-primary/40 bg-background/50 px-5 py-3 font-mono text-xs text-foreground hover:border-primary hover:text-primary">
                Client sign in
              </Link>
            )}
          </div>
        </div>
      </section>

      {/* about */}
      <section className="mx-auto max-w-[1440px] px-6 py-16 sm:px-10">
        <div className="grid items-center gap-10 lg:grid-cols-2">
          <div>
            <p className="mb-4 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">About Ousus</p>
            <h2 className="font-mono text-2xl font-bold text-foreground">
              Decades of fabrication discipline, now with a production platform to match.
            </h2>
            <p className="mt-5 font-mono text-xs leading-6 text-muted-foreground">
              From its workshop, Ousus delivers carbon steel, structural steel,
              aluminium decorative and stainless steel products for projects
              across the region — railings, staircases, gates, walkways,
              warehouses and more. Every job is planned before it is cut:
              materials verified against stock, hours taken from the rate
              handbook, schedules booked against real weekly capacity, and
              nothing released without management sign-off.
            </p>
            <div className="mt-6 grid grid-cols-3 gap-4">
              {[["4", "Product lines"], ["40+", "Product types"], ["9", "Tracked stages"]].map(([n, l]) => (
                <div key={l} className="border border-border bg-card p-4">
                  <p className="font-mono text-2xl font-bold text-primary">{n}</p>
                  <p className="mt-1 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{l}</p>
                </div>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <img src="/about-1.png" alt="Ousus fabrication" className="h-56 w-full border border-border object-cover" />
            <img src="/about-2.png" alt="Ousus products" className="mt-8 h-56 w-full border border-border object-cover" />
          </div>
        </div>
      </section>

      {/* products */}
      <section className="mx-auto max-w-[1440px] px-6 py-16 sm:px-10">
        <p className="mb-6 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Our products</p>
        <div className="grid gap-px bg-border sm:grid-cols-2 lg:grid-cols-4">
          {CATEGORIES.map((cat) => (
            <div key={cat.name} className="bg-card p-6">
              <b className="font-mono text-sm uppercase tracking-wide text-foreground">{cat.name}</b>
              <ul className="mt-4 flex flex-col gap-2">
                {cat.items.map((item) => (
                  <li key={item} className="flex items-center gap-2 font-mono text-[11px] text-muted-foreground">
                    <span className="size-1 shrink-0 bg-primary" />{item}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <p className="mt-4 font-mono text-[11px] text-muted-foreground">
          Catalogues and references available at{" "}
          <a href="https://ousus.com" target="_blank" rel="noreferrer" className="text-primary hover:underline">ousus.com</a>
        </p>
      </section>

      {/* workshop strip */}
      <section className="relative h-56 overflow-hidden border-y border-border">
        <img src="/workshop.png" alt="Ousus workshop" className="h-full w-full object-cover opacity-40" />
        <div className="absolute inset-0 flex items-center justify-center bg-background/50">
          <Link href="/request" className="flex items-center gap-2 border border-primary/60 bg-background/80 px-6 py-3 font-mono text-xs font-bold text-primary hover:bg-primary hover:text-primary-foreground">
            Ask for a quote <ArrowRight className="size-4" />
          </Link>
        </div>
      </section>

      {/* process */}
      <section className="mx-auto max-w-[1440px] px-6 pb-24 sm:px-10">
        <p className="mb-6 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">How the platform works</p>
        <div className="grid gap-px bg-border sm:grid-cols-2 lg:grid-cols-5">
          {STEPS.map(([t, d]) => (
            <div key={t} className="bg-card p-5">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-primary">{t}</p>
              <p className="mt-2 font-mono text-[11px] leading-5 text-muted-foreground">{d}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="flex flex-col items-center gap-3 border-t border-border px-6 py-10 sm:px-10">
        <img src="/ousus-logo.png" alt="Ousus" className="h-10 w-auto opacity-70" />
        <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          People stay in control of what reaches the workshop floor.
        </p>
      </footer>
    </div>
  );
}
