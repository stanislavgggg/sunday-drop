"""
emailer.py — TRANSACTIONAL email sender (double-opt-in confirmation + reward).

Deliberately separate from the marketing ESP: opt-in/confirmation mail is
transactional and can go over plain SMTP or a transactional API even when the
marketing provider (e.g. Mailchimp) forbids the promotional content.

Prod: set SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASS / EMAIL_FROM.
Dev (no SMTP_HOST): messages are captured in OUTBOX and logged, so the flow is
fully testable without a real mail server.
"""
import os
import ssl
import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

SMTP_HOST = os.environ.get("SMTP_HOST", "").strip()
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "").strip()
SMTP_PASS = os.environ.get("SMTP_PASS", "").strip()
EMAIL_FROM = os.environ.get("EMAIL_FROM", "no-reply@example.com").strip()

# Dev capture — list of dicts {to, subject, html, text}
OUTBOX: list = []


def _smtp_send(to: str, subject: str, html: str, text: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = to
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    ctx = ssl.create_default_context()
    if SMTP_PORT == 465:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx) as s:
            if SMTP_USER:
                s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(EMAIL_FROM, [to], msg.as_string())
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls(context=ctx)
            if SMTP_USER:
                s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(EMAIL_FROM, [to], msg.as_string())


async def send(to: str, subject: str, html: str, text: str) -> bool:
    if not SMTP_HOST:
        OUTBOX.append({"to": to, "subject": subject, "html": html, "text": text})
        logger.info(f"[emailer:dev] captured mail to {to}: {subject}")
        return True
    try:
        await asyncio.to_thread(_smtp_send, to, subject, html, text)
        return True
    except Exception as e:
        logger.error(f"emailer send failed to {to}: {e}")
        return False
