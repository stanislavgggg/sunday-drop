"""
resync_esp.py — добирает в ESP все confirmed-контакты, которые туда ещё не доехали.

Берёт записи со status='confirmed' и esp_ok IS NOT TRUE (включая старые, где
esp_ok = NULL, и те, у кого прошлый пуш упал), повторно пушит и сохраняет результат.
Идемпотентно: успешные ре-пуши проставят esp_ok=TRUE и в следующий раз пропустятся.

Запуск разово:           python resync_esp.py
Или Railway cron job:    python resync_esp.py   (например, каждые 15 минут)
"""
import os
import asyncio
import logging

import emailcfg
import emaildb
import esp

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("resync_esp")

# Пауза между пушами, чтобы не упереться в rate-limit Mailchimp.
SLEEP = float(os.environ.get("ESP_RESYNC_SLEEP", "0.3"))
# Опционально ограничить одним брендом; по умолчанию — текущий BRAND_ID.
BRAND = os.environ.get("ESP_RESYNC_BRAND", emailcfg.BRAND_ID).strip() or None


async def main():
    rows = emaildb.pending_esp_sync(BRAND)
    logger.info(f"pending esp sync: {len(rows)} contact(s) for brand={BRAND}")
    ok = fail = 0
    for rec in rows:
        report = await esp.push_contact(rec)
        emaildb.set_esp_status(rec["email_lc"], rec["brand"],
                               report.get("esp"), report.get("ok"), report.get("error"))
        if report.get("ok"):
            ok += 1
            logger.info(f"  ✓ {rec['email']} -> {report['esp']}")
        else:
            fail += 1
            logger.warning(f"  ✗ {rec['email']} -> {report.get('esp')} "
                           f"err={report.get('error')}")
        await asyncio.sleep(SLEEP)
    logger.info(f"done: ok={ok} fail={fail}")


if __name__ == "__main__":
    asyncio.run(main())
