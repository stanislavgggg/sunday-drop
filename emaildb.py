"""
emaildb.py — contact store for email capture.

System of record for collected emails. Postgres (via DATABASE_URL) in prod,
JSON-file fallback for local dev. Railway's filesystem is ephemeral, so emails
MUST live in Postgres in production — never rely on the JSON fallback there.

Two tables:
  email_contacts   — one row per (brand, email): status, interests, consent, tokens
  email_consent_log — append-only audit trail (GDPR proof of consent / opt-out)

Status lifecycle:  pending → confirmed → unsubscribed   (erased = row deleted)
"""
import os
import json
import time
import secrets
import logging

logger = logging.getLogger(__name__)

DATABASE_URL  = os.environ.get("DATABASE_URL", "").strip()
EMAIL_DB_PATH = os.environ.get("EMAIL_DB_PATH", "email_contacts.json")
_USE_PG = bool(DATABASE_URL)

# ── token helpers ───────────────────────────────────────────────────────────
def _token() -> str:
    return secrets.token_urlsafe(24)

def _now() -> float:
    return time.time()

def _norm_email(email: str) -> str:
    return (email or "").strip().lower()


# ── Postgres backend ────────────────────────────────────────────────────────
_pg_ready = False

def _pg():
    """Return a fresh autocommit psycopg connection (lazy import)."""
    import psycopg  # psycopg3 — add `psycopg[binary]` to requirements for prod
    conn = psycopg.connect(DATABASE_URL, autocommit=True)
    return conn

def _pg_init():
    global _pg_ready
    if _pg_ready:
        return
    with _pg() as c:
        c.execute("""
        CREATE TABLE IF NOT EXISTS email_contacts (
            id            BIGSERIAL PRIMARY KEY,
            brand         TEXT NOT NULL,
            email         TEXT NOT NULL,
            email_lc      TEXT NOT NULL,
            status        TEXT NOT NULL DEFAULT 'pending',
            verticals     TEXT DEFAULT '',
            source        TEXT,
            wrapper       TEXT,
            lang          TEXT,
            country       TEXT,
            tg_id         BIGINT,
            consent_text  TEXT,
            consent_ver   TEXT,
            consent_ts    DOUBLE PRECISION,
            consent_ip    TEXT,
            confirm_token TEXT,
            unsub_token   TEXT,
            confirmed_at  DOUBLE PRECISION,
            unsub_at      DOUBLE PRECISION,
            created_at    DOUBLE PRECISION,
            updated_at    DOUBLE PRECISION,
            esp_ok        BOOLEAN,
            esp_name      TEXT,
            esp_synced_at DOUBLE PRECISION,
            esp_error     TEXT,
            UNIQUE (brand, email_lc)
        );""")
        # Миграция для уже существующих таблиц (колонки добавляются в конец —
        # порядок совпадает с CREATE выше, поэтому _COLS остаётся валидным).
        for col, typ in (("esp_ok", "BOOLEAN"), ("esp_name", "TEXT"),
                         ("esp_synced_at", "DOUBLE PRECISION"), ("esp_error", "TEXT")):
            c.execute(f"ALTER TABLE email_contacts ADD COLUMN IF NOT EXISTS {col} {typ};")
        c.execute("""
        CREATE TABLE IF NOT EXISTS email_consent_log (
            id       BIGSERIAL PRIMARY KEY,
            brand    TEXT, email_lc TEXT, event TEXT, ip TEXT, meta TEXT,
            ts       DOUBLE PRECISION
        );""")
        c.execute("CREATE INDEX IF NOT EXISTS ix_contacts_token  ON email_contacts (confirm_token);")
        c.execute("CREATE INDEX IF NOT EXISTS ix_contacts_unsub  ON email_contacts (unsub_token);")
    _pg_ready = True

_COLS = ["id","brand","email","email_lc","status","verticals","source","wrapper","lang",
         "country","tg_id","consent_text","consent_ver","consent_ts","consent_ip",
         "confirm_token","unsub_token","confirmed_at","unsub_at","created_at","updated_at",
         "esp_ok","esp_name","esp_synced_at","esp_error"]

def _row_to_dict(row) -> dict:
    d = dict(zip(_COLS, row))
    d["verticals"] = [v for v in (d.get("verticals") or "").split(",") if v]
    return d


# ── JSON backend (dev only) ─────────────────────────────────────────────────
_json_db = {"contacts": {}, "log": []}

def _json_load():
    global _json_db
    if os.path.exists(EMAIL_DB_PATH):
        try:
            with open(EMAIL_DB_PATH) as f:
                _json_db = json.load(f)
        except Exception as e:
            logger.error(f"email db load error: {e}")

def _json_save():
    try:
        tmp = EMAIL_DB_PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(_json_db, f, indent=2, ensure_ascii=False)
        os.replace(tmp, EMAIL_DB_PATH)
    except Exception as e:
        logger.error(f"email db save error: {e}")

def _json_key(brand, email_lc):
    return f"{brand}:{email_lc}"

if not _USE_PG:
    _json_load()
else:
    try:
        _pg_init()
    except Exception as e:  # don't crash the whole API on a bad DB url; log loudly
        logger.error(f"Postgres init failed, email capture degraded: {e}")


# ── public API ──────────────────────────────────────────────────────────────
def upsert_pending(email, brand, *, verticals, source, wrapper, lang, country,
                   tg_id=None, consent_text="", consent_ver="", ip=""):
    """Insert or refresh a pending contact. Returns (record, is_new).

    Re-subscribing an unsubscribed/pending contact resets it to pending with a
    fresh confirm token (so a new double-opt-in email is sent). A contact that
    is already 'confirmed' is returned as-is (idempotent, no re-email).
    """
    email_lc = _norm_email(email)
    verticals_s = ",".join(verticals or [])
    now = _now()
    if _USE_PG:
        _pg_init()
        with _pg() as c:
            cur = c.execute("SELECT * FROM email_contacts WHERE brand=%s AND email_lc=%s",
                            (brand, email_lc))
            existing = cur.fetchone()
            if existing:
                rec = _row_to_dict(existing)
                if rec["status"] == "confirmed":
                    return rec, False
                ctoken = _token()
                c.execute("""UPDATE email_contacts SET status='pending', verticals=%s,
                             source=%s, wrapper=%s, lang=%s, country=%s, tg_id=%s,
                             consent_text=%s, consent_ver=%s, consent_ts=%s, consent_ip=%s,
                             confirm_token=%s, updated_at=%s
                             WHERE brand=%s AND email_lc=%s""",
                          (verticals_s, source, wrapper, lang, country, tg_id,
                           consent_text, consent_ver, now, ip, ctoken, now, brand, email_lc))
                cur = c.execute("SELECT * FROM email_contacts WHERE brand=%s AND email_lc=%s",
                                (brand, email_lc))
                _log(brand, email_lc, "resubscribe_pending", ip, {"verticals": verticals})
                return _row_to_dict(cur.fetchone()), False
            ctoken, utoken = _token(), _token()
            c.execute("""INSERT INTO email_contacts
                (brand,email,email_lc,status,verticals,source,wrapper,lang,country,tg_id,
                 consent_text,consent_ver,consent_ts,consent_ip,confirm_token,unsub_token,
                 created_at,updated_at)
                VALUES (%s,%s,%s,'pending',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (brand, email, email_lc, verticals_s, source, wrapper, lang, country, tg_id,
                 consent_text, consent_ver, now, ip, ctoken, utoken, now, now))
            cur = c.execute("SELECT * FROM email_contacts WHERE brand=%s AND email_lc=%s",
                            (brand, email_lc))
            _log(brand, email_lc, "subscribe_pending", ip, {"verticals": verticals, "source": source})
            return _row_to_dict(cur.fetchone()), True

    # JSON fallback
    k = _json_key(brand, email_lc)
    rec = _json_db["contacts"].get(k)
    if rec and rec["status"] == "confirmed":
        return _json_pub(rec), False
    if rec:
        rec.update(status="pending", verticals=verticals_s, source=source, wrapper=wrapper,
                   lang=lang, country=country, tg_id=tg_id, consent_text=consent_text,
                   consent_ver=consent_ver, consent_ts=now, consent_ip=ip,
                   confirm_token=_token(), updated_at=now)
        _json_save()
        _log(brand, email_lc, "resubscribe_pending", ip, {"verticals": verticals})
        return _json_pub(rec), False
    rec = dict(brand=brand, email=email, email_lc=email_lc, status="pending",
               verticals=verticals_s, source=source, wrapper=wrapper, lang=lang,
               country=country, tg_id=tg_id, consent_text=consent_text, consent_ver=consent_ver,
               consent_ts=now, consent_ip=ip, confirm_token=_token(), unsub_token=_token(),
               confirmed_at=None, unsub_at=None, created_at=now, updated_at=now)
    _json_db["contacts"][k] = rec
    _json_save()
    _log(brand, email_lc, "subscribe_pending", ip, {"verticals": verticals, "source": source})
    return _json_pub(rec), True


def _json_pub(rec) -> dict:
    d = dict(rec)
    d["verticals"] = [v for v in (rec.get("verticals") or "").split(",") if v]
    return d


def get_by_token(token, kind="confirm"):
    field = "confirm_token" if kind == "confirm" else "unsub_token"
    if _USE_PG:
        _pg_init()
        with _pg() as c:
            cur = c.execute(f"SELECT * FROM email_contacts WHERE {field}=%s", (token,))
            row = cur.fetchone()
            return _row_to_dict(row) if row else None
    for rec in _json_db["contacts"].values():
        if rec.get(field) == token:
            return _json_pub(rec)
    return None


def mark(email_lc, brand, status, ip=""):
    now = _now()
    ts_field = {"confirmed": "confirmed_at", "unsubscribed": "unsub_at"}.get(status)
    if _USE_PG:
        _pg_init()
        with _pg() as c:
            if ts_field:
                c.execute(f"UPDATE email_contacts SET status=%s, {ts_field}=%s, updated_at=%s "
                          f"WHERE brand=%s AND email_lc=%s", (status, now, now, brand, email_lc))
            else:
                c.execute("UPDATE email_contacts SET status=%s, updated_at=%s "
                          "WHERE brand=%s AND email_lc=%s", (status, now, brand, email_lc))
    else:
        rec = _json_db["contacts"].get(_json_key(brand, email_lc))
        if rec:
            rec["status"] = status
            rec["updated_at"] = now
            if ts_field:
                rec[ts_field] = now
            _json_save()
    _log(brand, email_lc, status, ip, {})


def erase(email_lc, brand, ip=""):
    """GDPR right-to-erasure: drop the contact row. Keep a minimal anonymised log."""
    if _USE_PG:
        _pg_init()
        with _pg() as c:
            c.execute("DELETE FROM email_contacts WHERE brand=%s AND email_lc=%s", (brand, email_lc))
    else:
        _json_db["contacts"].pop(_json_key(brand, email_lc), None)
        _json_save()
    _log(brand, "[erased]", "erase", ip, {})


def set_esp_status(email_lc, brand, esp_name, ok, error=None):
    """Записать результат пуша контакта в ESP. Источник правды для ре-синка."""
    now = _now()
    if _USE_PG:
        _pg_init()
        with _pg() as c:
            c.execute("UPDATE email_contacts SET esp_ok=%s, esp_name=%s, "
                      "esp_synced_at=%s, esp_error=%s, updated_at=%s "
                      "WHERE brand=%s AND email_lc=%s",
                      (bool(ok), esp_name, now, (None if ok else (error or "")[:300]),
                       now, brand, email_lc))
    else:
        rec = _json_db["contacts"].get(_json_key(brand, email_lc))
        if rec:
            rec["esp_ok"] = bool(ok)
            rec["esp_name"] = esp_name
            rec["esp_synced_at"] = now
            rec["esp_error"] = None if ok else (error or "")[:300]
            rec["updated_at"] = now
            _json_save()


def pending_esp_sync(brand=None):
    """Confirmed-контакты, которые ещё НЕ доехали до ESP (esp_ok не True).

    Сюда попадают и старые записи (esp_ok = NULL), и те, у кого пуш падал.
    """
    if _USE_PG:
        _pg_init()
        with _pg() as c:
            q = ("SELECT * FROM email_contacts "
                 "WHERE status='confirmed' AND (esp_ok IS NULL OR esp_ok=FALSE)")
            args = ()
            if brand:
                q += " AND brand=%s"; args = (brand,)
            return [_row_to_dict(r) for r in c.execute(q, args).fetchall()]
    return [_json_pub(r) for r in _json_db["contacts"].values()
            if r["status"] == "confirmed" and not r.get("esp_ok")
            and (not brand or r["brand"] == brand)]


def _log(brand, email_lc, event, ip, meta):
    now = _now()
    if _USE_PG:
        try:
            with _pg() as c:
                c.execute("INSERT INTO email_consent_log (brand,email_lc,event,ip,meta,ts) "
                          "VALUES (%s,%s,%s,%s,%s,%s)",
                          (brand, email_lc, event, ip, json.dumps(meta, ensure_ascii=False), now))
        except Exception as e:
            logger.error(f"consent log error: {e}")
    else:
        _json_db["log"].append(dict(brand=brand, email_lc=email_lc, event=event,
                                     ip=ip, meta=meta, ts=now))
        _json_save()


def counts(brand=None) -> dict:
    """Funnel counters for CRO: pending / confirmed / unsubscribed."""
    out = {"pending": 0, "confirmed": 0, "unsubscribed": 0, "total": 0}
    if _USE_PG:
        _pg_init()
        with _pg() as c:
            q = "SELECT status, COUNT(*) FROM email_contacts"
            args = ()
            if brand:
                q += " WHERE brand=%s"; args = (brand,)
            q += " GROUP BY status"
            for status, n in c.execute(q, args).fetchall():
                out[status] = n
    else:
        for rec in _json_db["contacts"].values():
            if brand and rec["brand"] != brand:
                continue
            out[rec["status"]] = out.get(rec["status"], 0) + 1
    out["total"] = out["pending"] + out["confirmed"] + out["unsubscribed"]
    return out


def all_confirmed(brand=None):
    """Confirmed contacts (for ESP sync / export)."""
    if _USE_PG:
        _pg_init()
        with _pg() as c:
            q = "SELECT * FROM email_contacts WHERE status='confirmed'"
            args = ()
            if brand:
                q += " AND brand=%s"; args = (brand,)
            return [_row_to_dict(r) for r in c.execute(q, args).fetchall()]
    return [_json_pub(r) for r in _json_db["contacts"].values()
            if r["status"] == "confirmed" and (not brand or r["brand"] == brand)]
