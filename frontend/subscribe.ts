// subscribe.ts — mini-app email capture (same /api/subscribe as landing + bot).
// Telegram doesn't give you the email, so collect it in a screen with a consent
// checkbox, then call subscribe() below.

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export type Vertical = "crypto" | "casino" | "esports" | "football";

export interface SubscribeInput {
  email: string;
  verticals: Vertical[];
  consent: boolean;          // must be an explicit, un-prechecked opt-in
  lang?: string;
}

export interface SubscribeResult {
  ok: boolean;
  status?: "pending" | "already_confirmed";
  error?: "invalid_email" | "consent_required" | "geo_restricted";
  reason?: string;
}

export async function subscribe(input: SubscribeInput): Promise<SubscribeResult> {
  const tg = (window as any).Telegram?.WebApp;
  const tgId = tg?.initDataUnsafe?.user?.id;
  const lang = input.lang ?? tg?.initDataUnsafe?.user?.language_code?.slice(0, 2) ?? "en";

  const res = await fetch(`${API_BASE}/api/subscribe`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: input.email.trim(),
      verticals: input.verticals,
      consent: input.consent,
      lang,
      tg_id: tgId,
      source: "bot_miniapp",
      // wrapper is decided by the backend (WRAPPER_TYPE); omit here.
    }),
  });
  return res.json();
}
