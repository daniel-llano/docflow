"use client";

import { useCallback, useEffect, useState } from "react";
import { AuthForm } from "@/components/AuthForm";
import { Dashboard } from "@/components/Dashboard";
import { loadSession, saveSession, type Session } from "@/lib/api";

export default function HomePage() {
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setSession(loadSession());
    setReady(true);
  }, []);

  const signOut = useCallback(() => {
    saveSession(null);
    setSession(null);
  }, []);

  return (
    <main>
      <header className="row spread top">
        <div>
          <h1>DocFlow</h1>
          <p className="muted">Upload a document and get a summary, keywords, amounts, dates, and a copy with personal data masked.</p>
        </div>
        {session && (
          <div className="row">
            <span className="muted small">{session.email}</span>
            <button type="button" onClick={signOut}>
              Sign out
            </button>
          </div>
        )}
      </header>
      {ready &&
        (session ? (
          <Dashboard onUnauthorized={signOut} />
        ) : (
          <AuthForm
            onSignedIn={(s) => {
              saveSession(s);
              setSession(s);
            }}
          />
        ))}
    </main>
  );
}
