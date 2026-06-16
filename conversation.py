"""
conversation.py — сбор email в чате → инвайт в закрытый канал.

Воронка предельно прямая, без мини-аппа на входе:
  /start → картинка + hook + ОДНА inline-кнопка [Получить инвайт]  (callback)
  тап    → email_flow.ConversationHandler просит email → пушит в Mailchimp →
           отдаёт ссылку на закрытый канал прямо в чате.
  любой текст вне воронки → короткий nudge + та же кнопка.

Мини-апп оставлен как ВТОРИЧНАЯ поверхность: handle_web_app_data всё ещё ловит
WebApp.sendData() и теперь тоже отдаёт инвайт в канал. Но воронка его не требует.
"""
import asyncio
import json
import logging

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

from config import State
from media import sanitize_markdown
from storage import get_user, update_user, append_history
import capture
import emailcfg
import email_copy as C
from email_flow import CTA_CB, deliver_channel

logger = logging.getLogger(__name__)

# Стабы для совместимости импортов bot.py (часть фич бренда kinetic выпилена).
JOIN_CHECK_CB  = "cb_join_check"
NEWS_CB_PREFIX = "cb_news_"


# ── Клавиатуры ────────────────────────────────────────────────────────────────

def _open_btn(lang: str) -> InlineKeyboardMarkup:
    """Единственная кнопка воронки — callback-вход в сбор email (НЕ web_app)."""
    label = C.CTA_BTN.get(lang, C.CTA_BTN["en"])
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data=CTA_CB)]])


def main_menu(lang: str) -> InlineKeyboardMarkup:
    return _open_btn(lang)


# ── Отправка с «печатает…» ────────────────────────────────────────────────────

def _typing_delay(text: str) -> float:
    return round(0.6 + min(len(text) / 200, 1.5), 1)


async def _send(bot: Bot, chat_id: int, text: str, lang: str, inline=None):
    await bot.send_chat_action(chat_id, "typing")
    await asyncio.sleep(_typing_delay(text))
    await bot.send_message(
        chat_id=chat_id,
        text=sanitize_markdown(text),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=inline if inline is not None else _open_btn(lang),
        disable_web_page_preview=True,
    )


# ── Текст вне воронки ─────────────────────────────────────────────────────────

async def handle_message(bot: Bot, user_id: int, chat_id: int, text: str, lang: str):
    """Срабатывает только когда юзер НЕ внутри ConversationHandler (email_flow)."""
    u     = get_user(user_id, lang)
    state = u.get("state", State.NEW)

    update_user(user_id, message_count=u.get("message_count", 0) + 1)
    append_history(user_id, "user", text)

    # Уже подписан — отдаём канал ещё раз (вдруг потерял ссылку)
    if state in (State.DEPOSITED, State.REPEAT):
        await deliver_channel(bot, chat_id, lang, already=True)
        return

    # Иначе — короткий nudge на тап по кнопке
    nudge = C.NUDGE.get(lang, C.NUDGE["en"])
    append_history(user_id, "assistant", nudge)
    await _send(bot, chat_id, nudge, lang)


# ── web_app_data (мини-апп → sendData) — вторичный путь ───────────────────────

async def handle_web_app_data(bot: Bot, user_id: int, chat_id: int, lang: str, raw: str):
    """Если кто-то всё же пришёл через мини-апп: тот же core + инвайт в канал."""
    logger.info(f"web_app_data user={user_id} raw={raw[:120]}")
    try:
        payload = json.loads(raw)
    except Exception:
        await _send(bot, chat_id, C.BAD_EMAIL.get(lang, C.BAD_EMAIL["en"]), lang)
        return

    email = (payload.get("email") or "").strip()
    if not email or "@" not in email:
        await _send(bot, chat_id, C.BAD_EMAIL.get(lang, C.BAD_EMAIL["en"]), lang)
        return

    payload["tg_id"]  = user_id
    payload["lang"]   = payload.get("lang") or lang
    payload["source"] = "bot_miniapp"
    payload.setdefault("consent", True)
    payload.setdefault("wrapper", emailcfg.WRAPPER)
    # Если фронт не прислал вертикали — ставим soft-дефолт (роутинг на Mailchimp)
    if not payload.get("verticals"):
        payload["verticals"] = emailcfg.BOT_VERTICALS

    try:
        status, result = await capture.subscribe(payload, ip="")
    except Exception as e:
        logger.error(f"capture.subscribe error user={user_id}: {e}", exc_info=True)
        await _send(bot, chat_id, C.BAD_EMAIL.get(lang, C.BAD_EMAIL["en"]), lang)
        return

    if not result.get("ok") and result.get("error") != "already_confirmed":
        await _send(bot, chat_id, C.BAD_EMAIL.get(lang, C.BAD_EMAIL["en"]), lang)
        return

    update_user(user_id, state=State.DEPOSITED, email=email)
    logger.info(f"miniapp subscribed user={user_id} email={email}")
    await deliver_channel(bot, chat_id, lang)


# ── Стабы (импортируются bot.py, фичи бренда kinetic не используются) ─────────

async def handle_menu_action(bot, user_id, chat_id, lang, action):
    await _send(bot, chat_id, C.NUDGE.get(lang, C.NUDGE["en"]), lang)

async def send_channel_join(bot, chat_id, lang):
    await _send(bot, chat_id, C.NUDGE.get(lang, C.NUDGE["en"]), lang)

async def handle_join_check(bot, user_id, chat_id, lang):
    await _send(bot, chat_id, C.NUDGE.get(lang, C.NUDGE["en"]), lang)
    return False

async def handle_news(bot, user_id, chat_id, lang, category=None):
    await _send(bot, chat_id, C.NUDGE.get(lang, C.NUDGE["en"]), lang)

async def handle_news_callback(bot, user_id, chat_id, lang, data):
    await _send(bot, chat_id, C.NUDGE.get(lang, C.NUDGE["en"]), lang)
