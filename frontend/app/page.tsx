
"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getStoredAuthToken } from "@/lib/api";

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    const token = getStoredAuthToken();
    router.replace(token ? "/projects" : "/login");
  }, [router]);

  return (
    <main className="auth-page compact-shell">
      <div className="auth-card">
        <div className="brand-row">
          <span className="brand-mark">MV</span>
          <div>
            <strong>ModelVerse</strong>
            <small>AI ENGINEERING WORKSPACE</small>
          </div>
        </div>
        <p className="auth-subtitle">Loading your workspace…</p>
      </div>
    </main>
  );
}
