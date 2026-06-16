"""
email_copy.py — тексты воронки «email-в-чате → инвайт в закрытый канал».

Отдельный модуль (не привязан к copy_<brand>.py), потому что эта механика
одинаковая для всех брендов: меняется только BRAND_ID/канал в env, а не текст.

ВАЖНО про модерацию Telegram Ads:
  Поверхность бота — то, что видит модератор, перейдя по рекламе, — должна быть
  «мягкой»: спорт/аналитика/закрытое комьюнити. Без «казино», «ставок»,
  «выигрыша», «бонуса». Сами бренды живут ВНУТРИ закрытого канала, не здесь.
  Поэтому здесь нигде нет гэмблинг-лексики, а в подвале — 18+/инфо-дисклеймер.
"""

# ── Хук на /start (картинка + этот caption + одна кнопка) ────────────────────
HOOK = {
    "en": (
        "⚡️ *The closed channel is open — for today.*\n\n"
        "Match insights, live breakdowns and drops you won't find anywhere public.\n"
        "Free to join, but invite-only.\n\n"
        "Drop your email — I'll send the invite right now 👇"
    ),
    "ru": (
        "⚡️ *Закрытый канал открыт — на сегодня.*\n\n"
        "Инсайды по матчам, лайв-разборы и дропы, которых нет в открытом доступе.\n"
        "Вход бесплатный, но по приглашению.\n\n"
        "Оставь почту — пришлю инвайт прямо сейчас 👇"
    ),
    "es": (
        "⚡️ *El canal cerrado está abierto — por hoy.*\n\n"
        "Insights de partidos, análisis en vivo y drops que no vas a encontrar en abierto.\n"
        "Entrada gratis, pero solo con invitación.\n\n"
        "Dejá tu email — te mando la invitación ahora mismo 👇"
    ),
}

# ── Кнопка-вход (callback, НЕ web_app) ───────────────────────────────────────
CTA_BTN = {
    "en": "🎟 Get my invite",
    "ru": "🎟 Получить инвайт",
    "es": "🎟 Quiero la invitación",
}

# ── Шаг запроса email (после тапа) — согласие свёрнуто в одно действие ───────
ASK_EMAIL = {
    "en": (
        "Drop your email here — I'll send the closed-channel link in one second.\n\n"
        "_By sending your email you confirm you're 18+ and agree to receive the "
        "newsletter (unsubscribe anytime)._"
    ),
    "ru": (
        "Кинь свой email сюда — за секунду пришлю ссылку на закрытый канал.\n\n"
        "_Отправляя email, ты подтверждаешь, что тебе 18+ и согласен получать "
        "рассылку (отписка в любой момент)._"
    ),
    "es": (
        "Dejá tu email acá — te mando el enlace del canal cerrado en un segundo.\n\n"
        "_Al enviar tu email confirmás que sos mayor de 18 y aceptás recibir el "
        "newsletter (podés darte de baja cuando quieras)._"
    ),
}

# ── Невалидный email ─────────────────────────────────────────────────────────
BAD_EMAIL = {
    "en": "Hmm, that doesn't look like an email. Check it and send again — or /cancel.",
    "ru": "Хм, это не похоже на email. Проверь и пришли ещё раз — или /cancel.",
    "es": "Mmm, eso no parece un email. Revisalo y enviá de nuevo — o /cancel.",
}

# ── Успех: текст + (ссылка отдаётся кнопкой) ─────────────────────────────────
SUCCESS = {
    "en": "✅ *You're in.* Here's your entry to the closed channel 👇\n\nThe good stuff drops there first.",
    "ru": "✅ *Готово.* Вот твой вход в закрытый канал 👇\n\nЛучшее падает туда первым.",
    "es": "✅ *Listo.* Acá tenés tu entrada al canal cerrado 👇\n\nLo bueno cae ahí primero.",
}

# Кнопка-ссылка на канал в сообщении успеха
JOIN_CHANNEL_BTN = {
    "en": "➡️ Open the channel",
    "ru": "➡️ Войти в канал",
    "es": "➡️ Abrir el canal",
}

# Если REWARD_CHANNEL_URL не задан в env — отдаём текст без кнопки (fail-soft)
SUCCESS_NO_LINK = {
    "en": "✅ You're in — your invite is on its way. (Channel link is being set up.)",
    "ru": "✅ Готово — инвайт уже в пути. (Ссылку на канал сейчас настраивают.)",
    "es": "✅ Listo — tu invitación está en camino. (El enlace del canal se está configurando.)",
}

# ── Уже в списке (повторный заход) ───────────────────────────────────────────
ALREADY_IN = {
    "en": "You're already on the list ✅ Here's the channel link in case you lost it 👇",
    "ru": "Ты уже в списке ✅ Вот ссылка на канал, если потерял 👇",
    "es": "Ya estás en la lista ✅ Acá tenés el enlace del canal por si lo perdiste 👇",
}

# ── Нудж: любой текст до тапа по кнопке ──────────────────────────────────────
NUDGE = {
    "en": "Tap below — I'll send your invite to the closed channel 👇",
    "ru": "Жми кнопку ниже — пришлю инвайт в закрытый канал 👇",
    "es": "Tocá el botón de abajo — te mando la invitación al canal cerrado 👇",
}

# ── Отмена ────────────────────────────────────────────────────────────────────
CANCELLED = {
    "en": "No problem. Tap below whenever you want in.",
    "ru": "Без проблем. Захочешь — жми кнопку ниже.",
    "es": "Sin problema. Cuando quieras, tocá el botón de abajo.",
}

# ── Догон: тапнул кнопку, но не прислал email ────────────────────────────────
ABANDON_NUDGE = {
    "en": (
        "You're *one step* away 👀\n"
        "Just drop your email here and your closed-channel invite lands instantly."
    ),
    "ru": (
        "Остался *один шаг* 👀\n"
        "Кинь свой email сюда — и инвайт в закрытый канал прилетит сразу."
    ),
    "es": (
        "Estás a *un paso* 👀\n"
        "Dejá tu email acá y la invitación al canal cerrado llega al instante."
    ),
}
