"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, getUser } from "../../lib/api";
import AppShell from "../../components/AppShell";

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

function ChatInner() {
  const user = getUser();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [step, setStep] = useState(0);
  const [done, setDone] = useState(null);
  const [busy, setBusy] = useState(false);
  const boxRef = useRef(null);
  const answers = useRef({});

  const steps = [
    { key: "title", q: "Hi! I'm the Ousus assistant. What would you like us to build?" },
    { key: "kind", q: "Great. What type of item is it?", options: ITEM_TYPES },
    { key: "qty", q: "How much/many? Enter just the number." },
    { key: "finish", q: "Any finish preference? (e.g. shop paint RAL 7016, galvanised — or 'none')" },
    { key: "site", q: "Where should it be delivered/installed? ('-' to skip)" },
    { key: "required_raw", q: "When do you need it? (e.g. 'within 6 weeks')" },
  ];

  useEffect(() => {
    if (user && messages.length === 0) {
      push("assistant", steps[0].q);
      setStep(1);
    }
  }, [user]);

  useEffect(() => { boxRef.current?.scrollTo(0, boxRef.current.scrollHeight); }, [messages]);

  function push(role, text) { setMessages((m) => [...m, { role, text }]); }

  async function submit() {
    const value = input.trim();
    if (!value) return;
    setInput("");

    if (step === steps.length + 1) {
      if (value.toLowerCase().startsWith("y")) return doSubmit();
      push("assistant", "No problem — let's start over. What would you like to build?");
      answers.current = {}; setStep(1);
      return;
    }
    const key = steps[step - 1].key;
    answers.current[key] = value;
    push("client", value);

    if (key === "qty") {
      const n = parseFloat(value);
      if (!n || n <= 0) {
        push("assistant", "Please enter a number greater than 0.");
        return;
      }
    }
    if (key === "finish" && ["unstated", "", "no"].includes(value.toLowerCase())) answers.current.finish = "";
    if (key === "site" && value === "-") answers.current.site = "";

    if (step === steps.length) {
      const a = answers.current;
      push("assistant",
        `Here is your request:\n\n• ${a.title}\n• ${ITEM_TYPES.find(([k]) => k === a.kind)?.[1] ?? a.kind}: ${a.qty}\n` +
        `• Finish: ${a.finish || "none specified"}\n• Site: ${a.site || "to be confirmed"}\n• Required: ${a.required_raw}\n\n` +
        `Type YES to submit for engineering review.`);
      setStep(steps.length + 1);
      return;
    }
    push("assistant", steps[step].q);
    setStep(step + 1);
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
          finish: a.finish, site: a.site, required_raw: a.required_raw,
        },
      });
      push("assistant",
        `Submitted as request ${out.code}. An engineer will review it — you'll get an email when it moves forward.`);
      setDone(out.code);
    } catch (e) {
      push("assistant", `Sorry, something went wrong: ${e.message}`);
    } finally { setBusy(false); }
  }

  if (!user || user.role !== "client") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-6">
        <div className="max-w-md border border-border bg-card p-8 text-center">
          <h3 className="font-mono text-sm font-bold text-foreground">Tell us what you need</h3>
          <p className="mt-3 font-mono text-xs leading-6 text-muted-foreground">
            Create a free client account first — the assistant walks you
            through your request in under two minutes.
          </p>
          <Link href="/login?mode=signup" className="mt-5 inline-block bg-primary px-5 py-3 font-mono text-xs font-bold text-primary-foreground hover:bg-primary/90">
            Create account
          </Link>
        </div>
      </div>
    );
  }

  return (
    <AppShell active="New request" title="Request a service"
              subtitle="Our assistant collects everything we need — no forms.">
      <div className="border border-border bg-card" style={{ padding: 0 }}>
        <div ref={boxRef} style={{ maxHeight: 440, overflowY: "auto", padding: 16 }}>
          {messages.map((m, i) => (
            <div key={i} className={`mb-2 flex ${m.role === "client" ? "justify-end" : "justify-start"}`}>
              <div style={{ whiteSpace: "pre-wrap" }}
                   className={`max-w-[80%] rounded-lg px-3 py-2 font-mono text-xs leading-6 ${m.role === "client" ? "bg-primary text-primary-foreground" : "bg-secondary text-foreground"}`}>
                {m.text}
              </div>
            </div>
          ))}
          {busy && <div className="font-mono text-[10px] text-muted-foreground">Sending…</div>}
        </div>
        {!done && (
          <div className="flex gap-2 border-t border-border p-3">
            <input value={input} onChange={(e) => setInput(e.target.value)}
                   onKeyDown={(e) => e.key === "Enter" && submit()}
                   placeholder={step > steps.length ? "Type YES to confirm…" : "Type your answer…"}
                   disabled={busy}
                   className="flex-1 border border-border bg-background px-3 py-2.5 font-mono text-xs text-foreground" />
            <button className="bg-primary px-4 py-2.5 font-mono text-xs font-bold text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                    onClick={submit} disabled={busy}>Send</button>
          </div>
        )}
      </div>
      {done && (
        <p className="font-mono text-xs text-primary">
          Request {done} submitted. Track progress in <Link href="/my" className="underline">My Projects</Link>.
        </p>
      )}
    </AppShell>
  );
}

export default function RequestChat() {
  return <ChatInner />;
}
