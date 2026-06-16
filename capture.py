"""
capture.py — orchestration for email capture (one core, used by landing + bot).

Flow:
  subscribe(payload)  → validate + consent + geo → store pending → send opt-in mail
  confirm(token)      → mark confirmed → push to ESP → return wrapper reward + welcome mail
  unsubscribe(token)  → mark unsubscribed
  erase(email, brand) → GDPR right-to-erasure
"""
import re
import logging

import emaildb
import emailgeo
import emailcfg
import emailer
import esp

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
VALID_VERTICALS = {"crypto", "casino", "sports", "esports", "football"}


def _valid_email(e: str) -> bool:
    return bool(e) and len(e) <= 254 and bool(_EMAIL_RE.match(e.strip()))


def _confirm_link(token: str) -> str:
    return f"{emailcfg.PUBLIC_API_BASE}/api/confirm?t={token}"

def _unsub_link(token: str) -> str:
    return f"{emailcfg.PUBLIC_API_BASE}/api/unsubscribe?t={token}"


# ── email templates (kept short; 18+ + unsubscribe always present) ──────────
_SUBJ_CONFIRM = {
    "en": f"Confirm your subscription to {emailcfg.BRAND_NAME}",
    "ru": f"Подтвердите подписку на {emailcfg.BRAND_NAME}",
    "es": f"Confirma tu suscripción a {emailcfg.BRAND_NAME}",
}
_BODY_CONFIRM = {
    "en": ("Tap to confirm you want emails from {b}. If this wasn't you, ignore this message.",
           "Confirm subscription"),
    "ru": ("Нажми, чтобы подтвердить подписку на письма от {b}. Если это не ты — просто проигнорируй.",
           "Подтвердить подписку"),
    "es": ("Pulsa para confirmar que quieres correos de {b}. Si no fuiste tú, ignora este mensaje.",
           "Confirmar suscripción"),
}
_SUBJ_WELCOME = {
    "en": f"You're in — {emailcfg.BRAND_NAME}",
    "ru": f"Ты в деле — {emailcfg.BRAND_NAME}",
    "es": f"Ya estás dentro — {emailcfg.BRAND_NAME}",
}
_FOOTER = {
    "en": "18+ · You can unsubscribe anytime: {u}",
    "ru": "18+ · Отписаться можно в любой момент: {u}",
    "es": "18+ · Puedes darte de baja cuando quieras: {u}",
}


def _wrap_html(inner: str, footer: str) -> str:
    return (f'<div style="font-family:system-ui,Arial,sans-serif;max-width:520px;margin:auto">'
            f'{inner}<hr style="border:none;border-top:1px solid #eee;margin:24px 0">'
            f'<p style="color:#888;font-size:12px">{footer}</p></div>')


async def _send_confirm(rec):
    lang = rec.get("lang") or "en"
    if lang not in _SUBJ_CONFIRM:
        lang = "en"
    body, btn = _BODY_CONFIRM[lang]
    body = body.format(b=emailcfg.BRAND_NAME)
    link = _confirm_link(rec["confirm_token"])
    footer = _FOOTER[lang].format(u=_unsub_link(rec["unsub_token"]))
    html = _wrap_html(
        f'<h2>{emailcfg.BRAND_NAME}</h2><p>{body}</p>'
        f'<p><a href="{link}" style="background:#111;color:#fff;padding:12px 20px;'
        f'border-radius:8px;text-decoration:none;display:inline-block">{btn}</a></p>'
        f'<p style="color:#888;font-size:12px">{link}</p>', footer)
    text = f"{body}\n\n{link}\n\n{footer}"
    await emailer.send(rec["email"], _SUBJ_CONFIRM[lang], html, text)


async def _send_welcome(rec, reward):
    lang = rec.get("lang") or "en"
    if lang not in _SUBJ_WELCOME:
        lang = "en"
    footer = _FOOTER[lang].format(u=_unsub_link(rec["unsub_token"]))
    lines = {"en": "You're confirmed. Here's what's next:",
             "ru": "Подписка подтверждена. Что дальше:",
             "es": "Suscripción confirmada. Esto es lo que sigue:"}[lang]
    extra = ""
    if reward.get("code"):
        extra = f'<p>Code: <b>{reward["code"]}</b></p>'
    elif reward.get("url"):
        extra = f'<p><a href="{reward["url"]}">{reward["url"]}</a></p>'
    html = _wrap_html(f'<h2>{emailcfg.BRAND_NAME}</h2><p>{lines}</p>{extra}', footer)
    text = f"{lines}\n{reward.get('code') or reward.get('url') or ''}\n\n{footer}"
    await emailer.send(rec["email"], _SUBJ_WELCOME[lang], html, text)


def _reward_for(wrapper: str) -> dict:
    r = emailcfg.REWARD
    return {
        "promo_feed": {"type": "promo", "url": r["promo_url"]},
        "tips":       {"type": "tips"},
        "bonus":      {"type": "code", "code": r["code"]},
        "wheel":      {"type": "wheel", "url": r["wheel_url"]},
        "vip":        {"type": "vip", "url": r["promo_url"]},
    }.get(wrapper, {"type": "promo", "url": r["promo_url"]})


# ── public orchestration ────────────────────────────────────────────────────
async def subscribe(payload: dict, ip: str = "") -> tuple[int, dict]:
    email = (payload.get("email") or "").strip()
    consent = bool(payload.get("consent"))
    lang = (payload.get("lang") or "en").lower()
    if lang not in ("en", "ru", "es"):
        lang = "en"
    country = (payload.get("country") or "").upper()
    source = (payload.get("source") or "landing").lower()
    wrapper = (payload.get("wrapper") or emailcfg.WRAPPER).lower()
    tg_id = payload.get("tg_id")
    verticals = [v for v in (payload.get("verticals") or []) if v in VALID_VERTICALS]

    if not _valid_email(email):
        return 400, {"ok": False, "error": "invalid_email"}
    if not consent:
        return 400, {"ok": False, "error": "consent_required"}

    # Geo gate applies to the gambling (hard) segment only.
    seg = emailcfg.segment_for(verticals)
    if seg == "hard":
        status, reason = emailgeo.country_status(country)
        if status == "block":
            logger.info(f"geo-blocked subscribe {email} cc={country}: {reason}")
            return 200, {"ok": False, "error": "geo_restricted", "reason": reason}

    consent_text = emailcfg.CONSENT_TEXT.get(lang, emailcfg.CONSENT_TEXT["en"])
    rec, is_new = emaildb.upsert_pending(
        email, emailcfg.BRAND_ID, verticals=verticals, source=source, wrapper=wrapper,
        lang=lang, country=country, tg_id=tg_id, consent_text=consent_text,
        consent_ver=emailcfg.CONSENT_VERSION, ip=ip,
    )

    email_lc = email.strip().lower()
    already_confirmed = (rec["status"] == "confirmed")

    # Если контакт уже подтверждён И уже успешно доехал до ESP — нечего делать.
    if already_confirmed and rec.get("esp_ok"):
        return 200, {"ok": True, "status": "already_confirmed",
                     "esp": {"esp": rec.get("esp_name"), "ok": True}}

    # Single opt-in: подтверждаем локально (если ещё не подтверждён),
    # затем ВСЕГДА пушем в ESP — в т.ч. ре-пуш для записей, где прошлый пуш упал.
    if not already_confirmed:
        emaildb.mark(email_lc, emailcfg.BRAND_ID, "confirmed")
        rec["status"] = "confirmed"

    report = await esp.push_contact(rec)
    # Сохраняем результат как источник правды — теперь ре-синк сможет добрать неудачные.
    emaildb.set_esp_status(email_lc, emailcfg.BRAND_ID,
                           report.get("esp"), report.get("ok"), report.get("error"))
    logger.info(f"single-optin {'resync' if already_confirmed else 'confirmed'} "
                f"{email} -> {report}")

    status_str = "resynced" if already_confirmed else "confirmed"
    return 200, {"ok": True, "status": status_str, "esp": report}


async def confirm(token: str) -> tuple[int, dict]:
    rec = emaildb.get_by_token(token, "confirm")
    if not rec:
        return 404, {"ok": False, "error": "invalid_token"}
    if rec["status"] != "confirmed":
        emaildb.mark(rec["email_lc"], rec["brand"], "confirmed")
        rec["status"] = "confirmed"
        report = await esp.push_contact(rec)
        emaildb.set_esp_status(rec["email_lc"], rec["brand"],
                               report.get("esp"), report.get("ok"), report.get("error"))
        logger.info(f"confirmed {rec['email']} → {report}")
    reward = _reward_for(rec.get("wrapper") or emailcfg.WRAPPER)
    await _send_welcome(rec, reward)
    return 200, {"ok": True, "brand": rec["brand"], "wrapper": rec.get("wrapper"),
                 "reward": reward, "site": emailcfg.SITE_BASE}


async def unsubscribe(token: str) -> tuple[int, dict]:
    rec = emaildb.get_by_token(token, "unsub")
    if not rec:
        return 404, {"ok": False, "error": "invalid_token"}
    emaildb.mark(rec["email_lc"], rec["brand"], "unsubscribed")
    return 200, {"ok": True, "status": "unsubscribed"}


async def erase(email: str, brand: str = None, ip: str = "") -> tuple[int, dict]:
    brand = brand or emailcfg.BRAND_ID
    emaildb.erase((email or "").strip().lower(), brand, ip)
    return 200, {"ok": True, "status": "erased"}
