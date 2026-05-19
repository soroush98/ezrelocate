"use client";

import { createBrowserClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";

// Singleton — one client per browser tab.
let _client: SupabaseClient | null = null;
let _warned = false;

/** Returns the Supabase client, or null if env vars are missing.
 * Callers that allow anonymous use (useMe, apiFetch) should accept null and
 * fall back to unauthenticated behavior. Callers that require auth
 * (sign in/up, checkout) should call `requireSupabase()` instead. */
export function supabase(): SupabaseClient | null {
  if (_client) return _client;
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) {
    if (!_warned && typeof window !== "undefined") {
      _warned = true;
      console.warn(
        "[supabase] NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY not set — " +
          "auth and billing UI will be disabled. Add them to frontend/.env.local for local dev."
      );
    }
    return null;
  }
  _client = createBrowserClient(url, key);
  return _client;
}

export function requireSupabase(): SupabaseClient {
  const c = supabase();
  if (!c) {
    throw new Error(
      "Supabase isn't configured. Set NEXT_PUBLIC_SUPABASE_URL and " +
        "NEXT_PUBLIC_SUPABASE_ANON_KEY in frontend/.env.local (or on Vercel)."
    );
  }
  return c;
}
