"use client";

import { useCallback, useEffect, useState } from "react";
import { requireSupabase, supabase } from "./supabase";

export type MeResponse =
  | { authenticated: false }
  | {
      authenticated: true;
      user_id: string;
      email: string | null;
      subscribed: boolean;
      subscription_status: string;
      current_period_end: string | null;
    };

async function authHeader(): Promise<HeadersInit> {
  const c = supabase();
  if (!c) return {};
  const { data } = await c.auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** Fetch wrapper that auto-attaches the Supabase JWT when the user is signed in. */
export async function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const headers = {
    ...(init.headers ?? {}),
    ...(await authHeader()),
  };
  return fetch(input, { ...init, headers });
}

/** Subscribes to Supabase auth state and tracks /api/me. */
export function useMe(): { me: MeResponse | null; refresh: () => void; loading: boolean } {
  const [me, setMe] = useState<MeResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiFetch("/api/me");
      if (!res.ok) {
        setMe({ authenticated: false });
        return;
      }
      setMe(await res.json());
    } catch {
      setMe({ authenticated: false });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const c = supabase();
    if (!c) return;
    const { data } = c.auth.onAuthStateChange(() => {
      refresh();
    });
    return () => {
      data.subscription.unsubscribe();
    };
  }, [refresh]);

  return { me, refresh, loading };
}

export async function signInWithPassword(email: string, password: string) {
  const { error } = await requireSupabase().auth.signInWithPassword({ email, password });
  if (error) throw error;
}

export async function signUpWithPassword(email: string, password: string) {
  const { error } = await requireSupabase().auth.signUp({ email, password });
  if (error) throw error;
}

export async function signInWithGoogle() {
  const { error } = await requireSupabase().auth.signInWithOAuth({
    provider: "google",
    options: {
      redirectTo: `${window.location.origin}/auth/callback`,
    },
  });
  if (error) throw error;
}

export async function signOut() {
  const c = supabase();
  if (!c) return;
  await c.auth.signOut();
}

export async function startCheckout(): Promise<string> {
  const res = await apiFetch("/api/billing/checkout", { method: "POST" });
  if (!res.ok) throw new Error(`checkout failed: HTTP ${res.status}`);
  const { url } = (await res.json()) as { url: string };
  return url;
}
