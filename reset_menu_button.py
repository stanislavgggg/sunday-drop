#!/usr/bin/env python3
"""
reset_menu_button.py — разовый сброс залипшей кнопки-меню (Menu Button).

ЗАЧЕМ
=====
Menu Button у бота хранится на стороне Telegram ГЛОБАЛЬНО и переживает любой
редеплой кода. Старый деплой когда-то выставил MenuButtonWebApp
(«🍒 Получать на почту — бесплатно» → мини-апп). В текущем коде её уже никто
не ставит (воронка собирает email внутри бота через inline-кнопку), но кнопка
осталась висеть. Удалять в коде нечего — её надо АКТИВНО перезаписать.

Этот скрипт затирает её на MenuButtonCommands (обычная кнопка «Меню» со
списком команд). bot.py теперь делает то же самое на каждом старте (post_init),
так что после редеплоя руками гонять скрипт уже не нужно — он для того, чтобы
поправить ЖИВОГО бота прямо сейчас, не дожидаясь деплоя.

Зависимостей нет — только стандартная библиотека и токен из окружения.

ЗАПУСК
======
    BOT_TOKEN=123:ABC python reset_menu_button.py
    # или, если BOT_TOKEN уже в окружении (Railway shell):
    python reset_menu_button.py

Сбросить ещё и персональный override конкретного чата (если он почему-то есть):
    python reset_menu_button.py --chat-id 123456789

Проверить текущее значение, ничего не меняя:
    python reset_menu_button.py --check
"""
import argparse
import json
import os
import sys
import urllib.request

API = "https://api.telegram.org/bot{token}/{method}"


def _call(token: str, method: str, payload: dict) -> dict:
    url = API.format(token=token, method=method)
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def main() -> int:
    ap = argparse.ArgumentParser(description="Reset Telegram bot Menu Button.")
    ap.add_argument("--chat-id", type=int, default=None,
                    help="сбросить персональный override конкретного чата (опц.)")
    ap.add_argument("--check", action="store_true",
                    help="только показать текущую кнопку, не менять")
    args = ap.parse_args()

    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        print("ERROR: переменная окружения BOT_TOKEN не задана.", file=sys.stderr)
        print("Запусти так:  BOT_TOKEN=123:ABC python reset_menu_button.py", file=sys.stderr)
        return 2

    get_payload: dict = {}
    if args.chat_id is not None:
        get_payload["chat_id"] = args.chat_id

    before = _call(token, "getChatMenuButton", get_payload)
    btn = before.get("result", {})
    print(f"BEFORE: {json.dumps(btn, ensure_ascii=False)}")

    if args.check:
        kind = btn.get("type")
        if kind == "web_app":
            print("→ Сейчас стоит WEB_APP — это и есть залипшая кнопка мини-аппа.")
        else:
            print(f"→ Текущий тип: {kind or 'default'} (web_app не обнаружен).")
        return 0

    set_payload: dict = {"menu_button": {"type": "commands"}}
    if args.chat_id is not None:
        set_payload["chat_id"] = args.chat_id

    res = _call(token, "setChatMenuButton", set_payload)
    if not res.get("ok"):
        print(f"ERROR: setChatMenuButton не прошёл: {res}", file=sys.stderr)
        return 1

    after = _call(token, "getChatMenuButton", get_payload)
    print(f"AFTER : {json.dumps(after.get('result', {}), ensure_ascii=False)}")
    scope = f"chat_id={args.chat_id}" if args.chat_id is not None else "ГЛОБАЛЬНО (все приватные чаты)"
    print(f"✅ Menu Button сброшена на 'commands' ({scope}).")
    print("   Если у отдельного юзера кнопка осталась — Telegram-клиент кэширует "
          "её до перезахода в чат; перезапуск приложения/повторный вход в диалог обновит.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
