"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { FileDown, Plus, Trash2, Upload } from "lucide-react";
import AppShell from "../../components/AppShell";
import { api, getUser } from "../../lib/api";

function CatalogInner() {
  const [user, setUser] = useState(null);
  useEffect(() => setUser(getUser()), []);
  const [catalog, setCatalog] = useState(null);
  const [catalogs, setCatalogs] = useState([]);
  const [cart, setCart] = useState([]);
  const [custom, setCustom] = useState([]);
  const [form, setForm] = useState({ title: "", finish: "", site: "", required_raw: "" });
  const [error, setError] = useState("");
  const [doneCode, setDoneCode] = useState(null);
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [customDraft, setCustomDraft] = useState({ name: "", description: "", photo: "" });

  useEffect(() => {
    api("/products").then((d) => { setCatalog(d); setCatalogs(d.catalogs || []); }).catch((e) => setError(e.message));
  }, []);

  if (!user || user.role !== "client") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-6">
        <div className="max-w-md border border-border bg-card p-8 text-center">
          <h3 className="font-mono text-sm font-bold text-foreground">Browse our services</h3>
          <p className="mt-3 font-mono text-xs leading-6 text-muted-foreground">
            Sign in with a client account to add products to a request.
          </p>
          <Link href="/login?mode=signup" className="mt-5 inline-block bg-primary px-5 py-3 font-mono text-xs font-bold text-primary-foreground hover:opacity-90">
            Create account
          </Link>
        </div>
      </div>
    );
  }

  function addToCart(p) {
    if (!p.est_kind) {
      setCustom([...custom, { name: p.name, description: p.description + " (standard product)", photo: "" }]);
      return;
    }
    const existing = cart.find((c) => c.kind === p.est_kind && c.name === p.name);
    if (existing) {
      setCart(cart.map((c) => (c === existing ? { ...c, qty: c.qty + 1 } : c)));
    } else {
      setCart([...cart, { kind: p.est_kind, qty: 1, name: p.name }]);
    }
  }

  async function uploadPhoto(file) {
    if (!file) return;
    setUploading(true); setError("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch("/api/uploads", {
        method: "POST",
        headers: { Authorization: `Bearer ${localStorage.getItem("ousus_token")}` },
        body: fd,
      });
      const out = await res.json();
      if (!res.ok) throw new Error(typeof out.detail === "string" ? out.detail : "upload failed");
      setCustomDraft((d) => ({ ...d, photo: out.url }));
    } catch (e) { setError(e.message); } finally { setUploading(false); }
  }

  async function submit() {
    setBusy(true); setError("");
    try {
      const out = await api("/requests", {
        method: "POST",
        body: {
          title: form.title || "Service request",
          items: cart.map(({ kind, qty }) => ({ kind, qty })),
          custom,
          finish: form.finish, site: form.site, required_raw: form.required_raw,
        },
      });
      setDoneCode(out.code);
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }

  if (doneCode) {
    return (
      <AppShell active="Services" title="Request submitted">
        <div className="border border-border bg-card p-8 text-center">
          <p className="font-mono text-sm text-foreground">
            Request <b className="text-primary">{doneCode}</b> submitted — an engineer will review it and you&apos;ll get an email at every step.
          </p>
          <div className="mt-6 flex justify-center gap-3">
            <Link href="/my" className="bg-primary px-4 py-2.5 font-mono text-xs font-bold text-primary-foreground hover:opacity-90">My Projects</Link>
            <button onClick={() => { setDoneCode(null); setCart([]); setCustom([]); }}
                    className="border border-border px-4 py-2.5 font-mono text-xs text-muted-foreground">New request</button>
          </div>
        </div>
      </AppShell>
    );
  }

  const grouped = catalog
    ? catalog.categories.map((c) => ({ category: c, products: catalog.products.filter((p) => p.category === c) }))
    : [];

  return (
    <AppShell active="Services" title="Ousus services"
              subtitle="Browse what we fabricate, add to your request, or describe something custom.">
      <div className="flex flex-wrap gap-2">
        {catalogs.map((c) => (
          <a key={c.url} href={c.url} target="_blank" rel="noreferrer"
             className="flex items-center gap-2 border border-border bg-card px-3 py-2 font-mono text-[11px] text-muted-foreground hover:border-primary hover:text-primary">
            <FileDown className="size-3.5" />{c.title}
          </a>
        ))}
      </div>

      {error && <div className="text-destructive">{error}</div>}

      {!catalog ? <p className="font-mono text-xs text-muted-foreground">Loading…</p> :
        grouped.map(({ category, products }) => (
          <section key={category}>
            <h2 className="mb-3 mt-2 font-mono text-sm font-bold uppercase tracking-wider text-muted-foreground">{category}</h2>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {products.map((p) => (
                <div key={p.id} className="flex flex-col border border-border bg-card">
                  <img src={p.image} alt={p.name} className="h-32 w-full object-cover opacity-90" />
                  <div className="flex flex-1 flex-col p-4">
                    <b className="font-mono text-xs text-foreground">{p.name}</b>
                    <p className="mt-2 flex-1 font-mono text-[10px] leading-5 text-muted-foreground">{p.description}</p>
                    <button onClick={() => addToCart(p)}
                            className="mt-3 flex items-center justify-center gap-1 border border-border py-2 font-mono text-[10px] text-muted-foreground hover:border-primary hover:text-primary">
                      <Plus className="size-3" />
                      Add{p.unit !== "count" ? ` (${p.unit})` : ""}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </section>
        ))}

      <section className="border border-primary/30 bg-card p-5">
        <h2 className="font-mono text-sm font-bold text-foreground">Need something custom?</h2>
        <p className="mt-1 font-mono text-[10px] text-muted-foreground">
          Describe it and attach a reference photo — engineers will plan it manually.
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <input placeholder="Name (e.g. Spiral staircase)" value={customDraft.name}
                 onChange={(e) => setCustomDraft({ ...customDraft, name: e.target.value })}
                 className="border border-border bg-background px-3 py-2.5 font-mono text-xs text-foreground" />
          <label className="flex cursor-pointer items-center justify-center gap-2 border border-dashed border-border px-3 py-2.5 font-mono text-[11px] text-muted-foreground hover:border-primary">
            <Upload className="size-3.5" />
            {uploading ? "Uploading…" : customDraft.photo ? "Photo attached ✓" : "Attach reference photo"}
            <input type="file" accept="image/png,image/jpeg,image/webp" className="hidden"
                   onChange={(e) => uploadPhoto(e.target.files?.[0])} disabled={uploading} />
          </label>
          <textarea placeholder="Description — dimensions, material, anything useful"
                    value={customDraft.description}
                    onChange={(e) => setCustomDraft({ ...customDraft, description: e.target.value })}
                    rows={2}
                    className="sm:col-span-2 border border-border bg-background px-3 py-2.5 font-mono text-xs text-foreground" />
        </div>
        <button disabled={!customDraft.name || uploading}
                onClick={() => { setCustom([...custom, customDraft]); setCustomDraft({ name: "", description: "", photo: "" }); }}
                className="mt-3 border border-primary/50 px-4 py-2 font-mono text-xs text-primary hover:bg-primary/10 disabled:opacity-40">
          + Add custom object
        </button>
      </section>

      <section className="border border-border bg-card p-5">
        <h2 className="font-mono text-sm font-bold text-foreground">Your request</h2>

        {cart.length + custom.length > 0 ? (
          <table className="mt-3 w-full border-collapse">
            <tbody>
              {cart.map((c, i) => (
                <tr key={`c${i}`} className="border-b border-border">
                  <td className="py-2 font-mono text-xs text-foreground">{c.name}</td>
                  <td className="w-28 py-2">
                    <input type="number" min="0.1" step="any" value={c.qty}
                           onChange={(e) => setCart(cart.map((x, j) => (j === i ? { ...x, qty: parseFloat(e.target.value) || x.qty } : x)))}
                           className="w-full border border-border bg-background px-2 py-1 font-mono text-xs text-foreground" />
                  </td>
                  <td className="w-8 py-2">
                    <button onClick={() => setCart(cart.filter((_, j) => j !== i))}>
                      <Trash2 className="size-3.5 text-muted-foreground hover:text-destructive" />
                    </button>
                  </td>
                </tr>
              ))}
              {custom.map((c, i) => (
                <tr key={`u${i}`} className="border-b border-border">
                  <td className="py-2 font-mono text-xs text-chart-2">
                    CUSTOM: {c.name}{c.photo && " · photo attached"}
                  </td>
                  <td className="py-2 font-mono text-[10px] text-muted-foreground">manual plan</td>
                  <td className="w-8 py-2">
                    <button onClick={() => setCustom(custom.filter((_, j) => j !== i))}>
                      <Trash2 className="size-3.5 text-muted-foreground hover:text-destructive" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="mt-3 font-mono text-xs text-muted-foreground">Empty — add products above or describe a custom object.</p>
        )}

        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          <input placeholder="Request title" value={form.title}
                 onChange={(e) => setForm({ ...form, title: e.target.value })}
                 className="border border-border bg-background px-3 py-2.5 font-mono text-xs text-foreground" />
          <input placeholder="Finish (e.g. shop paint RAL 7016 — optional)" value={form.finish}
                 onChange={(e) => setForm({ ...form, finish: e.target.value })}
                 className="border border-border bg-background px-3 py-2.5 font-mono text-xs text-foreground" />
          <input placeholder="Site location (optional)" value={form.site}
                 onChange={(e) => setForm({ ...form, site: e.target.value })}
                 className="border border-border bg-background px-3 py-2.5 font-mono text-xs text-foreground" />
          <input placeholder="Deadline (e.g. within 6 weeks)" value={form.required_raw}
                 onChange={(e) => setForm({ ...form, required_raw: e.target.value })}
                 className="border border-border bg-background px-3 py-2.5 font-mono text-xs text-foreground" />
        </div>

        <button onClick={submit} disabled={busy || cart.length + custom.length === 0}
                className="mt-4 w-full bg-primary py-3 font-mono text-xs font-bold text-primary-foreground hover:opacity-90 disabled:opacity-40">
          {busy ? "Submitting…" : "Submit request for engineering review"}
        </button>
      </section>
    </AppShell>
  );
}

export default function RequestChat() {
  return <CatalogInner />;
}
