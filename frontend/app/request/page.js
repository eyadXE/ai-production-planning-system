"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { FileDown, MessageSquare, Paperclip, Plus, Trash2 } from "lucide-react";
import AppShell from "../../components/AppShell";
import { api, getUser } from "../../lib/api";
import { addCustom, addItem, clearCart, getCart, removeLine, setQty } from "../../lib/cart";

export default function RequestPage() {
  const [ready, setReady] = useState(false);
  const [user, setUser] = useState(null);
  const [tab, setTab] = useState("catalog");
  const chatBoxRef = useRef(null);

  // catalog
  const [catalog, setCatalog] = useState(null);
  const [catalogs, setCatalogs] = useState([]);
  // cart
  const [cart, setCart] = useState({ items: [], custom: [] });
  const refreshCart = () => setCart(getCart());

  // checkout
  const [form, setForm] = useState({ title: "", site: "", required_raw: "" });
  const [submitBusy, setSubmitBusy] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [submittedCode, setSubmittedCode] = useState(null);

  // custom chat
  const [chatMsgs, setChatMsgs] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [chatSession, setChatSession] = useState(null);
  const [chatOffline, setChatOffline] = useState(false);
  const [chatDoneCode, setChatDoneCode] = useState(null);
  const [cartCount, setCartCount] = useState(0);

  useEffect(() => {
    setUser(getUser());
    api("/products")
      .then((d) => { setCatalog(d); setCatalogs(d.catalogs || []); })
      .catch(() => {});
    refreshCart();
    setReady(true);
  }, []);

  useEffect(() => {
    chatBoxRef.current?.scrollTo(0, chatBoxRef.current.scrollHeight);
  }, [chatMsgs]);

  if (!ready) return null;

  if (!user || user.role !== "client") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-6">
        <div className="max-w-md border border-border bg-card p-8 text-center">
          <h3 className="font-mono text-sm font-bold text-foreground">Browse our services</h3>
          <p className="mt-3 font-mono text-xs leading-6 text-muted-foreground">
            Sign in with a client account to build a request.
          </p>
          <Link href="/login?mode=signup"
                className="mt-5 inline-block bg-primary px-5 py-3 font-mono text-xs font-bold text-primary-foreground hover:opacity-90">
            Create account
          </Link>
        </div>
      </div>
    );
  }

  if (chatDoneCode) {
    return (
      <AppShell active="New request" title="Added to your request">
        <div className="border border-border bg-card p-8 text-center">
          <p className="font-mono text-sm text-foreground">
            Your custom build was added. Keep shopping or go to
            <b className="text-foreground"> Step 3 · Review &amp; submit</b>.
          </p>
          <div className="mt-6 flex justify-center gap-3">
            <button onClick={() => { setChatDoneCode(null); setTab("submit"); }}
                    className="bg-primary px-4 py-2.5 font-mono text-xs font-bold text-primary-foreground hover:opacity-90">
              Review &amp; submit
            </button>
          </div>
        </div>
      </AppShell>
    );
  }

  if (submittedCode) {
    const code = submittedCode;
    return (
      <AppShell active="New request" title="Request submitted">
        <div className="border border-border bg-card p-8 text-center">
          <p className="font-mono text-sm text-foreground">
            Request <b className="text-primary">{code}</b> submitted — an engineer
            will review it and you&apos;ll be notified at every step.
          </p>
          <div className="mt-6 flex justify-center gap-3">
            <Link href="/my" className="bg-primary px-4 py-2.5 font-mono text-xs font-bold text-primary-foreground hover:opacity-90">
              My Projects
            </Link>
            <button onClick={() => { setSubmittedCode(null); setChatDoneCode(null); refreshCart(); }}
                    className="border border-border px-4 py-2.5 font-mono text-xs text-muted-foreground hover:text-foreground">
              New request
            </button>
          </div>
        </div>
      </AppShell>
    );
  }

  // ---------- catalog ----------
  function chooseFromGrid(name) {
    // grid cards navigate via link — this is only a fallback
    const p = catalog?.products.find((x) => x.name === name);
    if (p) setSelected(p);
  }

  async function startChat() {
    setChatMsgs([]); setChatOffline(false); setChatBusy(true);
    try {
      const out = await api("/intake/start", { method: "POST" });
      if (!out.llm || !out.session_id) {
        setChatOffline(true);
        cPush("assistant",
          "The smart assistant is offline right now — press Retry in a moment.");
        return;
      }
      setChatSession(out.session_id);
      cPush("assistant", out.reply);
    } catch (e) {
      cPush("assistant", e.message);
    } finally { setChatBusy(false); }
  }

  function cPush(role, text) { setChatMsgs((m) => [...m, { role, text }]); }

  async function sendChat() {
    const text = chatInput.trim();
    if (!text || chatBusy || !chatSession) return;
    setChatInput(""); cPush("client", text); setChatBusy(true);
    try {
      const out = await api(`/intake/${chatSession}/message`, {
        method: "POST", body: { text },
      });
      cPush("assistant", out.reply);
      if (out.complete && out.code) setChatDoneCode(out.code);
    } catch (e) {
      cPush("assistant", e.message);
    } finally { setChatBusy(false); }
  }

  async function attachChatPhoto(file) {
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
    } finally { setChatBusy(false); }
  }

  async function submitRequest() {
    setSubmitBusy(true); setSubmitError("");
    try {
      const out = await api("/requests", {
        method: "POST",
        body: {
          title: form.title || "Service request",
          items: cart.items
            .filter((it) => !String(it.kind).startsWith("custom_"))
            .map(({ kind, qty }) => ({ kind, qty })),
          custom: [
            ...cart.custom,
            ...cart.items
              .filter((it) => String(it.kind).startsWith("custom_"))
              .map((it) => ({ name: it.name,
                              description: `${it.name} — catalogue product`,
                              photo: "" })),
          ],
          finish: "",
          site: form.site,
          required_raw: form.required_raw,
        },
      });
      clearCart();
      refreshCart();
      setSubmittedCode(out.code);
    } catch (e) { setSubmitError(e.message); } finally { setSubmitBusy(false); }
  }

  const grouped = catalog
    ? catalog.categories.map((c) => ({
        category: c,
        products: catalog.products.filter((p) => p.category === c),
      }))
    : [];
  const totalLines = cart.items.length + cart.custom.length;

  return (
    <AppShell active="New request" title="Build your request"
              subtitle="Pick catalog products, or describe something fully custom to the assistant. Then submit for engineering review.">

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

      {/* TABS */}
      <div className="flex gap-2">
        {[["catalog", "1 · Catalog products"], ["custom", "2 · Fully custom build"], ["submit", "3 · Review & submit"]].map(([k, lbl]) => (
          <button key={k} onClick={() => setTab(k)}
                  className={`px-4 py-2.5 font-mono text-xs font-bold ${tab === k ? "bg-primary text-primary-foreground" : "border border-border text-muted-foreground hover:text-foreground"}`}>
            {lbl}
          </button>
        ))}
      </div>

      {/* ---------- TAB: catalog ---------- */}
      {tab === "catalog" && (
        <>
          {!catalog ? (
            <p className="font-mono text-xs text-muted-foreground">Loading catalog…</p>
          ) : (
            grouped.map(({ category, products }) => (
              <section key={category}>
                <h2 className="mb-3 mt-2 font-mono text-sm font-bold uppercase tracking-wider text-muted-foreground">{category}</h2>
                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                  {products.map((p) => (
                    <div key={p.id} className="flex flex-col border border-border bg-card">
                      <img src={p.image} alt={p.name}
                           onError={(e) => { e.currentTarget.style.visibility = "hidden"; }}
                           className="h-32 w-full object-cover opacity-90" />
                      <div className="flex flex-1 flex-col p-4">
                        <b className="font-mono text-xs text-foreground">{p.name}</b>
                        <p className="mt-2 flex-1 font-mono text-[10px] leading-5 text-muted-foreground">{p.description}</p>
                        <Link href={`/configure?id=${p.id}`}
                              className="mt-3 flex items-center justify-center gap-1 border border-border py-2 font-mono text-[10px] text-muted-foreground hover:border-primary hover:text-primary">
                          <Plus className="size-3" /> Choose &amp; configure{p.unit !== "count" ? ` (${p.unit})` : ""}
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            ))
          )}
        </>
      )}

      {/* ---------- TAB: custom chat ---------- */}
      {tab === "custom" && (
        <section className="border border-primary/30 bg-card p-5">
          {!chatSession && !chatBusy && (
            <div className="text-center">
              <MessageSquare className="mx-auto size-6 text-primary" />
              <p className="mt-3 font-mono text-xs leading-6 text-muted-foreground">
                Describe what you want built. The assistant asks exactly what an
                engineer needs, then submits for review.
              </p>
              <button onClick={startChat}
                      className="mt-4 bg-primary px-5 py-3 font-mono text-xs font-bold text-primary-foreground hover:opacity-90">
                Start the assistant
              </button>
            </div>
          )}
          {chatBusy && !chatMsgs.length && (
            <p className="font-mono text-xs text-muted-foreground">Connecting…</p>
          )}
          {chatMsgs.length > 0 && (
            <>
              <div ref={chatBoxRef} style={{ maxHeight: 360, overflowY: "auto", padding: 12 }}>
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
              {!chatDoneCode && (
                <div className="flex gap-2 border-t border-border p-3">
                  <input value={chatInput} onChange={(e) => setChatInput(e.target.value)}
                         onKeyDown={(e) => e.key === "Enter" && sendChat()}
                         placeholder="Type your answer…" disabled={chatBusy}
                         className="flex-1 border border-border bg-background px-3 py-2.5 font-mono text-xs text-foreground" />
                  <label className="cursor-pointer border border-border p-2.5 text-muted-foreground hover:border-primary hover:text-primary"
                         title="Attach reference photo">
                    <Paperclip className="size-4" />
                    <input type="file" accept="image/png,image/jpeg,image/webp" className="hidden"
                           onChange={(e) => attachChatPhoto(e.target.files?.[0])} disabled={chatBusy} />
                  </label>
                  <button onClick={sendChat} disabled={chatBusy}
                          className="bg-primary px-4 py-2.5 font-mono text-xs font-bold text-primary-foreground hover:opacity-90 disabled:opacity-50">Send</button>
                </div>
              )}
            </>
          )}
        </section>
      )}

      {/* ---------- TAB: review & submit ---------- */}
      {tab === "submit" && (
        <section id="your-request" className="border border-border bg-card p-5">
          <h3 className="mb-3 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            Your request · {totalLines} line{totalLines !== 1 ? "s" : ""}</h3>

          {totalLines > 0 ? (
            <table className="w-full border-collapse">
              <tbody>
                {cart.items.map((c, i) => (
                  <tr key={`i${i}`} className="border-b border-border">
                    <td className={`py-2 font-mono text-xs ${String(c.kind).startsWith("custom_") ? "text-chart-2" : "text-foreground"}`}>
                      {String(c.kind).startsWith("custom_") ? "CUSTOM (catalog): " : ""}{c.name}{c.finish ? ` · ${c.finish}` : ""}
                    </td>
                    <td className="w-24 py-2">
                      <input type="number" min="0.1" step="any" value={c.qty}
                             onChange={(e) => { setQty(i, parseFloat(e.target.value) || c.qty); refreshCart(); }}
                             className="w-full border border-border bg-background px-2 py-1 font-mono text-xs text-foreground" />
                    </td>
                    <td className="w-8 py-2 text-right">
                      <button onClick={() => { removeLine("item", i); refreshCart(); }} aria-label="Remove">
                        <Trash2 className="size-3.5 text-muted-foreground hover:text-destructive" />
                      </button>
                    </td>
                  </tr>
                ))}
                {cart.custom.map((c, i) => (
                  <tr key={`u${i}`} className="border-b border-border">
                    <td className="py-2 font-mono text-xs text-chart-2">CUSTOM: {c.name}{c.photo ? " · photo attached" : ""}</td>
                    <td colSpan={2} className="py-2 text-right">
                      <button onClick={() => { removeLine("custom", i); refreshCart(); }}>
                        <Trash2 className="size-3.5 text-muted-foreground hover:text-destructive" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="font-mono text-xs text-muted-foreground">
              Empty — pick products from the Catalog tab or describe a custom build.
            </p>
          )}

          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <input placeholder="Request title *" value={form.title}
                   onChange={(e) => setForm({ ...form, title: e.target.value })}
                   className="border border-border bg-background px-3 py-2.5 font-mono text-xs text-foreground" />
            <input placeholder="Site location (optional)" value={form.site}
                   onChange={(e) => setForm({ ...form, site: e.target.value })}
                   className="border border-border bg-background px-3 py-2.5 font-mono text-xs text-foreground" />
            <input placeholder="Deadline — optional (we estimate completion)" value={form.required_raw}
                   onChange={(e) => setForm({ ...form, required_raw: e.target.value })}
                   className="sm:col-span-2 border border-border bg-background px-3 py-2.5 font-mono text-xs text-foreground" />
          </div>

          {submitError && <p className="mt-3 font-mono text-xs text-destructive">{submitError}</p>}

          <button onClick={submitRequest} disabled={submitBusy || totalLines === 0}
                  className="mt-4 w-full bg-primary py-3 font-mono text-xs font-bold text-primary-foreground hover:opacity-90 disabled:opacity-40">
            {submitBusy ? "Submitting…" : `Submit request (${totalLines} line${totalLines !== 1 ? "s" : ""})`}
          </button>
        </section>
      )}
    </AppShell>
  );
}
