"""
emailcfg.py — configuration for the email-capture layer.

Kept separate from the large brand.py so it stays low-coupling: it reads BRAND
for display name + active verticals, and env for everything deploy-specific.
"""
import os
from brand import BRAND

BRAND_ID     = BRAND.id
BRAND_NAME   = BRAND.display_name

# Public base URL of THIS api (used to build confirm/unsubscribe links in emails).
# e.g. https://cherry-rush-backend.up.railway.app
PUBLIC_API_BASE = os.environ.get("PUBLIC_API_BASE", "").rstrip("/")

# Where users land after confirming / unsubscribing (your Lovable site).
SITE_BASE = os.environ.get("SITE_BASE", "").rstrip("/")

# Which "packaging" this deployment runs. One engine, many wrappers.
#   promo_feed | tips | bonus | wheel | vip
WRAPPER = os.environ.get("WRAPPER_TYPE", "promo_feed").strip().lower()

# Consent copy is VERSIONED: we store the exact text + version a user agreed to,
# so consent is provable. Bump CONSENT_VERSION whenever the wording changes.
CONSENT_VERSION = os.environ.get("CONSENT_VERSION", "2026-06-v1")

CONSENT_TEXT = {
    "en": (f"I am 18+ and agree to receive promotional emails from {BRAND_NAME}. "
           "I can unsubscribe at any time. See the Privacy Policy."),
    "ru": (f"Мне есть 18 лет, и я согласен получать рекламные письма от {BRAND_NAME}. "
           "Могу отписаться в любой момент. См. Политику конфиденциальности."),
    "es": (f"Soy mayor de 18 años y acepto recibir correos promocionales de {BRAND_NAME}. "
           "Puedo darme de baja en cualquier momento. Ver la Política de Privacidad."),
}

# Verticals that make a contact a "hard" (gambling) segment → route OFF Mailchimp.
HARD_VERTICALS = {v.strip() for v in
                  os.environ.get("EMAIL_HARD_VERTICALS", "casino,sports,betting").split(",") if v.strip()}

def segment_for(verticals) -> str:
    """'hard' if any gambling vertical is selected, else 'soft'."""
    return "hard" if (set(verticals or []) & HARD_VERTICALS) else "soft"

# ── ESP routing ─────────────────────────────────────────────────────────────
# soft segment -> Mailchimp (only safe for non-gambling content)
# hard segment -> an iGaming-tolerant ESP (configure ESP_HARD_*). Never Mailchimp.
ESP_SOFT = os.environ.get("ESP_SOFT", "mailchimp").strip().lower()   # mailchimp | noop
ESP_HARD = os.environ.get("ESP_HARD", "noop").strip().lower()        # set when iGaming ESP chosen

MAILCHIMP_API_KEY = os.environ.get("MAILCHIMP_API_KEY", "").strip()
MAILCHIMP_DC      = os.environ.get("MAILCHIMP_DC", "").strip()  # e.g. "us21"; else derived from key
MAILCHIMP_LIST_ID = os.environ.get("MAILCHIMP_LIST_ID", "").strip()

# ── reward per wrapper (what the user gets right after double-opt-in) ────────
# Values are env-overridable so each test variant is configured per deploy.
REWARD = {
    "code":      os.environ.get("REWARD_CODE", "").strip(),        # bonus/promo code to reveal
    "wheel_url": os.environ.get("REWARD_WHEEL_URL", "").strip(),   # link to the spin-the-wheel page
    "promo_url": os.environ.get("REWARD_PROMO_URL", "").strip(),   # link to the promo / offer page
    # Лид-магнит бота: инвайт в ЗАКРЫТЫЙ канал. Это t.me/+<hash> приглашение,
    # а НЕ публичный @handle — там внутри живут бренды (вне модерации Telegram Ads).
    "channel_url": os.environ.get("REWARD_CHANNEL_URL", "").strip(),
}

# ── Вертикаль, под которой бот собирает email ────────────────────────────────
# Должна быть «мягкой» (crypto/esports/football), иначе esp.py уведёт контакт
# с Mailchimp на iGaming-ESP. По умолчанию football → роутинг на Mailchimp.
# Список через запятую, напр. "football,crypto".
BOT_VERTICALS = [v.strip() for v in
                 os.environ.get("BOT_VERTICALS", "football").split(",") if v.strip()]
