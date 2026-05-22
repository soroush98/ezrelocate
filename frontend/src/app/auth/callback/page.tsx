"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { requireSupabase } from "@/lib/supabase";

export default function AuthCallbackPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const url = window.location.href;
        const { error } = await requireSupabase().auth.exchangeCodeForSession(url);
        if (error) throw error;
        router.replace("/");
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    })();
  }, [router]);

  return (
    <div className="grid min-h-screen place-items-center p-6 text-sm text-ink-muted">
      {error ? (
        <div className="max-w-md rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-rose-700">
          Sign-in failed: {error}
        </div>
      ) : (
        <div>Signing you in…</div>
      )}
    </div>
  );
}
