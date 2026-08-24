"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getUser } from "../lib/api";

const SERVICES = [
  { name: "Mezzanine decks", desc: "Structural steel decks with chequer-plate flooring, edge protection included." },
  { name: "Staircases", desc: "Straight flights with landings, balustrades measured separately." },
  { name: "Railings & balustrades", desc: "SHS posts with flat-bar infill, any run length, shop painted any RAL." },
  { name: "Gates & doors", desc: "Single/double swing or sliding gates, mesh or plate infill, security doors." },
  { name: "Access ladders", desc: "Caged access ladders for plant and fire-escape routes." },
  { name: "Racking", desc: "Heavy-duty storage racking, priced per bay." },
  { name: "Canopies", desc: "Entrance canopies with RHS frames and plate soffits." },
  { name: "Support frames", desc: "Machine support and press-line framing." },
];

const STEPS = [
  ["1. Request", "Tell our assistant what you need — it walks you through every detail."],
  ["2. Engineering review", "An Ousus engineer checks the request before anything is planned."],
  ["3. Plan & schedule", "We compute materials, hours, price and a realistic completion date."],
  ["4. Manager release", "Nothing starts until management signs off — your guarantee of control."],
  ["5. Build & install", "Track your project stage by stage; get email updates at every milestone."],
];

export default function Landing() {
  const [user, setUser] = useState(null);
  useEffect(() => setUser(getUser()), []);

  const ctaHref = user ? (user.role === "client" ? "/request" : "/board") : "/login";

  return (
    <div>
      <nav className="nav">
        <span className="brand">Ousus</span>
        <span className="spacer" />
        {user ? (
          <>
            <Link className="link active" href={ctaHref}>Open app</Link>
          </>
        ) : (
          <>
            <Link className="link" href="/login">Sign in</Link>
            <Link className="btn" href="/login?mode=signup">Create account</Link>
          </>
        )}
      </nav>

      <div className="container">
        <div style={{ textAlign: "center", padding: "50px 0 40px" }}>
          <h1 style={{ fontSize: 34 }}>
            Steel fabrication,<br />planned with discipline.
          </h1>
          <p style={{ color: "var(--muted)", maxWidth: 560, margin: "14px auto 24px", lineHeight: 1.7 }}>
            Ousus turns your written request into a full production plan —
            materials, labour, price and a realistic schedule — reviewed by
            engineers and released only with management sign-off.
          </p>
          <div style={{ display: "flex", gap: 10, justifyContent: "center" }}>
            <Link className="btn" href="/request">Request a service</Link>
            {!user && <Link className="btn secondary" href="/login">Client sign in</Link>}
          </div>
        </div>

        <h3>What we fabricate</h3>
        <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", marginBottom: 36 }}>
          {SERVICES.map((s) => (
            <div key={s.name} className="card">
              <b>{s.name}</b>
              <div style={{ color: "var(--muted)", marginTop: 6, lineHeight: 1.6 }}>{s.desc}</div>
            </div>
          ))}
        </div>

        <h3>How it works</h3>
        <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", marginBottom: 40 }}>
          {STEPS.map(([t, d]) => (
            <div key={t} className="card">
              <b>{t}</b>
              <div style={{ color: "var(--muted)", marginTop: 6, lineHeight: 1.6 }}>{d}</div>
            </div>
          ))}
        </div>

        <div className="card" style={{ textAlign: "center", padding: 30 }}>
          <b style={{ fontSize: 16 }}>Ready to start?</b>
          <p style={{ color: "var(--muted)" }}>
            Chat with our assistant — it collects everything we need in minutes.
          </p>
          <Link className="btn" href="/request">Request a service</Link>
        </div>
      </div>
    </div>
  );
}
