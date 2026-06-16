"""
copy_brief.py — копирайт бренда Brief (спокойный премиальный daily brief + live score, режим КАНАЛ)
====================================================================================================
Цель воронки: ПОДПИСКА на Telegram-канал. Не продукт, не ставки.
Персона: «Otis» — сова-аналитик 🦉, ночная смена. Тон спокойный, точный, editorial, сухой юмор.

⚠️ TELEGRAM ADS COMPLIANCE (строго):
- только новости/цифры/счёт; никаких фин/беттинг-советов;
- не зовём покупать/продавать/ставить/депозитить;
- НИКОГДА не обещаем прибыль/доход/выигрыш.

Языки: en (дефолт), ru, es. {url} в CTA_REGISTER = ссылка на канал.
"""
from config import CHANNEL_HANDLE

_RAW_HANDLE = CHANNEL_HANDLE or "@your_channel"
CH = _RAW_HANDLE.replace("_", "\\_")

HOOK_CAPTION = {
    "en": (
        "🦉 *Brief — your daily money & scores brief*\n\n"
        "I'm Otis. I read everything so you don't have to, then distil it: clear headlines, the "
        "numbers behind them, and live scores. No noise.\n\n"
        "• 🗞 the day's signal across crypto, casino, esports & football\n"
        "• 📊 the numbers that actually matter\n"
        "• 🔴 live scores in real time\n\n"
        "Reporting only — no advice, no promises.\n\nWhich topics should I prioritise?"
    ),
    "ru": (
        "🦉 *Brief — твой дневной брифинг по деньгам и счёту*\n\n"
        "Я Otis. Читаю всё, чтобы тебе не пришлось, и отжимаю до сути: чёткие заголовки, цифры "
        "за ними и live-счёт. Без шума.\n\n"
        "• 🗞 сигнал дня по крипте, казино, киберспорту и футболу\n"
        "• 📊 цифры, которые реально важны\n"
        "• 🔴 счёт в реальном времени\n\n"
        "Только репортаж — без советов и обещаний.\n\nКакие темы ставить в приоритет?"
    ),
    "es": (
        "🦉 *Brief — tu resumen diario de dinero y resultados*\n\n"
        "Soy Otis. Leo todo para que vos no tengas que hacerlo, y lo destilo: titulares claros, "
        "los números detrás y resultados en vivo. Sin ruido.\n\n"
        "• 🗞 la señal del día en cripto, casino, esports y fútbol\n"
        "• 📊 los números que de verdad importan\n"
        "• 🔴 resultados en vivo en tiempo real\n\n"
        "Solo reporte — sin consejos ni promesas.\n\n¿Qué temas priorizo?"
    ),
}

WARMUP_FOOTBALL = {
    "en": ["🦉 The story that matters usually lands here before the noise.",
           "🔴 Live scores update in real time, no refresh needed.",
           "📊 Crypto, casino, esports, football — distilled, not dumped."],
    "ru": ["🦉 Важное обычно появляется здесь раньше шума.",
           "🔴 Live-счёт обновляется в реальном времени, без перезагрузки.",
           "📊 Крипта, казино, киберспорт, футбол — отжато, а не свалено."],
    "es": ["🦉 Lo que importa suele llegar acá antes que el ruido.",
           "🔴 Los resultados en vivo se actualizan en tiempo real.",
           "📊 Cripto, casino, esports, fútbol — destilado, no volcado."],
}
WARMUP_ESPORTS = WARMUP_FOOTBALL

BRIDGE = {
    "en": (
        "🔑 *Where the full brief lives*\n\n"
        f"The complete brief — early alerts and live-score pushes — runs in the {CH} channel.\n\n"
        "• 🗞 every story the moment it matters\n"
        "• 📊 the numbers in full\n"
        "• 🔴 live-score pings for matches you follow\n\n"
        "It's free, and it's reporting — not advice. Want the link?"
    ),
    "ru": (
        "🔑 *Где живёт полный брифинг*\n\n"
        f"Полный брифинг — ранние алерты и пуши со счётом — идёт в канале {CH}.\n\n"
        "• 🗞 каждая история в момент, когда она важна\n"
        "• 📊 цифры целиком\n"
        "• 🔴 пинги со счётом по матчам, за которыми следишь\n\n"
        "Бесплатно, и это репортаж — не советы. Скинуть ссылку?"
    ),
    "es": (
        "🔑 *Dónde vive el resumen completo*\n\n"
        f"El resumen completo — alertas tempranas y avisos de resultados — corre en el canal {CH}.\n\n"
        "• 🗞 cada historia cuando importa\n"
        "• 📊 los números completos\n"
        "• 🔴 avisos de resultados de los partidos que seguís\n\n"
        "Es gratis, y es reporte — no consejos. ¿Te paso el link?"
    ),
}

CTA_REGISTER = {
    "en": (
        "👇 *Subscribe to the channel — free*\n\n{url}\n\n"
        "Turn on notifications for the early alerts and live scores. Reporting only — no advice, "
        "no promises. 🦉"
    ),
    "ru": (
        "👇 *Подписывайся на канал — бесплатно*\n\n{url}\n\n"
        "Включи уведомления — ранние алерты и счёт. Только репортаж — без советов и обещаний. 🦉"
    ),
    "es": (
        "👇 *Suscribite al canal — gratis*\n\n{url}\n\n"
        "Activá notificaciones para las alertas tempranas y resultados. Solo reporte — sin "
        "consejos ni promesas. 🦉"
    ),
}

FTD_CELEBRATION = {
    "en": "🦉 *You're in*\n\nNotifications on so you don't miss an early alert or a live-score push.",
    "ru": "🦉 *Ты в деле*\n\nУведомления включены — не пропустишь ранний алерт и пуш со счётом.",
    "es": "🦉 *Estás adentro*\n\nNotificaciones activadas para no perderte una alerta ni un resultado.",
}

REPEAT_PUSH = {
    "en": ["🗞 Today's brief is live in the channel.",
           "🔴 Live scores are rolling — check the channel.",
           "📊 Notifications off? That's how the signal slips by."],
    "ru": ["🗞 Сегодняшний брифинг уже в канале.",
           "🔴 Live-счёт идёт — загляни в канал.",
           "📊 Уведомления выключены? Так и пропускается сигнал."],
    "es": ["🗞 El resumen de hoy está en el canal.",
           "🔴 Los resultados en vivo están corriendo — mirá el canal.",
           "📊 ¿Notificaciones apagadas? Así se escapa la señal."],
}

BARRIER_FALLBACK = {
    "en": {
        "no_trust": "Fair. Open the channel and read a couple of briefs first — no signup, judge it yourself.",
        "not_urgent": "No rush. The channel's free and early alerts are time-sensitive — that's the only catch.",
        "thinking": "Take your time. Which topics matter most to you — crypto, casino, esports or football?",
    },
    "ru": {
        "no_trust": "Справедливо. Открой канал и прочитай пару брифингов — без регистрации, оцени сам.",
        "not_urgent": "Без спешки. Канал бесплатный, а ранние алерты привязаны ко времени — единственный нюанс.",
        "thinking": "Подумай спокойно. Какие темы тебе важнее — крипта, казино, киберспорт или футбол?",
    },
    "es": {
        "no_trust": "Válido. Abrí el canal y leé un par de resúmenes — sin registro, juzgalo vos mismo.",
        "not_urgent": "Sin apuro. El canal es gratis y las alertas dependen del tiempo — ese es el único detalle.",
        "thinking": "Tomate tu tiempo. ¿Qué temas te importan más — cripto, casino, esports o fútbol?",
    },
}

GENERIC_FALLBACK = {
    "en": "🦉 Distilling the latest — one moment.",
    "ru": "🦉 Отжимаю свежее до сути — момент.",
    "es": "🦉 Destilando lo último — un momento.",
}

FTD_CONFIRM_PROMPT = {
    "en": "Subscribed? Say yes and I'll point you to today's brief.",
    "ru": "Подписался? Скажи «да» — и подскажу сегодняшний брифинг.",
    "es": "¿Te suscribiste? Decí sí y te marco el resumen de hoy.",
}

MORNING_DIGEST_HEADER = {
    "en": "📅 *Good morning — today's fixtures*\n\n",
    "ru": "📅 *Доброе утро — матчи на сегодня*\n\n",
    "es": "📅 *Buen día — los partidos de hoy*\n\n",
}
MORNING_DIGEST_FOOTER = {
    "en": f"\n\n🦉 Live-score pushes + full brief — in the channel {CH}.",
    "ru": f"\n\n🦉 Пуши со счётом + полный брифинг — в канале {CH}.",
    "es": f"\n\n🦉 Avisos de resultados + resumen completo — en el canal {CH}.",
}

JOIN_PROMPT = {
    "en": "🦉 *Subscribe to the channel*\n\nThe full brief, early alerts and live-score pushes — free. Tap subscribe, then come back and check access. 👇",
    "ru": "🦉 *Подписывайся на канал*\n\nПолный брифинг, ранние алерты и пуши со счётом — бесплатно. Нажми «Подписаться», затем вернись и проверь доступ. 👇",
    "es": "🦉 *Suscribite al canal*\n\nEl resumen completo, alertas tempranas y avisos de resultados — gratis. Tocá suscribirte, después volvé y verificá el acceso. 👇",
}
JOIN_CHECK_BTN = {"en": "✅ I subscribed", "ru": "✅ Я подписался", "es": "✅ Ya me suscribí"}
JOIN_OK = {
    "en": "✅ Done — access unlocked. The full brief is live in the channel.",
    "ru": "✅ Готово — доступ открыт. Полный брифинг уже в канале.",
    "es": "✅ Listo — acceso desbloqueado. El resumen completo está en el canal.",
}
JOIN_NOT_YET = {
    "en": "🔒 Don't see your subscription yet. Join the channel and tap “I subscribed” again.",
    "ru": "🔒 Пока не вижу подписки. Подпишись на канал и нажми «Я подписался» ещё раз.",
    "es": "🔒 Todavía no veo tu suscripción. Unite al canal y tocá «Ya me suscribí» de nuevo.",
}

NEWS_HEADER = {
    "en": "🗞 *Today's brief*\n\n",
    "ru": "🗞 *Сегодняшний брифинг*\n\n",
    "es": "🗞 *El resumen de hoy*\n\n",
}
NEWS_EMPTY = {
    "en": "🦉 The brief is compiling — try again in a moment.",
    "ru": "🦉 Брифинг собирается — попробуй ещё раз через минуту.",
    "es": "🦉 El resumen se está compilando — probá de nuevo en un momento.",
}
NEWS_FOOTER = {
    "en": f"\n\n🦉 *This is the preview.* The full brief + early alerts run in the channel {CH}.",
    "ru": f"\n\n🦉 *Это превью.* Полный брифинг + ранние алерты идут в канале {CH}.",
    "es": f"\n\n🦉 *Esto es la vista previa.* El resumen completo + alertas tempranas corren en el canal {CH}.",
}
NEWS_CAT_LABELS = {
    "en": {"all": "🌐 All", "crypto": "₿ Crypto", "casino": "🎰 Casino", "esports": "🎮 Esports"},
    "ru": {"all": "🌐 Все", "crypto": "₿ Крипто", "casino": "🎰 Казино", "esports": "🎮 Киберспорт"},
    "es": {"all": "🌐 Todo", "crypto": "₿ Cripto", "casino": "🎰 Casino", "esports": "🎮 Esports"},
}
LIVE_CHANNEL_LINE = {
    "en": f"\n\n🦉 _Live-score pushes for these — in the channel {CH}._",
    "ru": f"\n\n🦉 _Пуши со счётом по этим матчам — в канале {CH}._",
    "es": f"\n\n🦉 _Avisos de resultados de estos — en el canal {CH}._",
}
