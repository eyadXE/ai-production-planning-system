"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, getUser } from "../../lib/api";
import Nav from "../../components/Nav";

const ITEM_TYPES = [
  ["railing", "Railing / balustrade (metres)"],
  ["mezzanine", "Mezzanine deck (m²)"],
  ["flight", "Staircase flight (count)"],
  ["gate_double", "Double gate (count)"],
  ["gate_single", "Single gate (count)"],
  ["security_door", "Security door (count)"],
  ["caged_ladder", "Caged ladder (count)"],
  ["support_frame", "Support frame (count)"],
  ["racking_bay", "Racking bay (count)"],
  ["canopy", "Canopy (m²)"],
  ["floor_plate_area", "Floor plate area (m²)"],
];

export default function RequestChat() {
  const user = getUser();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [step, setStep] = useState(0);
  const [done, setDone] = useState(null);
  const [busy, setBusy] = useState(false);
  const boxRef = useRef(null);

  const steps = [
    { key: "title", q: "Hi! I'm the Ousus assistant. In a few words, what would you like us to build? (e.g. 'Villa gate and fence rail')" },
    { key: "kind", q: "Great. What type of item is it?", options: ITEM_TYPES },
    { key: "qty", q: "How much/many? Enter just the number." },
    { key: "finish", q: "Any finish preference? (e.g. shop paint RAL 7016, galvanised, or 'none')" },
    { key: "site", q: "Where should it be delivered/installed?" },
    { key: "required_raw", q: "When do you need it? (e.g. 'within 6 weeks' or a date)" },
    { key: "confirm", q: "" },
  ];

  useEffect(() => {
    if (user !== null && step === 0 && messages.length === 0) {
      push("assistant", steps[0].q);
      setStep(1);
    }
  }, [user]);

  useEffect(() => { boxRef.current?.scrollTo(0, boxRef.current.scrollHeight); }, [messages]);

  function push(role, text) {
    setMessages((m) => [...m, { role, text }]);
  }

  const answers = useRef({});

  async function submit() {
    const value = input.trim();
    if (!value) return;
    setInput("");

    if (step === steps.length) { // summary confirmation
      if (value.toLowerCase().startsWith("y")) return doSubmit();
      push("assistant", "No problem — let's start over. What would you like to build?");
      answers.current = {};
      setStep(1);
      return;
    }
    const key = steps[step - 1].key;
    answers.current[key] = value;
    push("client", value);

    if (key === "qty") {
      const n = parseFloat(value);
      if (!n || n <= 0) {
        push("assistant", "That doesn't look like a valid quantity — please enter a number greater than 0.");
        return;
      }
    }
    if (key === "finish" && ["unstated", "", "no"].includes(value.toLowerCase())) {
      answers.current.finish = "";
    }
    if (key === "site") answers.current.site = value === "-" ? "" : value;

    const nextQ = steps[step]?.q;
    if (step + 1 === steps.length) { // reached confirm
      const a = answers.current;
      push("assistant",
        `Here is your request:\n\n` +
        `• ${a.title}\n` +
        `• ${ITEM_TYPES.find(([k]) => k === a.kind)?.[1] ?? a.kind}: ${a.qty}\n` +
        `• Finish: ${a.finish || "none specified"}\n` +
        `• Site: ${a.site || "to be confirmed"}\n` +
        `• Required: ${a.required_raw}\n\n` +
        `Type YES to submit for engineering review, or anything else to start over.`);
      setStep(steps.length);
      setInput("");
      return;
    }
    push("assistant", nextQ);
    setStep(step + 1);
    setInput("");
  }

  async function doSubmit() {
    setBusy(true);
    try {
      const a = answers.current;
      const out = await api("/requests", {
        method: "POST",
        body: {
          title: a.title,
          items: [{ kind: a.kind, qty: parseFloat(a.qty), note: "" }],
          finish: a.finish,
          site: a.site,
          required_raw: a.required_raw,
        },
      });
      push("assistant",
        `Submitted as request ${out.code}. An engineer will review it — ` +
        `you'll get an email when it moves forward. Track it under My Projects.`);
      setDone(out.code);
    } catch (e) {
      push("assistant", `Sorry, something went wrong: ${e.message}`);
    } finally {
      setBusy(false);
    }
  }

  if (getUser() === null) {
    return (
      <>
        <Nav />
        <div className="container">
          <div className="card" style={{ maxWidth: 480, margin: "60px auto", textAlign: "center" }}>
            <h3>Tell us what you need</h3>
            <p style={{ color: "var(--muted)", lineHeight: 1.7 }}>
              Create a free client account first — then our assistant will walk
              you through your request in under two minutes.
            </p>
            <Link className="btn" href="/login?mode=signup">Create account</Link>
          </div>
        </div>
      </>
    );
  }
  if (user?.role !== "client") {
    return (
      <>
        <Nav />
        <div className="container"><div className="card">The intake chat is for client accounts.</div></div>
      </>
    );
  }

  return (
    <>
      <Nav />
      <div className="container" style={{ maxWidth: 720 }}>
        <h1>Request a service</h1>
        <div className="card" style={{ padding: 0 }}>
          <div ref={boxRef} style={{ maxHeight: 420, overflowY: "auto", padding: 16 }}>
            {messages.map((m, i) => (
              <div key={i} style={{
                display: "flex",
                justifyContent: m.role === "client" ? "flex-end" : "flex-start",
                marginBottom: 8,
              }}>
                <div style={{
                  background: m.role === "client" ? "var(--accent)" : "var(--border)",
                  color: m.role === "client" ? "#fff" : "var(--text)",
                  borderRadius: 10, padding: "8px 12px",
                  whiteSpace: "pre-wrap", maxWidth: "80%", lineHeight: 1.5,
                }}>{m.text}</div>
              </div>
            ))}
            {busy && <div style={{ color: "var(--muted)" }}>Sending…</div>}
          </div>
          {!done && (
            <div style={{ display: "flex", gap: 8, borderTop: "1px solid var(--border)", padding: 12 }}>
              <input value={input} onChange={(e) => setInput(e.target.value)}
                     onKeyDown={(e) => e.key === "Enter" && submit()}
                     placeholder={step >= steps.length ? "Type YES to confirm…" : "Type your answer…"}
                     disabled={busy} />
              <button className="btn" onClick={submit} disabled={busy}>Send</button>
            </div>
          )}
        </div>
        {done && <p className="success">Request {done} submitted. Check <Link href="/my" style={{ color: "var(--accent)" }}>My Projects</Link> for progress.</p>}
      </div>
    </>
  );
}
