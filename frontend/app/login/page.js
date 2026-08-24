"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, setSession } from "../../lib/api";

export default function Login() {
  const router = useRouter();
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({
    email: "", password: "", full_name: "",
    role: "client", account_code: "",
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const path = mode === "login" ? "/auth/login"
        : "/auth/signup";
      const body = mode === "login"
        ? { email: form.email, password: form.password }
        : form;
      const out = await api(path, { method: "POST", body });
      setSession(out.access_token, out.user);
      router.push(out.user.role === "client" ? "/my" : "/board");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ maxWidth: 400, margin: "80px auto" }}>
      <div className="card">
        <h1>{mode === "login" ? "Sign in to Ousus" : "Create an account"}</h1>
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
              <label>Role</label>
              <select value={form.role} onChange={set("role")}>
                <option value="client">Client</option>
                <option value="engineer">Engineer / Estimator</option>
                <option value="manager">Manager</option>
                <option value="viewer">Viewer</option>
              </select>
              {form.role === "client" && (
                <>
                  <label>Company account code</label>
                  <input placeholder="AC-01" value={form.account_code}
                         onChange={set("account_code")} required />
                </>
              )}
            </>
          )}
          <div style={{ marginTop: 18 }}>
            <button className="btn" disabled={busy} style={{ width: "100%" }}>
              {busy ? "…" : mode === "login" ? "Sign in" : "Sign up"}
            </button>
          </div>
        </form>
        {error && <div className="error">{error}</div>}
        <p style={{ marginTop: 16, color: "var(--muted)" }}>
          {mode === "login" ? "No account?" : "Have an account?"}{" "}
          <a href="#" onClick={(e) => {
            e.preventDefault();
            setError("");
            setMode(mode === "login" ? "signup" : "login");
          }} style={{ color: "var(--accent)" }}>
            {mode === "login" ? "Sign up" : "Sign in"}
          </a>
        </p>
        <p className="meta" style={{ color: "var(--muted)", fontSize: 12 }}>
          Demo: manager@oususapp.com / engineer@oususapp.com / client@oususapp.com — password demo1234
        </p>
      </div>
    </div>
  );
}
