"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
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
    setError("");
    setBusy(true);
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
        : "/board");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ maxWidth: 400, margin: "80px auto" }}>
      <div className="card">
        <h1>{mode === "login" ? "Sign in to Ousus" : "Create a client account"}</h1>
        <form onSubmit={submit}>
          <label>Email</label>
          <input type="email" value={form.email} onChange={set("email")} required />
          <label>Password</label>
          <input type="password" value={form.password} onChange={set("password")}
                 minLength={8} required />
          {mode === "signup" && (
            <>
              <label>Full name</label>
              <input value={form.full_name} onChange={set("full_name")} required />
              <label>Company name <span style={{ opacity: .6 }}>(new customers)</span></label>
              <input placeholder="Leave blank to use your name"
                     value={form.company_name} onChange={set("company_name")} />
              <label>Existing account code <span style={{ opacity: .6 }}>(if your company already works with Ousus)</span></label>
              <input placeholder="e.g. AC-01 (optional)"
                     value={form.account_code} onChange={set("account_code")} />
              <p className="meta" style={{ color: "var(--muted)", fontSize: 12 }}>
                New here? Just use your name — we create your account
                automatically. Staff sign-in is admin-provisioned.
              </p>
            </>
          )}
          <div style={{ marginTop: 18 }}>
            <button className="btn" disabled={busy} style={{ width: "100%" }}>
              {busy ? "…" : mode === "login" ? "Sign in" : "Create account & start request"}
            </button>
          </div>
        </form>
        {error && <div className="error">{error}</div>}
        <p style={{ marginTop: 16, color: "var(--muted)" }}>
          {mode === "login" ? "New customer?" : "Have an account?"}{" "}
          <a href="#" onClick={(e) => {
            e.preventDefault();
            setError("");
            setMode(mode === "login" ? "signup" : "login");
          }} style={{ color: "var(--accent)" }}>
            {mode === "login" ? "Create an account" : "Sign in"}
          </a>
        </p>
        <p className="meta" style={{ color: "var(--muted)", fontSize: 12 }}>
          Demo staff: manager@oususapp.com / engineer@oususapp.com / client@oususapp.com — password demo1234
        </p>
      </div>
    </div>
  );
}

function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginInner />
    </Suspense>
  );
}

export default LoginPage;
