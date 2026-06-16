"""
bot.py — email-в-чате → инвайт в закрытый канал (CRO, без мини-аппа на входе)

Команды: /start /subscribe /policy /lang /funnel
Флоу:
  /start      → картинка + hook (4 строки) + ОДНА inline-кнопка [Получить инвайт]
  тап кнопки  → ConversationHandler (email_flow): просит email → Mailchimp →
                сразу отдаёт ссылку на закрытый канал
  любой текст → nudge + та же кнопка (вне воронки)
"""
import atexit
import logging
import os
import sys

from telegram import Update, ReplyKeyboardRemove
from telegram.error import Conflict, NetworkError
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler, filters,
)
from telegram.constants import ParseMode

from brand import BRAND
from config import BOT_TOKEN, BOT_USERNAME, DEFAULT_LANG, HOOK_IMAGE, State, TG_LANG_MAP
from conversation import handle_message, handle_web_app_data, _open_btn
from email_flow import build_email_conversation
from media import send_pic
import email_copy as C
from storage import append_history, get_user, update_user
import analytics


# ── Фильтр web_app_data (мини-апп sendData) ──────────────────────────────────
class _WebAppDataFilter(filters.MessageFilter):
    def filter(self, message) -> bool:
        return message.web_app_data is not None

_WEB_APP_DATA_FILTER = _WebAppDataFilter()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

LOCK_FILE = "/tmp/email_drop_bot.lock"


def _check_lock():
    import signal
    MY_FINGERPRINT = "bot.py"
    if os.path.exists(LOCK_FILE):
        try:
            raw = open(LOCK_FILE).read().strip().split(":", 1)
            pid = int(raw[0]); stored_fp = raw[1] if len(raw) > 1 else ""
            os.kill(pid, 0)
            try:
                cmdline = open(f"/proc/{pid}/cmdline").read().replace("\x00", " ")
                is_bot = MY_FINGERPRINT in cmdline
            except Exception:
                is_bot = (stored_fp == MY_FINGERPRINT)
            if is_bot:
                logger.critical(f"bot.py already running (PID {pid}). Exiting.")
                sys.exit(1)
            else:
                logger.warning(f"Lock PID {pid} is a different process — removing stale lock.")
                os.remove(LOCK_FILE)
        except (ProcessLookupError, ValueError, OSError):
            os.remove(LOCK_FILE)
    with open(LOCK_FILE, "w") as f:
        f.write(f"{os.getpid()}:{MY_FINGERPRINT}")

    def _cleanup(*args):
        try:
            if os.path.exists(LOCK_FILE):
                os.remove(LOCK_FILE)
        except Exception:
            pass
        sys.exit(0)

    atexit.register(_cleanup)
    signal.signal(signal.SIGTERM, _cleanup)
    signal.signal(signal.SIGINT, _cleanup)


_check_lock()


def _detect_lang(code: str | None) -> str:
    if not code:
        return DEFAULT_LANG
    return TG_LANG_MAP.get(code.split("-")[0].lower(), DEFAULT_LANG)


# ── Privacy / legal footer (помогает и модерации Telegram Ads) ───────────────

PRIVACY_URL = (BRAND.privacy_url or "").strip()
_SHOW_PRIVACY = (
    bool(PRIVACY_URL)
    and "your_channel" not in PRIVACY_URL.lower()
    and ".example." not in PRIVACY_URL.lower()
)
_LEGAL = {
    "en": "18+ · Informational only — not betting or financial advice.",
    "ru": "18+ · Только информация — не беттинг/финансовый совет.",
    "es": "18+ · Solo información — no es asesoramiento de apuestas/financiero.",
}

def _legal_footer(lang: str) -> str:
    base = _LEGAL.get(lang, _LEGAL["en"])
    if _SHOW_PRIVACY:
        lbl = {"en": "Privacy Policy", "ru": "Политика", "es": "Privacidad"}.get(lang, "Privacy Policy")
        base += f"\n[{lbl}]({PRIVACY_URL})"
    return f"\n\n———\n{base}"


# ── /start ────────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    chat_id = update.effective_chat.id

    # ── Снести залипшую reply-клавиатуру от старого кода ─────────────────────
    # Старый деплой когда-то прислал ReplyKeyboardMarkup с web_app-кнопкой
    # («🍒 Получать на почту»). Reply-клавиатура хранится в КЛИЕНТЕ per-chat и
    # переживает редеплой: новый код её не шлёт, поэтому и не заменяет, и не
    # убирает. Inline-кнопка хука её НЕ трогает — это отдельный слой UI. Снять
    # можно только ReplyKeyboardRemove: шлём временное сообщение-носитель и
    # сразу удаляем его — снятие клавиатуры сохраняется и после удаления.
    # Глобального сброса для reply-клавиатур (как у menu button) у Telegram нет:
    # у каждого юзера она исчезнет при первом /start после этого деплоя.
    try:
        _tmp = await context.bot.send_message(
            chat_id, "\u2063", reply_markup=ReplyKeyboardRemove()
        )
        await context.bot.delete_message(chat_id, _tmp.message_id)
    except Exception as e:
        logger.debug(f"reply-keyboard cleanup skipped: {e}")

    detected = _detect_lang(user.language_code)
    u_check  = get_user(user.id, detected)
    lang = u_check.get("lang", detected) if u_check.get("lang_manual") else detected

    is_new = u_check.get("message_count", 0) == 0
    # Deep-link источник из рекламы: t.me/Bot?start=<src> (TG Ads ставит метку
    # на креатив). Сохраняем first-touch, не перезатираем при повторном /start.
    src = ""
    if context.args:
        import re as _re
        src = _re.sub(r"[^A-Za-z0-9_\-:.]", "", context.args[0])[:48]
    if is_new:
        update_user(user.id, lang=lang, state=State.NEW, src=(src or "direct"))
    else:
        update_user(user.id, lang=lang)
        if src and not u_check.get("src"):
            update_user(user.id, src=src)

    analytics.track("cta_view", user.id)

    caption = C.HOOK.get(lang, C.HOOK["en"]) + _legal_footer(lang)
    kb      = _open_btn(lang)

    sent = await send_pic(context.bot, chat_id, "start", caption, lang, reply_markup=kb)
    if not sent and os.path.exists(HOOK_IMAGE):
        try:
            with open(HOOK_IMAGE, "rb") as p:
                await context.bot.send_photo(
                    chat_id=chat_id, photo=p, caption=caption,
                    parse_mode=ParseMode.MARKDOWN, reply_markup=kb,
                )
            sent = True
        except Exception as e:
            logger.warning(f"hook.png fallback failed: {e}")
    if not sent:
        await context.bot.send_message(
            chat_id=chat_id, text=caption, parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb, disable_web_page_preview=True,
        )

    append_history(user.id, "assistant", caption)
    logger.info(f"/start user={user.id} lang={lang} new={is_new}")


# ── /lang ─────────────────────────────────────────────────────────────────────

async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    arg  = (context.args[0].lower() if context.args else "")
    if arg in ("en", "ru", "es"):
        update_user(user.id, lang=arg, lang_manual=True)
        reply = {"en": "✅ Language set to English.",
                 "ru": "✅ Язык переключён на русский.",
                 "es": "✅ Idioma cambiado a español."}[arg]
        await update.message.reply_text(reply)
    else:
        cur = get_user(user.id).get("lang", _detect_lang(user.language_code))
        await update.message.reply_text(
            f"🌐 Current language: {cur.upper()}\nUsage: /lang en · /lang ru · /lang es"
        )


# ── /policy ───────────────────────────────────────────────────────────────────

async def cmd_policy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u    = get_user(update.effective_user.id)
    lang = u.get("lang", _detect_lang(update.effective_user.language_code))
    if lang == "ru":
        text = ("🔒 *Политика конфиденциальности*\n\n"
                f"{BRAND.display_name} собирает email и Telegram ID исключительно "
                "для отправки выбранной тобой рассылки.\n"
                "Платёжные данные не хранятся. Отписка — в любой момент по ссылке в письме.")
    elif lang == "es":
        text = ("🔒 *Política de Privacidad*\n\n"
                f"{BRAND.display_name} recopila tu email e ID de Telegram únicamente "
                "para enviar el newsletter que elegiste.\n"
                "No almacenamos datos de pago. Podés darte de baja en cualquier momento.")
    else:
        text = ("🔒 *Privacy Policy*\n\n"
                f"{BRAND.display_name} collects your email and Telegram ID solely "
                "to send the newsletter you signed up for.\n"
                "No payment data stored. Unsubscribe anytime via the link in any email.")
    if _SHOW_PRIVACY:
        lbl = {"ru": "Читать полностью →", "es": "Leer completo →"}.get(lang, "Read full policy →")
        text += f"\n\n[{lbl}]({PRIVACY_URL})"
    await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)


# ── web_app_data (мини-апп → sendData) — вторичный путь ───────────────────────

async def handle_web_app_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    raw_data = getattr(getattr(update.message, "web_app_data", None), "data", None)
    if not raw_data:
        return
    u    = get_user(user.id)
    lang = u.get("lang", _detect_lang(user.language_code))
    try:
        await handle_web_app_data(context.bot, user.id, update.effective_chat.id, lang, raw_data)
    except Exception as e:
        logger.error(f"web_app_data error user={user.id}: {e}", exc_info=True)


# ── Текст вне воронки ─────────────────────────────────────────────────────────

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (update.message.text or "").strip()
    if not text:
        return
    u    = get_user(user.id)
    lang = u.get("lang", _detect_lang(user.language_code))
    try:
        await handle_message(context.bot, user.id, update.effective_chat.id, text, lang)
    except Exception as e:
        logger.error(f"handle_text error user={user.id}: {e}", exc_info=True)


# ── Admin /funnel ─────────────────────────────────────────────────────────────

def _admin_ids():
    return [int(x.strip()) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()]

async def cmd_funnel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in _admin_ids():
        return
    snap = analytics.snapshot()
    f, r = snap["funnel"], snap["rates"]
    lines = ["📊 *Funnel snapshot*", ""]
    for k in ("cta_view", "cta_tap", "channel_open", "membership_check", "join_confirmed"):
        lines.append(f"{k}: {f.get(k, 0)}")
    lines += ["", f"unique joins: {snap['unique_joins']}",
              f"tap/view: {r['tap_per_view']}%", f"join/tap: {r['join_per_tap']}%",
              f"join/view: {r['join_per_view']}%"]
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── Post-init ─────────────────────────────────────────────────────────────────

async def post_init(application: Application):
    from telegram import BotCommand, MenuButtonCommands
    await application.bot.set_my_commands([
        BotCommand("start",  "Start"),
        BotCommand("policy", "Privacy policy"),
        BotCommand("lang",   "Language: en / ru / es"),
    ])

    # ── Menu Button: жёстко выправляем на КАЖДОМ старте ───────────────────────
    # Воронка собирает email ВНУТРИ бота (inline-кнопка /start → ConversationHandler),
    # а НЕ через мини-апп. Но кнопка-меню (Menu Button) хранится на стороне Telegram
    # глобально и переживает любой редеплой кода: старый деплой когда-то выставил
    # MenuButtonWebApp («🍒 Получать на почту»), и она осталась висеть, хотя в коде
    # её уже никто не ставит. Удалять нечего — её нужно АКТИВНО перезаписать.
    # MenuButtonCommands надёжно затирает застрявший WebApp-баттон (надёжнее, чем
    # MenuButtonDefault, который в части клиентов не сбрасывает WebApp). chat_id не
    # передаём → меняем глобальный дефолт для всех приватных чатов.
    try:
        await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        logger.info("Menu Button reset → MenuButtonCommands (no web_app)")
    except Exception as e:
        logger.warning(f"set_chat_menu_button failed: {e}")

    logger.info(f"{BRAND.display_name} bot ready (in-chat email → channel invite)")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("policy", cmd_policy))
    app.add_handler(CommandHandler("lang",   cmd_lang))
    app.add_handler(CommandHandler("funnel", cmd_funnel))

    # ВАЖНО: ConversationHandler — ДО общего text-хендлера, иначе ввод email
    # перехватит nudge. Entry — тап по CTA-кнопке (callback) или /subscribe.
    app.add_handler(build_email_conversation(_detect_lang))

    app.add_handler(MessageHandler(_WEB_APP_DATA_FILTER, handle_web_app_data_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    async def _error_handler(update, context):
        if isinstance(context.error, (Conflict, NetworkError)):
            logger.warning(f"Recoverable error: {context.error}")
            return
        logger.exception(context.error)

    app.add_error_handler(_error_handler)
    logger.info(f"Starting {BOT_USERNAME}...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
