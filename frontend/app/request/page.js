"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, getUser } from "../../lib/api";
import AppShell from "../../components/AppShell";

function ChatInner() {
  const user = getUser();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [doneCode, setDoneCode] = useState(null);
  const [llmMode, setLlmMode] = useState(null); // true=AI, false=form fallback
  const boxRef = useRef(null);
  const sessionId = useRef(null);
  const started = useRef(false);

  // ---- scripted fallback state (only when LLM unavailable) ----
  const fallback = useRef({ step: 0, answers: {} });
  const FALLBACK_STEPS = [
    ["title", "What would you like us to build? (short description)"],
    ["kind", "Item type? railing / mezzanine / flight / gate_double / gate_single / security_door / caged_ladder / support_frame / racking_bay / canopy"],
    ["qty", "Quantity (metres, m2 or count — just the number):"],
    ["finish", "Finish? (e.g. shop paint RAL 7016, galvanised — or 'none')"],
    ["site", "Site location? ('-' to skip)"],
    ["required_raw", "When do you need it? (e.g. 'within 6 weeks')"],
  ];

  useEffect(() => {
    if (!user || user.role !== "client" || started.current) return;
    started.current = true;
    setBusy(true);
    api("/intake/start", { method: "POST" })
      .then((out) => {
        if (out.llm && out.session_id) {
          sessionId.current = out.session_id;
          setLlmMode(true);
          push("assistant", out.reply);
        } else {
          setLlmMode(false);
          push("assistant",
            "(Smart assistant offline — using guided mode.) " + FALLBACK_STEPS[0][1]);
        }
      })
      .catch((e) => push("assistant", `Error: ${e.message}`))
      .finally(() => setBusy(false));
  }, []);

  useEffect(() => { boxRef.current?.scrollTo(0, boxRef.current.scrollHeight); }, [messages]);

  function push(role, text) { setMessages((m) => [...m, { role, text }]); }

  async function submit() {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    push("client", text);
    setBusy(true);
    try {
      if (llmMode) {
        const out = await api(`/intake/${sessionId.current}/message`, {
          method: "POST",
          body: { text },
        });
        push("assistant", out.reply);
        if (out.complete) setDoneCode(out.code);
      } else {
        runFallback(text);
      }
    } catch (e) {
      push("assistant", `Something went wrong: ${e.message}`);
    } finally {
      setBusy(false);
    }
  }

  function runFallback(text) {
    const fb = fallback.current;
    if (fb.step > 0) fb.answers[FALLBACK_STEPS[fb.step - 1][0]] = text;
    if (fb.step === FALLBACK_STEPS.length) {
      if (!text.toLowerCase().startsWith("y")) {
        fb.step = 0; fb.answers = {};
        push("assistant", "Starting over. " + FALLBACK_STEPS[0][1]);
        return;
      }
      const a = fb.answers;
      api("/requests", {
        method: "POST",
        body: {
          title: a.title,
          items: [{ kind: a.kind, qty: parseFloat(a.qty) || 1, note: "" }],
          finish: a.finish === "none" ? "" : a.finish,
          site: a.site === "-" ? "" : a.site,
          required_raw: a.required_raw,
        },
      }).then((out) => {
        push("assistant", `Submitted as request ${out.code}. An engineer will review it.`);
        setDoneCode(out.code);
      }).catch((e) => push("assistant", `Error: ${e.message}`));
      return;
    }
    const next = FALLBACK_STEPS[fb.step];
    push("assistant", next[1]);
    fb.step += 1;
  }

  if (!user || user.role !== "client") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-6">
        <div className="max-w-md border border-border bg-card p-8 text-center">
          <h3 className="font-mono text-sm font-bold text-foreground">Tell us what you need</h3>
          <p className="mt-3 font-mono text-xs leading-6 text-muted-foreground">
            Create a free client account first — then chat with our assistant
            and it will handle everything.
          </p>
          <Link href="/login?mode=signup" className="mt-5 inline-block bg-primary px-5 py-3 font-mono text-xs font-bold text-primary-foreground hover:opacity-90">
            Create account
          </Link>
        </div>
      </div>
    );
  }

  return (
    <AppShell active="New request" title="Request a service"
              subtitle={
                llmMode === null ? "Connecting…" :
                llmMode ? "Chat naturally — the assistant knows what Ousus needs."
                        : "Guided mode (smart assistant offline)."}>
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
          {busy && <div className="font-mono text-[10px] text-muted-foreground">Thinking…</div>}
        </div>
        {!doneCode && (
          <div className="flex gap-2 border-t border-border p-3">
            <input value={input} onChange={(e) => setInput(e.target.value)}
                   onKeyDown={(e) => e.key === "Enter" && submit()}
                   placeholder="Type your answer…" disabled={busy}
                   className="flex-1 border border-border bg-background px-3 py-2.5 font-mono text-xs text-foreground" />
            <button onClick={submit} disabled={busy}
                    className="bg-primary px-4 py-2.5 font-mono text-xs font-bold text-primary-foreground hover:opacity-90 disabled:opacity-50">Send</button>
          </div>
        )}
      </div>
      {doneCode && (
        <p className="font-mono text-xs text-primary">
          Request {doneCode} submitted. Track progress in <Link href="/my" className="underline">My Projects</Link>.
        </p>
      )}
    </AppShell>
  );
}

export default function RequestChat() {
  return <ChatInner />;
}
