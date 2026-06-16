# Email capture + segmented campaigns — rework (pilot: Cherry Rush)

This turns the bots/mini-apps/landings into **email-collection funnels** that feed
**segmented campaigns by vertical**, EU-ready. Built on `cherry-rush` as the pilot;
replicate to the other 4 brands the same way we did the polish pass.

## The core decision: own the list, treat the ESP as a swappable output

```
 Landing (Lovable) ┐
 Bot chat /subscribe ├──> /api/subscribe ──> Postgres (system of record) ──> double opt-in
 Mini-app screen   ┘                          + consent log (GDPR proof)        │
                                                                                ▼
                                              on confirm → route by segment → ESP
                                                soft (crypto/esports/football) → Mailchimp
                                                hard (casino/sports betting)   → iGaming ESP
```

Why: **Mailchimp prohibits gambling content and terminates iGaming accounts — often
freezing the list.** So Mailchimp is *one output for the soft segment only*, never the
foundation and never the gambling segment. Your own Postgres is the source of truth;
if any ESP bans you, the list is still yours and you re-point the sync.

Transactional mail (the opt-in/confirmation + welcome) goes through a **separate**
sender (`emailer.py`, SMTP) — it's transactional, so it isn't subject to the marketing
provider's content rules.

## What I decided (you said "as you see fit")

- **Pilot wrapper:** `promo_feed` (cleanest to debug capture→consent→opt-in→sync end-to-end).
  Other wrappers (`tips`, `bonus`, `wheel`, `vip`) are config variants — one engine.
- **Store:** Postgres via `DATABASE_URL` (Railway's FS is ephemeral; emails must persist).
  JSON fallback exists for local dev only.
- **Consent:** explicit, versioned, logged with timestamp + IP + source. Double opt-in.
- **Geo:** per-country gate on the gambling segment, env-driven (default deny-set is a
  conservative starting point — confirm with compliance).

## New files

| file | role |
|------|------|
| `emaildb.py` | contact store (Postgres / JSON) + consent log |
| `emailgeo.py` | EU per-country allow/deny for the gambling segment |
| `emailcfg.py` | wrapper, consent text/version, ESP routing, rewards (all env-driven) |
| `emailer.py` | transactional sender (SMTP prod / OUTBOX dev) |
| `esp.py` | marketing ESP adapters (Mailchimp + Noop) + segment routing |
| `capture.py` | orchestration: subscribe / confirm / unsubscribe / erase + email templates |
| `email_flow.py` | in-chat capture (PTB ConversationHandler) |
| `frontend/landing/index.html` | Lovable lead-capture landing (config-parameterized) |
| `frontend/subscribe.ts` | mini-app `subscribe()` helper (same endpoint) |

`api.py` gained: `POST /api/subscribe`, `GET /api/confirm?t=`, `GET /api/unsubscribe?t=`,
`POST /api/erase`. `requirements.txt` gained `psycopg[binary]`.

## API contract

```
POST /api/subscribe   {email, verticals[], consent:true, lang, country?, source, wrapper?, tg_id?}
                      → {ok, status:"pending"|"already_confirmed"} | {ok:false, error}
GET  /api/confirm?t=TOKEN        → HTML page (marks confirmed, pushes to ESP)
GET  /api/unsubscribe?t=TOKEN    → HTML page
POST /api/erase       {email, brand?}   → {ok}      (GDPR erasure)
```

## Env (set per Railway service)

```
DATABASE_URL=postgres://...              # Railway Postgres plugin
PUBLIC_API_BASE=https://<backend>.up.railway.app   # for confirm/unsub links in emails
SITE_BASE=https://<lovable-site>         # post-confirm landing
WRAPPER_TYPE=promo_feed                   # promo_feed|tips|bonus|wheel|vip
CONSENT_VERSION=2026-06-v1

# transactional sender (opt-in/welcome) — any SMTP
SMTP_HOST=... SMTP_PORT=587 SMTP_USER=... SMTP_PASS=... EMAIL_FROM="Cherry Rush <hi@...>"

# marketing ESP routing
ESP_SOFT=mailchimp                        # crypto/esports/football
ESP_HARD=noop                             # ← set once an iGaming-tolerant ESP is chosen
MAILCHIMP_API_KEY=...  MAILCHIMP_LIST_ID=...  MAILCHIMP_DC=us21
EMAIL_HARD_VERTICALS=casino,sports,betting

# geo gate (gambling segment)
EMAIL_GEO_MODE=deny_list                  # allow_all|deny_list|allow_list
EMAIL_GEO_DENY=IT,ES,DE,NL,BE,PL,FR       # starting point — confirm with compliance

# wrapper rewards (shown after opt-in)
REWARD_PROMO_URL=...  REWARD_CODE=...  REWARD_WHEEL_URL=...
```

## Three capture surfaces, one core

- **Landing (Lovable):** drop `frontend/landing/index.html`, set `CONFIG.API_BASE` to the
  backend origin and `CONFIG.privacyUrl`. Reskins per brand via the `CONFIG` block + tokens.
- **Bot chat:** wire `email_flow.build_email_conversation(_detect_lang)` into `bot.py`
  and expose `/subscribe` (or a button). Explicit consent → email → opt-in mail.
- **Mini-app:** call `subscribe()` from `frontend/subscribe.ts` with `tg_id` from
  `Telegram.WebApp` and `source:"bot_miniapp"` — same endpoint, same DB.

## Compliance baked in (EU)

- Double opt-in; consent text **versioned** and stored with ts/IP/source (provable).
- Unsubscribe link in every email; `/api/unsubscribe` flips status (suppressed from sync).
- `/api/erase` for right-to-erasure.
- 18+ everywhere; per-country gambling gate on the hard segment.
- Mailchimp never receives the gambling segment (hard guard in `esp.py`).

## Testing the wrappers (the real metric)

Each contact carries `source` + `wrapper` + `brand` + `verticals`. Measure not signups
but **FTD per email** downstream via the Voonix / BigQuery pipeline. Expect `wheel`/`bonus`
to win on signup volume and lose on quality; `promo_feed`/`tips` the reverse. Run them as
parallel deploys (same engine, different `WRAPPER_TYPE`) and compare on quality, not count.

## Status & next

- ✅ Core built and tested end-to-end (subscribe→opt-in→confirm→ESP route→unsub→erase),
  consent log verified, geo gate verified.
- ⏳ **Pick the iGaming-tolerant ESP** for `ESP_HARD` (the one open decision) — then it's a
  one-line adapter + env.
- ⏳ Replicate to BLAZE + lime-feed + owl-digest + kinetic-streams (same files + env).
- ⏳ Wire the mini-app email screen (helper provided) and add the `/subscribe` button in bots.
```
