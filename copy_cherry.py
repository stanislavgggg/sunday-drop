"""
copy_cherry.py — Cherry Rush (email capture)
============================================
Цель воронки: открыть мини-апп → оставить email.
Персона: Ruby + команда вишен 🍒.

CRO-принципы:
  - Hook = 1 сильная строка + 3 буллета ценности + 1 CTA
  - Никакого онбординга в боте — топики выбираются в мини-аппе
  - Inline-кнопка сразу под сообщением (не ReplyKeyboard внизу)

⚠️ COMPLIANCE: 18+, только информация, не беттинг/финансовый совет.
"""

# /start — первый экран. Коротко, ясно, одна кнопка.
HOOK_CAPTION = {
    "en": (
        "🍒 *Catch the drop before the crowd*\n\n"
        "Pick what you follow — we deliver the freshest headlines, "
        "live scores and members-only promos straight to your inbox.\n\n"
        "✨ Crypto moves & odds shifts — early\n"
        "🎮 Live match and tournament alerts\n"
        "🎁 Exclusive promos you won't find on site\n\n"
        "Takes 10 seconds to set up. 👇"
    ),
    "ru": (
        "🍒 *Лови дроп раньше толпы*\n\n"
        "Выбери темы — отправим самые свежие заголовки, "
        "live-счёт и эксклюзивные промо прямо на почту.\n\n"
        "✨ Движения крипты и коэффициентов — заранее\n"
        "🎮 Алерты по live-матчам и турнирам\n"
        "🎁 Промо только для подписчиков, не для всех\n\n"
        "Настроить за 10 секунд. 👇"
    ),
    "es": (
        "🍒 *Agarrá el drop antes que el resto*\n\n"
        "Elegí lo que seguís — te mandamos los titulares más frescos, "
        "resultados en vivo y promos exclusivos directo a tu email.\n\n"
        "✨ Movimientos de cripto y cuotas — antes que nadie\n"
        "🎮 Alertas de partidos en vivo y torneos\n"
        "🎁 Promos exclusivos que no están en el sitio\n\n"
        "Lo configurás en 10 segundos. 👇"
    ),
}

# Кнопка открытия мини-аппа
OPEN_APP_BTN = {
    "en": "🍒 Get the email feed — free",
    "ru": "🍒 Получать на почту — бесплатно",
    "es": "🍒 Recibir por email — gratis",
}

# После того как пользователь написал что-то (не открыл апп сразу)
NUDGE = {
    "en": (
        "👆 Tap the button above — pick your topics and drop your email.\n"
        "No noise, no advice, unsubscribe anytime."
    ),
    "ru": (
        "👆 Нажми кнопку выше — выбери темы и укажи email.\n"
        "Без спама, без советов, отписка в один клик."
    ),
    "es": (
        "👆 Tocá el botón de arriba — elegí temas y dejá tu email.\n"
        "Sin spam, sin consejos, te das de baja cuando quieras."
    ),
}

# Пользователь уже подписан
ALREADY_SUBSCRIBED = {
    "en": "✅ You're already in! Check your inbox — the latest drops are there.",
    "ru": "✅ Ты уже подписан! Проверь почту — последние дропы уже там.",
    "es": "✅ ¡Ya estás suscripto! Revisá tu inbox — los últimos drops ya están ahí.",
}

# Повторный push если пользователь не нажал кнопку (можно слать через scheduler)
REPEAT_PUSH = {
    "en": [
        "🍒 Crypto is moving. Are you catching it?\n\nTap to set up your email feed — free. 👇",
        "⚡ You're one tap away from never missing a drop again. 👇",
    ],
    "ru": [
        "🍒 Крипта движется. Ты в курсе?\n\nНажми и настрой ленту на почту — бесплатно. 👇",
        "⚡ Один тап — и больше ни одного пропущенного дропа. 👇",
    ],
    "es": [
        "🍒 La cripto se mueve. ¿Lo estás viendo?\n\nConfigurá tu feed por email — gratis. 👇",
        "⚡ Un tap y no te perdés más ningún drop. 👇",
    ],
}

# ── Стабы для совместимости с messages.py (он реэкспортит всё из этого файла) ─

BRIDGE = HOOK_CAPTION  # не используется в новом флоу, но импорт не сломается

CTA_REGISTER = {
    "en": "👇 Open the app, pick topics, drop your email. Free. 🍒",
    "ru": "👇 Открой приложение, выбери темы, укажи email. Бесплатно. 🍒",
    "es": "👇 Abrí la app, elegí temas, dejá tu email. Gratis. 🍒",
}

FTD_CELEBRATION = ALREADY_SUBSCRIBED

WARMUP_FOOTBALL = {
    "en": ["🍒 The freshest drops land in your inbox first."],
    "ru": ["🍒 Самые свежие дропы — первыми в твоей почте."],
    "es": ["🍒 Las novedades más frescas llegan primero a tu inbox."],
}
WARMUP_ESPORTS = WARMUP_FOOTBALL

BARRIER_FALLBACK = {
    "en": {
        "no_trust": "Fair. Open the app and browse the topics first — no email needed to look.",
        "not_urgent": "No rush. The drops are time-sensitive — but subscribing takes 10 seconds whenever you're ready.",
        "thinking": "Which topics are you most into — crypto, markets, esports or football?",
    },
    "ru": {
        "no_trust": "Справедливо. Открой приложение и посмотри темы — без email-а, просто глянь.",
        "not_urgent": "Без спешки. Дропы привязаны ко времени, но подписка займёт 10 секунд — когда будешь готов.",
        "thinking": "Какие темы ближе — крипта, рынки, киберспорт или футбол?",
    },
    "es": {
        "no_trust": "Válido. Abrí la app y mirá los temas — sin email, solo explorá.",
        "not_urgent": "Sin apuro. Los drops son tiempo-dependientes, pero suscribirse son 10 segundos.",
        "thinking": "¿Qué temas te interesan más — cripto, mercados, esports o fútbol?",
    },
}

GENERIC_FALLBACK = {
    "en": "🍒 Tap the button to subscribe — 10 seconds, free, unsubscribe anytime.",
    "ru": "🍒 Нажми кнопку — 10 секунд, бесплатно, отписка в любой момент.",
    "es": "🍒 Tocá el botón para suscribirte — 10 segundos, gratis, baja cuando quieras.",
}

FTD_CONFIRM_PROMPT = {
    "en": "Check your inbox — confirmation email is on its way.",
    "ru": "Проверь почту — письмо с подтверждением уже летит.",
    "es": "Revisá tu inbox — el correo de confirmación ya está en camino.",
}

MORNING_DIGEST_HEADER = {"en": "📅 *Today's drops*\n\n", "ru": "📅 *Дропы дня*\n\n", "es": "📅 *Drops de hoy*\n\n"}
MORNING_DIGEST_FOOTER = {"en": "\n\n🍒 Get these by email — tap below.", "ru": "\n\n🍒 Получай на почту — нажми ниже.", "es": "\n\n🍒 Recibilos por email — tocá abajo."}

JOIN_PROMPT     = HOOK_CAPTION
JOIN_CHECK_BTN  = OPEN_APP_BTN
JOIN_OK         = ALREADY_SUBSCRIBED
JOIN_NOT_YET    = {
    "en": "Didn't get the confirmation email? Check spam or tap again.",
    "ru": "Письмо не пришло? Проверь спам или нажми ещё раз.",
    "es": "¿No llegó el email? Revisá spam o intentá de nuevo.",
}

NEWS_HEADER       = {"en": "🍒 *Latest — Cherry Rush*\n\n", "ru": "🍒 *Свежее — Cherry Rush*\n\n", "es": "🍒 *Lo último — Cherry Rush*\n\n"}
NEWS_EMPTY        = {"en": "🍒 Loading — try again in a moment.", "ru": "🍒 Загружается — попробуй ещё раз.", "es": "🍒 Cargando — probá de nuevo."}
NEWS_FOOTER       = {"en": "\n\n🍒 *Get the full feed by email* — subscribe below.", "ru": "\n\n🍒 *Полный фид на почту* — подпишись ниже.", "es": "\n\n🍒 *Feed completo por email* — suscribite abajo."}
NEWS_CAT_LABELS   = {
    "en": {"all": "🌐 All", "crypto": "₿ Crypto", "casino": "🏦 Industry", "esports": "🎮 Esports"},
    "ru": {"all": "🌐 Все", "crypto": "₿ Крипто", "casino": "🏦 Индустрия", "esports": "🎮 Киберспорт"},
    "es": {"all": "🌐 Todo", "crypto": "₿ Cripto", "casino": "🏦 Industria", "esports": "🎮 Esports"},
}
LIVE_CHANNEL_LINE = {"en": "\n\n🍒 _Get email alerts for these — subscribe below._", "ru": "\n\n🍒 _Алерты по этим матчам на почту — подпишись ниже._", "es": "\n\n🍒 _Alertas de resultados por email — suscribite abajo._"}
