"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Factory } from "lucide-react";
import { api, setSession } from "../../lib/api";

function LoginInner() {
  const router = useRouter();
  const params = useSearchParams();
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({
    email: "", password: "", full_name: "",
    account_code: "", company_name: "",
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (params.get("mode") === "signup") setMode("signup");
  }, [params]);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setError(""); setBusy(true);
    try {
      const path = mode === "login" ? "/auth/login" : "/auth/signup";
      const body = mode === "login"
        ? { email: form.email, password: form.password }
        : {
            email: form.email,
            password: form.password,
            full_name: form.full_name,
            account_code: form.account_code || null,
            company_name: form.company_name || null,
          };
      const out = await api(path, { method: "POST", body });
      setSession(out.access_token, out.user);
      router.push(out.user.role === "client"
        ? (mode === "signup" ? "/request" : "/my")
        : "/summary");
    } catch (err) {
      setError(err.message);
    } finally { setBusy(false); }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-6">
      <div className="w-full max-w-md border border-border bg-card p-8">
        <div className="flex items-center gap-3">
          <div className="grid size-9 place-items-center bg-primary text-primary-foreground">
            <Factory className="size-4" />
          </div>
          <div>
            <p className="font-mono text-base font-bold tracking-tight text-foreground">OUSUS</p>
            <p className="font-mono text-[9px] uppercase tracking-[0.24em] text-muted-foreground">Operations OS</p>
          </div>
        </div>

        <h1 className="mt-6 font-mono text-xl font-bold text-foreground">
          {mode === "login" ? "Sign in" : "Create a client account"}
        </h1>
        <form onSubmit={submit} className="mt-5 flex flex-col gap-4">
          <div>
            <label className="mb-1 block font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Email</label>
            <input type="email" value={form.email} onChange={set("email")} required
                   className="w-full border border-border bg-background px-3 py-2.5 font-mono text-xs text-foreground" />
          </div>
          <div>
            <label className="mb-1 block font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Password</label>
            <input type="password" minLength={8} value={form.password} onChange={set("password")} required
                   className="w-full border border-border bg-background px-3 py-2.5 font-mono text-xs text-foreground" />
          </div>
          {mode === "signup" && (
            <>
              <div>
                <label className="mb-1 block font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Full name</label>
                <input value={form.full_name} onChange={set("full_name")} required
                       className="w-full border border-border bg-background px-3 py-2.5 font-mono text-xs text-foreground" />
              </div>
              <div>
                <label className="mb-1 block font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Company name (new customers)</label>
                <input placeholder="Leave blank to use your name" value={form.company_name} onChange={set("company_name")}
                       className="w-full border border-border bg-background px-3 py-2.5 font-mono text-xs text-foreground" />
              </div>
              <div>
                <label className="mb-1 block font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Existing account code (optional)</label>
                <input placeholder="e.g. AC-01" value={form.account_code} onChange={set("account_code")}
                       className="w-full border border-border bg-background px-3 py-2.5 font-mono text-xs text-foreground" />
                <p className="mt-2 font-mono text-[10px] leading-5 text-muted-foreground">
                  New here? Just use your name — we create your account automatically.
                  Staff sign-in is admin-provisioned.
                </p>
              </div>
            </>
          )}
          <button disabled={busy}
                  className="bg-primary px-4 py-3 font-mono text-xs font-bold text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
            {busy ? "…" : mode === "login" ? "Sign in" : "Create account & start request"}
          </button>
        </form>
        {error && <p className="mt-3 font-mono text-xs text-destructive">{error}</p>}
        <p className="mt-5 font-mono text-xs text-muted-foreground">
          {mode === "login" ? "New customer?" : "Have an account?"}{" "}
          <a href="#" onClick={(e) => { e.preventDefault(); setError(""); setMode(mode === "login" ? "signup" : "login"); }}
             className="text-primary hover:underline">
            {mode === "login" ? "Create an account" : "Sign in"}
          </a>
        </p>
        <p className="mt-4 border-t border-border pt-4 font-mono text-[10px] leading-5 text-muted-foreground">
          Demo staff: manager@ / engineer@ / client@oususapp.com — password demo1234
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginInner />
    </Suspense>
  );
}
