# SUNDAY DROP — деплой (email-в-чате → инвайт в закрытый канал)

Воронка без мини-аппа на входе. Поверхность бота — «мягкая» (спорт/инсайды/
закрытое комьюнити), модерацию Telegram Ads проходит. Бренды живут ВНУТРИ
закрытого канала.

## Флоу

```
TG Ads (soft-креатив, deep-link ?start=<src>)
  → /start   картинка + хук + ОДНА кнопка [🎟 Получить инвайт]   (callback)
  → тап      просим email прямо в чате (согласие 18+ свёрнуто в тап)
  → email    capture.subscribe(vertical=football → soft) → Mailchimp сразу
  → выдаём   ссылку на закрытый канал кнопкой, в чате, мгновенно

  ⤷ догон: тапнул, но email не прислал → через ABANDON_NUDGE_MIN мин один пинок
```

Лид всегда сохраняется в Postgres (источник правды) с `source=bot_chat:<src>`,
`tg_id`, согласием (текст+версия+ip). Сбой Mailchimp не блокирует пользователя —
`resync_esp.py` добирает неудачные пуши.

## Изменённые/новые файлы

| Файл | Что |
|---|---|
| `bot.py` | вход: хук + callback-CTA, ConversationHandler, deep-link `?start=<src>` |
| `email_flow.py` | сбор email в чате → выдача канала, события `cta_tap`/lead |
| `conversation.py` | callback-кнопка (не web_app), нудж, вторичный web_app-путь |
| `email_copy.py` | **новый** — все тексты воронки (en/ru/es), модерация-safe |
| `emailcfg.py` | `REWARD_CHANNEL_URL`, `BOT_VERTICALS` (soft → Mailchimp) |

## Env (Railway)

| Переменная | Значение |
|---|---|
| `BOT_TOKEN`, `ANTHROPIC_API_KEY` | как раньше |
| `BRAND_ID` | твой бренд (по умолчанию `cherry`) |
| `REWARD_CHANNEL_URL` | инвайт закрытого канала `https://t.me/+xxxx` (НЕ `@handle`; без аппрува заявок) |
| `BOT_VERTICALS` | `football` (держит роутинг на Mailchimp; НЕ ставить casino/sports/betting) |
| `ESP_SOFT` | `mailchimp` |
| `MAILCHIMP_API_KEY` | полный ключ С суффиксом `-usXX` (иначе задай `MAILCHIMP_DC`) |
| `MAILCHIMP_LIST_ID` | `d241024d22` |
| `DATABASE_URL` | Postgres-плагин (обязательно — FS Railway эфемерна) |
| `PUBLIC_API_BASE`, `SITE_BASE` | для confirm/unsub-ссылок (api.py) |
| `ADMIN_IDS` | твой tg id — для `/funnel` |
| `ABANDON_NUDGE_MIN` | через сколько минут пнуть тех, кто тапнул, но не дал email (по умолч. `12`; `0` = выкл) |
| `MINI_APP_URL` | можно убрать — на входе не нужен |

## Замер (CRO)

`/funnel` (для ADMIN_IDS) показывает `cta_view → cta_tap → join_confirmed` и
конверсии tap/view, lead/tap, lead/view. Креатив виден в `source` контакта →
FTD-по-источнику считается в Voonix/BigQuery.

Догон считается отдельно: `abandon_nudge` (сколько пнули) и `lead_after_nudge`
(сколько из них доконвертились) — это ROI рычага. Догон in-memory: при рестарте
процесса незавершённые таймеры теряются (для 12-мин окна некритично).

## Запуск

`railway.toml` уже гонит `python api.py &` + `python bot.py`. Деплой как обычно.
Бот НЕ обязан быть админом канала (он просто шлёт инвайт-ссылку).
