"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { FileDown, MessageSquare, Plus, Trash2, Upload, X } from "lucide-react";
import AppShell from "../../components/AppShell";
import { api, getUser } from "../../lib/api";

const CUSTOM_CHAT_SCHEMA_NOTE =
  "Chat collects: item name, description + size, quantity, material & finish.";

export default function RequestPage() {
  // auth (mount-safe)
  const [ready, setReady] = useState(false);
  const [user, setUser] = useState(null);

  // catalog
  const [catalog, setCatalog] = useState(null);
  const [loadError, setLoadError] = useState("");
  const [catalogs, setCatalogs] = useState([]);

  // cart
  const [cart, setCart] = useState([]);            // [{kind, qty, name}]
  const [customLines, setCustomLines] = useState([]); // manual lines

  // checkout form
  const [form, setForm] = useState({ title: "", finish: "", site: "", required_raw: "" });

  // custom chat
  const [chatError, setChatError] = useState("");
  const [chatOpen, setChatOpen] = useState(false);
  const [chatMsgs, setChatMsgs] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [chatSession, setChatSession] = useState(null);
  const [chatOffline, setChatOffline] = useState(false);
  const [chatDoneCode, setChatDoneCode] = useState(null);
  const chatBoxRef = useRef(null);

  // submit
  const [submitBusy, setSubmitBusy] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [submittedCode, setSubmittedCode] = useState(null);

  useEffect(() => {
    setUser(getUser());
    setReady(true);
  }, []);

  const loadCatalog = useCallback(() => {
    api("/products")
      .then((d) => {
        setCatalog(d);
        setCatalogs(d.catalogs || []);
      })
      .catch((e) => setLoadError(e.message));
  }, []);

  useEffect(() => { loadCatalog(); }, [loadCatalog]);

  useEffect(() => {
    chatBoxRef.current?.scrollTo(0, chatBoxRef.current.scrollHeight);
  }, [chatMsgs]);

  function addToCart(p) {
    if (!p.est_kind) {
      // not auto-estimable -> goes into the request as a custom line
      setCustomLines((prev) =>
        prev.some((c) => c.name === p.name)
          ? prev
          : [...prev, { name: p.name, description: p.description + " (standard product)", photo: "" }]
      );
      return;
    }
    setCart((prev) => {
      const i = prev.findIndex((c) => c.kind === p.est_kind && c.name === p.name);
      if (i >= 0) {
        const copy = [...prev];
        copy[i] = { ...copy[i], qty: copy[i].qty + 1 };
        return copy;
      }
      return [...prev, { kind: p.est_kind, qty: 1, name: p.name }];
    });
  }

  function removeFromCart(i) {
    setCart((prev) => prev.filter((_, j) => j !== i));
  }

  function changeQty(i, qty) {
    setCart((prev) =>
      prev.map((c, j) => (j === i ? { ...c, qty: qty > 0 ? qty : c.qty } : c))
    );
  }

  // ---------- custom chat ----------
  function cPush(role, text) {
    setChatMsgs((m) => [...m, { role, text }]);
  }

  const startChat = useCallback(async () => {
    setChatError("");
    setChatOpen(true);
    setChatMsgs([]);
    setChatDoneCode(null);
    setChatBusy(true);
    try {
      const out = await api("/intake/start", { method: "POST" });
      if (!out.llm || !out.session_id) {
        setChatOffline(true);
        cPush("assistant",
          "The smart assistant is offline right now. Press Retry, or add a " +
          "custom line below your cart describing what you need.");
        return;
      }
      setChatOffline(false);
      setChatSession(out.session_id);
      cPush("assistant", out.reply);
    } catch (e) {
      setChatError(e.message);
    } finally {
      setChatBusy(false);
    }
  }, []);

  const sendChat = useCallback(async () => {
    const text = chatInput.trim();
    if (!text || chatBusy || !chatSession) return;
    setChatInput("");
    cPush("client", text);
    setChatBusy(true);
    try {
      const out = await api(`/intake/${chatSession}/message`, {
        method: "POST",
        body: { text },
      });
      cPush("assistant", out.reply);
      if (out.complete && out.code) setChatDoneCode(out.code);
    } catch (e) {
      cPush("assistant", e.message);
    } finally {
      setChatBusy(false);
    }
  }, [chatInput, chatBusy, chatSession]);

  async function attachPhoto(file) {
    if (!file || !chatSession) return;
    setChatBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch("/api/uploads", {
        method: "POST",
        headers: { Authorization: `Bearer ${localStorage.getItem("ousus_token")}` },
        body: fd,
      });
      const out = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof out.detail === "string" ? out.detail : `HTTP ${res.status}`);
      await api(`/intake/${chatSession}/photo`, { method: "POST", body: { url: out.url } });
      cPush("assistant", "Reference photo attached.");
    } catch (e) {
      cPush("assistant", `Upload failed: ${e.message}`);
    } finally {
      setChatBusy(false);
    }
  }

  // ---------- submit whole request ----------
  async function submitRequest() {
    setSubmitBusy(true); setSubmitError("");
    try {
      const out = await api("/requests", {
        method: "POST",
        body: {
          title: form.title || "Service request",
          items: cart.map(({ kind, qty }) => ({ kind, qty })),
          custom: customLines,
          finish: form.finish,
          site: form.site,
          required_raw: form.required_raw,
        },
      });
      setSubmittedCode(out.code);
    } catch (e) {
      setSubmitError(e.message);
    } finally {
      setSubmitBusy(false);
    }
  }

  if (!ready) return null;

  if (!user || user.role !== "client") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-6">
        <div className="max-w-md border border-border bg-card p-8 text-center">
          <h3 className="font-mono text-sm font-bold text-foreground">Browse our services</h3>
          <p className="mt-3 font-mono text-xs leading-6 text-muted-foreground">
            Sign in with a client account to add products to a request.
          </p>
          <Link href="/login?mode=signup"
                className="mt-5 inline-block bg-primary px-5 py-3 font-mono text-xs font-bold text-primary-foreground hover:opacity-90">
            Create account
          </Link>
        </div>
      </div>
    );
  }

  if (submittedCode) {
    return (
      <AppShell active="Services" title="Request submitted">
        <div className="border border-border bg-card p-8 text-center">
          <p className="font-mono text-sm text-foreground">
            Request <b className="text-primary">{submittedCode}</b> submitted — an engineer
            will review it and you&apos;ll get an email at every step.
          </p>
          <div className="mt-6 flex justify-center gap-3">
            <Link href="/my" className="bg-primary px-4 py-2.5 font-mono text-xs font-bold text-primary-foreground hover:opacity-90">
              My Projects
            </Link>
            <button onClick={() => { setSubmittedCode(null); setCart([]); setCustomLines([]); }}
                    className="border border-border px-4 py-2.5 font-mono text-xs text-muted-foreground hover:text-foreground">
              New request
            </button>
          </div>
        </div>
      </AppShell>
    );
  }

  const grouped = catalog
    ? catalog.categories.map((c) => ({
        category: c,
        products: catalog.products.filter((p) => p.category === c),
      }))
    : [];
  const totalLines = cart.length + customLines.length;

  return (
    <AppShell active="Services" title="Ousus services"
              subtitle="Add catalog products to your request — or describe something custom to the assistant.">

      {/* catalogue PDFs */}
      {catalogs.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {catalogs.map((c) => (
            <a key={c.url} href={c.url} target="_blank" rel="noreferrer"
               className="flex items-center gap-2 border border-border bg-card px-3 py-2 font-mono text-[11px] text-muted-foreground hover:border-primary hover:text-primary">
              <FileDown className="size-3.5" />{c.title}
            </a>
          ))}
        </div>
      )}

      {/* mini cart indicator */}
      {totalLines > 0 && !chatOpen && (
        <div className="flex items-center justify-between border border-primary/40 bg-primary/10 px-4 py-3">
          <span className="font-mono text-xs text-foreground">
            {cart.length} product{cart.length !== 1 ? "s" : ""}
            {customLines.length ? ` + ${customLines.length} custom` : ""} in your request
          </span>
          <a href="#your-request" className="font-mono text-[11px] text-primary hover:underline">
            Review &amp; submit ↓
          </a>
        </div>
      )}

      {loadError && (
        <div className="border border-destructive/40 p-4">
          <p className="font-mono text-xs text-destructive">{loadError}</p>
          <button onClick={loadCatalog} className="mt-2 border border-border px-3 py-1.5 font-mono text-[11px] text-muted-foreground hover:text-foreground">
            Retry
          </button>
        </div>
      )}

      {/* product grid */}
      {!catalog && !loadError ? (
        <p className="font-mono text-xs text-muted-foreground">Loading catalog…</p>
      ) : (
        grouped.map(({ category, products }) => (
          <section key={category}>
            <h2 className="mb-3 mt-2 font-mono text-sm font-bold uppercase tracking-wider text-muted-foreground">
              {category}
            </h2>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {products.map((p) => (
                <div key={p.id} className="flex flex-col border border-border bg-card">
                  <img src={p.image} alt={p.name}
                       onError={(e) => { e.currentTarget.style.visibility = "hidden"; }}
                       className="h-32 w-full object-cover opacity-90" />
                  <div className="flex flex-1 flex-col p-4">
                    <b className="font-mono text-xs text-foreground">{p.name}</b>
                    <p className="mt-2 flex-1 font-mono text-[10px] leading-5 text-muted-foreground">
                      {p.description}
                    </p>
                    <div className="mt-3 flex items-center justify-between gap-2">
                      <span className="font-mono text-[9px] uppercase text-muted-foreground">per {p.unit}</span>
                      <button onClick={() => addToCart(p)}
                              className="flex items-center gap-1 border border-border px-3 py-1.5 font-mono text-[10px] text-muted-foreground hover:border-primary hover:text-primary">
                        <Plus className="size-3" /> Add
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>
        ))
      )}

      {/* custom object: chat */}
      <section className="border border-primary/30 bg-card p-5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="font-mono text-sm font-bold text-foreground">Need something custom?</h2>
            <p className="mt-1 font-mono text-[10px] leading-5 text-muted-foreground">
              {CUSTOM_CHAT_SCHEMA_NOTE}
            </p>
          </div>
          {!chatOpen && !chatDoneCode && (
            <button onClick={startChat} disabled={chatBusy}
                    className="flex shrink-0 items-center gap-2 bg-primary px-4 py-2.5 font-mono text-xs font-bold text-primary-foreground hover:opacity-90 disabled:opacity-50">
              <MessageSquare className="size-3.5" />
              {chatBusy ? "Connecting…" : "Describe it to the assistant"}
            </button>
          )}
        </div>

        {chatError && <p className="mt-3 font-mono text-xs text-destructive">{chatError}</p>}

        {chatOffline && chatOpen && (
          <button onClick={startChat} disabled={chatBusy}
                  className="mt-3 border border-border px-4 py-2 font-mono text-xs text-muted-foreground hover:text-foreground">
            Retry assistant
          </button>
        )}

        {chatDoneCode && (
          <p className="mt-3 font-mono text-xs text-primary">
            Custom request {chatDoneCode} submitted — track it in{" "}
            <Link href="/my" className="underline">My Projects</Link>.
          </p>
        )}

        {chatOpen && !chatDoneCode && (
          <div className="mt-4 border border-border">
            <div ref={chatBoxRef} style={{ maxHeight: 320, overflowY: "auto", padding: 12 }}>
              {chatMsgs.map((m, i) => (
                <div key={i} className={`mb-2 flex ${m.role === "client" ? "justify-end" : "justify-start"}`}>
                  <div style={{ whiteSpace: "pre-wrap" }}
                       className={`max-w-[80%] rounded-lg px-3 py-2 font-mono text-xs leading-6 ${m.role === "client" ? "bg-primary text-primary-foreground" : "bg-secondary text-foreground"}`}>
                    {m.text}
                  </div>
                </div>
              ))}
              {chatBusy && <p className="font-mono text-[10px] text-muted-foreground">Thinking…</p>}
            </div>
            <div className="flex items-center gap-2 border-t border-border p-3">
              <label className="cursor-pointer border border-border p-2.5 text-muted-foreground hover:border-primary hover:text-primary"
                     title="Attach reference photo">
                <Upload className="size-4" />
                <input type="file" accept="image/png,image/jpeg,image/webp" className="hidden"
                       onChange={(e) => attachPhoto(e.target.files?.[0])} disabled={chatBusy} />
              </label>
              <input value={chatInput} onChange={(e) => setChatInput(e.target.value)}
                     onKeyDown={(e) => e.key === "Enter" && sendChat()}
                     placeholder="Type your answer…" disabled={chatBusy}
                     className="flex-1 border border-border bg-background px-3 py-2.5 font-mono text-xs text-foreground" />
              <button onClick={sendChat} disabled={chatBusy}
                      className="bg-primary px-4 py-2.5 font-mono text-xs font-bold text-primary-foreground hover:opacity-90 disabled:opacity-50">
                Send
              </button>
              <button onClick={() => setChatOpen(false)} aria-label="Close chat"
                      className="border border-border p-2.5 text-muted-foreground hover:text-foreground">
                <X className="size-4" />
              </button>
            </div>
          </div>
        )}
      </section>

      {/* your request */}
      <section id="your-request" className="border border-border bg-card p-5">
        <h2 className="font-mono text-sm font-bold text-foreground">Your request</h2>

        {totalLines > 0 ? (
          <table className="mt-3 w-full border-collapse">
            <tbody>
              {cart.map((c, i) => (
                <tr key={`c${i}`} className="border-b border-border">
                  <td className="py-2 font-mono text-xs text-foreground">{c.name}</td>
                  <td className="w-28 py-2">
                    <input type="number" min="0.1" step="any" value={c.qty}
                           onChange={(e) => changeQty(i, parseFloat(e.target.value))}
                           className="w-full border border-border bg-background px-2 py-1 font-mono text-xs text-foreground" />
                  </td>
                  <td className="w-8 py-2 text-right">
                    <button onClick={() => removeFromCart(i)} aria-label="Remove">
                      <Trash2 className="size-3.5 text-muted-foreground hover:text-destructive" />
                    </button>
                  </td>
                </tr>
              ))}
              {customLines.map((c, i) => (
                <tr key={`u${i}`} className="border-b border-border">
                  <td className="py-2 font-mono text-xs text-chart-2">
                    CUSTOM: {c.name}{c.photo ? " · photo attached" : ""}
                  </td>
                  <td colSpan={2} className="py-2 text-right">
                    <button onClick={() => setCustomLines(customLines.filter((_, j) => j !== i))}>
                      <Trash2 className="size-3.5 text-muted-foreground hover:text-destructive" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="mt-3 font-mono text-xs text-muted-foreground">
            Empty — add products above, or describe a custom object with the assistant.
          </p>
        )}

        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          <input placeholder="Request title *" value={form.title}
                 onChange={(e) => setForm({ ...form, title: e.target.value })}
                 className="border border-border bg-background px-3 py-2.5 font-mono text-xs text-foreground" />
          <input placeholder="Finish (optional — e.g. RAL 7016)" value={form.finish}
                 onChange={(e) => setForm({ ...form, finish: e.target.value })}
                 className="border border-border bg-background px-3 py-2.5 font-mono text-xs text-foreground" />
          <input placeholder="Site location (optional)" value={form.site}
                 onChange={(e) => setForm({ ...form, site: e.target.value })}
                 className="border border-border bg-background px-3 py-2.5 font-mono text-xs text-foreground" />
          <input placeholder="Deadline (e.g. within 6 weeks) *" value={form.required_raw}
                 onChange={(e) => setForm({ ...form, required_raw: e.target.value })}
                 className="border border-border bg-background px-3 py-2.5 font-mono text-xs text-foreground" />
        </div>

        {submitError && <p className="mt-3 font-mono text-xs text-destructive">{submitError}</p>}

        <button onClick={submitRequest} disabled={submitBusy || totalLines === 0}
                className="mt-4 w-full bg-primary py-3 font-mono text-xs font-bold text-primary-foreground hover:opacity-90 disabled:opacity-40">
          {submitBusy ? "Submitting…" : "Submit request for engineering review"}
        </button>
      </section>
    </AppShell>
  );
}
