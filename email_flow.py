"""
email_flow.py — сбор email ПРЯМО в чате бота → мгновенный инвайт в закрытый канал.

Telegram не отдаёт email пользователя, поэтому спрашиваем явно. Фрикшн срезан
до минимума: один тап по кнопке (= согласие, текст согласия показан) → юзер
пишет email → мы пушим контакт (capture.subscribe, single-opt-in → Mailchimp для
soft-вертикали) и СРАЗУ отдаём ссылку на закрытый канал кнопкой.

Никакого мини-аппа, никакого «проверь почту перед входом» — инвайт в чате сразу.
Письмо (welcome/opt-in) при этом всё равно уходит фоном через capture/emailer.

Подключение в bot.py:
    from email_flow import build_email_conversation, deliver_channel, CTA_CB
    app.add_handler(build_email_conversation(_detect_lang))   # ДО общего text-хендлера
и кнопка на /start с callback_data=CTA_CB.
"""
import logging
import asyncio
import os
import time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (ContextTypes, ConversationHandler, CommandHandler,
                          CallbackQueryHandler, MessageHandler, filters)

import capture
import emailcfg
import email_copy as C
from storage import get_user, update_user, append_history
from config import State
import analytics

logger = logging.getLogger(__name__)

ASK_EMAIL = 1
CTA_CB = "cta_get"          # callback_data кнопки-входа на /start

# Догон бросивших тап: через сколько минут пнуть тех, кто тапнул, но не дал email.
# 0 → выключить. Без job-queue extra — на лёгком asyncio-таске (без новых зависимостей).
try:
    ABANDON_NUDGE_MIN = int(os.environ.get("ABANDON_NUDGE_MIN", "12"))
except ValueError:
    ABANDON_NUDGE_MIN = 12


# ── Догон (abandoned tap → email не прислан) ─────────────────────────────────

async def _abandon_watch(bot, uid: int, chat_id: int, lang: str, ts: float, delay: float):
    """Ждёт delay сек и шлёт ОДИН нудж, если юзер так и не сконвертился.

    In-memory (переживает только до рестарта процесса — для 12-мин окна ок).
    Идемпотентность и отсутствие спама — через сверку awaiting_ts/nudged_ts.
    """
    try:
        await asyncio.sleep(delay)
        u = get_user(uid)
        if u.get("email") or u.get("state") in (State.DEPOSITED, State.REPEAT):
            return                              # уже сконвертился
        if not u.get("awaiting_email"):
            return                              # отменил / сбросил
        if u.get("awaiting_ts") != ts:
            return                              # перетапнул — этим займётся свежий watcher
        if u.get("nudged_ts") == ts:
            return                              # уже пнули в этом цикле
        update_user(uid, nudged_ts=ts, nudged=True)
        analytics.track("abandon_nudge", uid)
        await bot.send_message(
            chat_id,
            C.ABANDON_NUDGE.get(lang, C.ABANDON_NUDGE["en"]),
            parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True,
        )
        logger.info(f"abandon-nudge sent user={uid}")
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.warning(f"abandon-nudge failed user={uid}: {e}")


def _schedule_abandon_watch(bot, uid: int, chat_id: int, lang: str, ts: float):
    if ABANDON_NUDGE_MIN <= 0:
        return
    try:
        asyncio.get_running_loop().create_task(
            _abandon_watch(bot, uid, chat_id, lang, ts, ABANDON_NUDGE_MIN * 60)
        )
    except RuntimeError:
        pass                                    # нет активного loop (вне PTB) — пропускаем


# ── Доставка ссылки на закрытый канал ────────────────────────────────────────

def channel_keyboard(lang: str) -> InlineKeyboardMarkup | None:
    url = emailcfg.REWARD.get("channel_url", "")
    if not url:
        return None
    label = C.JOIN_CHANNEL_BTN.get(lang, C.JOIN_CHANNEL_BTN["en"])
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, url=url)]])


async def deliver_channel(bot, chat_id: int, lang: str, *, already: bool = False):
    """Отдаёт инвайт в закрытый канал кнопкой. fail-soft если URL не задан."""
    kb = channel_keyboard(lang)
    if kb is None:
        await bot.send_message(chat_id, C.SUCCESS_NO_LINK.get(lang, C.SUCCESS_NO_LINK["en"]))
        logger.warning("REWARD_CHANNEL_URL not set — delivered no-link fallback")
        return
    if already:
        text = C.ALREADY_IN.get(lang, C.ALREADY_IN["en"])
    else:
        text = C.SUCCESS.get(lang, C.SUCCESS["en"])
    await bot.send_message(
        chat_id, text, parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb, disable_web_page_preview=True,
    )


# ── ConversationHandler ───────────────────────────────────────────────────────

def build_email_conversation(detect_lang):

    def _lang(update, ctx) -> str:
        u = get_user(update.effective_user.id)
        return u.get("lang") or ctx.user_data.get("lang") or detect_lang(update.effective_user.language_code)

    async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Вход в воронку: тап по кнопке или /subscribe. Сразу просим email."""
        lang = _lang(update, ctx)
        ctx.user_data["lang"] = lang
        uid = update.effective_user.id

        # Уже подписан → не гоняем по кругу, сразу отдаём канал
        if get_user(uid).get("state") in (State.DEPOSITED, State.REPEAT):
            if update.callback_query:
                await update.callback_query.answer()
            await deliver_channel(ctx.bot, update.effective_chat.id, lang, already=True)
            return ConversationHandler.END

        if update.callback_query:
            await update.callback_query.answer()

        analytics.track("cta_tap", uid)
        ts = time.time()
        update_user(uid, awaiting_email=True, awaiting_ts=ts, nudged_ts=None)
        msg = update.callback_query.message if update.callback_query else update.message
        await msg.reply_text(
            C.ASK_EMAIL.get(lang, C.ASK_EMAIL["en"]),
            parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True,
        )
        _schedule_abandon_watch(ctx.bot, uid, update.effective_chat.id, lang, ts)
        return ASK_EMAIL

    async def got_email(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        lang = _lang(update, ctx)
        uid = update.effective_user.id
        chat_id = update.effective_chat.id
        email = (update.message.text or "").strip()
        append_history(uid, "user", email)

        src = get_user(uid).get("src") or "direct"

        # Последний рубеж: что бы ни случилось внутри (БД легла, неожиданная
        # ошибка ESP, таймаут сети) — юзер НЕ должен зависнуть без ответа.
        # emaildb.py сам падает на JSON-фоллбэк при сбое Postgres, но это
        # дополнительная страховка против любого непредвиденного исключения.
        try:
            status, data = await capture.subscribe(dict(
                email=email,
                consent=True,                      # тап + текст согласия = явное согласие (логируется)
                lang=lang,
                verticals=emailcfg.BOT_VERTICALS,  # soft → Mailchimp
                source=f"bot_chat:{src}",          # атрибуция креатива для CAC/качества по источнику
                wrapper=emailcfg.WRAPPER,
                tg_id=uid,
            ), ip="")
        except Exception as e:
            # [LEAD_EMERGENCY] — грепаемый тег: лид виден в Railway-логах даже
            # если ВСЁ хранилище недоступно. Юзеру всё равно отдаём канал —
            # конверсия важнее идеальной записи, а резинк добор сделает позже.
            logger.error(f"[LEAD_EMERGENCY] capture.subscribe crashed user={uid} email={email} "
                        f"src={src}: {e}", exc_info=True)
            update_user(uid, state=State.DEPOSITED, email=email, awaiting_email=False)
            analytics.mark_join(uid)
            analytics.track("capture_exception", uid)
            append_history(uid, "assistant", "[channel invite delivered — degraded, see LEAD_EMERGENCY log]")
            await deliver_channel(ctx.bot, chat_id, lang)
            return ConversationHandler.END

        err = data.get("error")
        if err == "invalid_email":
            await update.message.reply_text(C.BAD_EMAIL.get(lang, C.BAD_EMAIL["en"]))
            return ASK_EMAIL          # остаёмся в стейте, даём переввести
        if err in ("geo_restricted",):
            # для soft-вертикали гео-гейт не срабатывает, но на всякий — мягко закрываем
            await update.message.reply_text(C.BAD_EMAIL.get(lang, C.BAD_EMAIL["en"]))
            return ConversationHandler.END
        if not data.get("ok") and err != "already_confirmed":
            logger.warning(f"subscribe failed user={uid}: {err}")
            await update.message.reply_text(C.BAD_EMAIL.get(lang, C.BAD_EMAIL["en"]))
            return ASK_EMAIL

        # Успех — фиксируем пользователя и СРАЗУ отдаём канал
        was_nudged = bool(get_user(uid).get("nudged"))
        update_user(uid, state=State.DEPOSITED, email=email, awaiting_email=False)
        analytics.mark_join(uid)   # уникальная конверсия (lead) для /funnel
        if was_nudged:
            analytics.track("lead_after_nudge", uid)   # ROI догона
        append_history(uid, "assistant", "[channel invite delivered]")
        logger.info(f"bot_chat subscribed user={uid} email={email} esp={data.get('esp')}")
        await deliver_channel(ctx.bot, chat_id, lang)
        return ConversationHandler.END

    async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        lang = _lang(update, ctx)
        update_user(update.effective_user.id, awaiting_email=False)
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(C.CANCELLED.get(lang, C.CANCELLED["en"]))
        else:
            await update.message.reply_text(C.CANCELLED.get(lang, C.CANCELLED["en"]))
        return ConversationHandler.END

    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start, pattern=f"^{CTA_CB}$"),
            CommandHandler("subscribe", start),
        ],
        states={
            ASK_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, got_email),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
        per_message=False,
    )
