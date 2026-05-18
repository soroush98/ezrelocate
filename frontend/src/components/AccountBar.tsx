"use client";

import { useState } from "react";
import { signOut, startCheckout, useMe } from "@/lib/auth";
import { AuthModal } from "./AuthModal";

/** Top-right account / subscribe controls. Reads /api/me via the useMe hook. */
export function AccountBar() {
  const { me, refresh } = useMe();
  const [modalOpen, setModalOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  async function onSubscribe() {
    setBusy(true);
    try {
      const url = await startCheckout();
      window.location.href = url;
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  if (!me || !me.authenticated) {
    return (
      <>
        <button
          onClick={() => setModalOpen(true)}
          className="rounded-full border border-line bg-white px-3 py-1.5 text-xs font-medium text-ink shadow-sm hover:border-brand-300"
        >
          Sign in
        </button>
        <AuthModal
          open={modalOpen}
          initialMode="signup"
          onClose={() => setModalOpen(false)}
          onSuccess={() => {
            setModalOpen(false);
            refresh();
          }}
        />
      </>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <span className="hidden text-[11px] text-ink-muted sm:inline">{me.email}</span>
      {me.subscribed ? (
        <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-medium text-emerald-800">
          Subscribed
        </span>
      ) : (
        <button
          onClick={onSubscribe}
          disabled={busy}
          className="rounded-full bg-brand-600 px-3 py-1.5 text-xs font-medium text-white shadow-sm hover:bg-brand-700 disabled:bg-slate-300"
        >
          {busy ? "…" : "Subscribe"}
        </button>
      )}
      <button
        onClick={async () => {
          await signOut();
          refresh();
        }}
        className="rounded-full border border-line bg-white px-2.5 py-1 text-[11px] text-ink-2 hover:border-brand-300"
      >
        Sign out
      </button>
    </div>
  );
}
