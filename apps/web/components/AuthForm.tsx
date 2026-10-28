"use client";

import { useState, type FormEvent } from "react";
import { ApiError, api, type Session } from "@/lib/api";

export function AuthForm({ onSignedIn }: { onSignedIn: (s: Session) => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onSignedIn(mode === "login" ? await api.login(email, password) : await api.register(email, password));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="panel auth" onSubmit={submit}>
      <div className="tabs" role="tablist">
        <button type="button" role="tab" aria-selected={mode === "login"} className={mode === "login" ? "active" : ""} onClick={() => setMode("login")}>
          Sign in
        </button>
        <button type="button" role="tab" aria-selected={mode === "register"} className={mode === "register" ? "active" : ""} onClick={() => setMode("register")}>
          Create account
        </button>
      </div>
      <label htmlFor="email">Email</label>
      <input id="email" type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
      <label htmlFor="password">Password</label>
      <input
        id="password"
        type="password"
        required
        minLength={mode === "register" ? 8 : undefined}
        autoComplete={mode === "login" ? "current-password" : "new-password"}
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      {mode === "register" && <p className="hint">At least 8 characters, with a letter and a digit.</p>}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <button type="submit" className="primary" disabled={busy}>
        {mode === "login" ? "Sign in" : "Create account"}
      </button>
    </form>
  );
}
