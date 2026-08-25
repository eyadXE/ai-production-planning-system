"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import AppShell from "../../components/AppShell";
import { addItem } from "../../lib/cart";
import { api } from "../../lib/api";

function ConfigInner() {
  const params = useSearchParams();
  const id = Number(params.get("id"));
  const [product, setProduct] = useState(null);
  const [qty, setQty] = useState(1);
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");
  const [added, setAdded] = useState(false);

  useEffect(() => {
    api("/products")
      .then((d) => {
        const p = d.products.find((x) => x.id === id);
        if (!p) setError("Product not found.");
        else setProduct(p);
      })
      .catch((e) => setError(e.message));
  }, [id]);

  function add() {
    if (!product) return;
    addItem({
      kind: product.est_kind || `custom_${product.id}`,
      qty: qty,
      name: product.name,
      finish: notes.trim(),
    });
    setAdded(true);
    setTimeout(() => {}, 0);
  }

  if (error) {
    return (
      <AppShell active="Configure" title="Configure">
        <div className="text-destructive">{error}</div>
      </AppShell>
    );
  }
  if (!product) {
    return (
      <AppShell active="Configure" title="Configure">
        <p className="font-mono text-xs text-muted-foreground">Loading…</p>
      </AppShell>
    );
  }

  if (added) {
    return (
      <AppShell active="Configure" title="Added to your request">
        <div className="border border-border bg-card p-8 text-center">
          <b className="font-mono text-sm text-foreground">{product.name}</b>
          <p className="mt-2 font-mono text-xs text-muted-foreground">qty {qty}</p>
          <div className="mt-6 flex justify-center gap-3">
            <Link href="/request" className="bg-primary px-4 py-2.5 font-mono text-xs font-bold text-primary-foreground hover:opacity-90">
              Review &amp; submit request
            </Link>
            <Link href="/request" className="border border-border px-4 py-2.5 font-mono text-xs text-muted-foreground hover:text-foreground">
              Keep browsing
            </Link>
          </div>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell active="Configure" title={product.name}>
      <div className="grid gap-8 lg:grid-cols-[1fr_1.2fr]">
        <img src={product.image} alt={product.name}
             onError={(e) => { e.currentTarget.style.display = "none"; }}
             className="w-full border border-border object-cover opacity-95"
             style={{ maxHeight: 320 }} />
        <div>
          <p className="font-mono text-[10px] uppercase tracking-wider text-primary">{product.category}</p>
          <h1 className="mt-2 font-mono text-xl font-bold text-foreground">{product.name}</h1>
          <p className="mt-3 font-mono text-xs leading-6 text-muted-foreground">{product.description}</p>

          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1 block font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                Quantity ({product.unit})</label>
              <input type="number" min="0.1" step="any" value={qty}
                     onChange={(e) => setQty(parseFloat(e.target.value) || 1)}
                     className="w-full border border-border bg-background px-3 py-2.5 font-mono text-xs text-foreground" />
            </div>
            <div>
              <label className="mb-1 block font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                Notes / special requirement (optional)</label>
              <input value={notes} onChange={(e) => setNotes(e.target.value)}
                     className="w-full border border-border bg-background px-3 py-2.5 font-mono text-xs text-foreground" />
            </div>
          </div>

          <button onClick={() => { add(); }}
                  className="mt-6 w-full bg-primary py-3 font-mono text-xs font-bold text-primary-foreground hover:opacity-90 sm:w-auto sm:px-8">
            Add to my request
          </button>
          <p className="mt-3 font-mono text-[10px] leading-5 text-muted-foreground">
            Finish/coating is decided with our engineers during planning — you can
            note a preference above.
          </p>
        </div>
      </div>
    </AppShell>
  );
}

export default function ConfigurePage() {
  return (
    <Suspense fallback={null}>
      <ConfigInner />
    </Suspense>
  );
}
