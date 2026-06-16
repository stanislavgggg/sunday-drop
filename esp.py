"""
esp.py — MARKETING email-service-provider adapters + segment routing.

The contact DB is the system of record; an ESP is a swappable OUTPUT. On
double-opt-in confirmation we push the contact to the ESP that matches its
segment:
  soft segment (crypto/esports/football news)  -> ESP_SOFT (e.g. Mailchimp)
  hard segment (casino/sports betting promos)   -> ESP_HARD (iGaming-tolerant)

NEVER route a hard/gambling segment to Mailchimp — it bans that content and
can terminate the account (and freeze the list).
"""
import os
import json
import hashlib
import asyncio
import logging
import urllib.request
import urllib.error

import emailcfg

logger = logging.getLogger(__name__)


class BaseESP:
    name = "base"
    last_error = None  # set to a short string when the most recent push failed
    async def push(self, rec: dict) -> bool:
        raise NotImplementedError


class NoopESP(BaseESP):
    """Dev / not-yet-configured. Records intent, sends nothing."""
    name = "noop"
    PUSHED: list = []
    async def push(self, rec: dict) -> bool:
        self.last_error = None
        self.PUSHED.append({"email": rec.get("email"), "verticals": rec.get("verticals"),
                            "brand": rec.get("brand")})
        logger.info(f"[esp:noop] would push {rec.get('email')} ({rec.get('verticals')})")
        return True


class MailchimpESP(BaseESP):
    """Upsert a confirmed contact into a Mailchimp audience with interest tags.

    Use ONLY for the soft (non-gambling) segment. Marketing-Mailchimp prohibits
    gambling content.
    """
    name = "mailchimp"

    def __init__(self):
        self.key = emailcfg.MAILCHIMP_API_KEY
        self.list_id = emailcfg.MAILCHIMP_LIST_ID
        self.dc = emailcfg.MAILCHIMP_DC or (self.key.split("-")[-1] if "-" in self.key else "")

    def _ok(self) -> bool:
        return bool(self.key and self.list_id and self.dc)

    def _req(self, method, path, payload=None):
        url = f"https://{self.dc}.api.mailchimp.com/3.0{path}"
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        # Mailchimp uses HTTP basic auth: any user + apikey
        import base64
        token = base64.b64encode(f"anystring:{self.key}".encode()).decode()
        req.add_header("Authorization", f"Basic {token}")
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read()

    def _push_sync(self, rec) -> bool:
        self.last_error = None
        if not self._ok():
            self.last_error = "not_configured(key/list/dc)"
            logger.error("[esp:mailchimp] not configured (key/list/dc)")
            return False
        email = rec["email"]
        h = hashlib.md5(email.strip().lower().encode()).hexdigest()
        body = {
            "email_address": email,
            "status_if_new": "subscribed",
            "status": "subscribed",
        }
        # Merge fields только если они существуют в audience — не добавляем кастомные,
        # чтобы не получить 400 "merge field not found". Стандартные FNAME/LNAME не трогаем.
        try:
            self._req("PUT", f"/lists/{self.list_id}/members/{h}", body)
            logger.info(f"[esp:mailchimp] upserted {email}")
            # Тэги вертикалей — separate endpoint, падение не критично
            verticals = rec.get("verticals") or []
            if isinstance(verticals, str):
                import json as _json
                try:
                    verticals = _json.loads(verticals)
                except Exception:
                    verticals = []
            tags = [{"name": v, "status": "active"} for v in verticals if v]
            if tags:
                try:
                    self._req("POST", f"/lists/{self.list_id}/members/{h}/tags", {"tags": tags})
                    logger.info(f"[esp:mailchimp] tagged {email} {tags}")
                except Exception as tag_err:
                    logger.warning(f"[esp:mailchimp] tags failed (non-critical): {tag_err}")
            return True
        except urllib.error.HTTPError as e:
            body_bytes = e.read()
            # Вытаскиваем человекочитаемый detail из ответа Mailchimp, если есть.
            detail = None
            try:
                detail = json.loads(body_bytes.decode()).get("detail")
            except Exception:
                detail = None
            self.last_error = f"HTTP {e.code}: {detail or body_bytes[:200]}"
            logger.error(f"[esp:mailchimp] HTTP {e.code}: {body_bytes[:300]}")
            return False
        except Exception as e:
            self.last_error = f"error: {e}"
            logger.error(f"[esp:mailchimp] error: {e}")
            return False

    async def push(self, rec) -> bool:
        return await asyncio.to_thread(self._push_sync, rec)


_REGISTRY = {"noop": NoopESP, "mailchimp": MailchimpESP}
_instances: dict = {}

def _get(name: str) -> BaseESP:
    name = name if name in _REGISTRY else "noop"
    if name not in _instances:
        _instances[name] = _REGISTRY[name]()
    return _instances[name]


async def push_contact(rec: dict) -> dict:
    """Route a confirmed contact to the ESP for its segment. Returns a small report."""
    # verticals из emaildb может прийти как JSON-строка ('["crypto","football"]'),
    # а не как список — безопасно распарсиваем.
    raw_v = rec.get("verticals")
    if isinstance(raw_v, str):
        try:
            import json as _json
            raw_v = _json.loads(raw_v)
        except Exception:
            raw_v = [v.strip() for v in raw_v.strip("[]").replace('"', '').split(",") if v.strip()]
    elif not isinstance(raw_v, list):
        raw_v = []
    seg = emailcfg.segment_for(raw_v)
    esp_name = emailcfg.ESP_HARD if seg == "hard" else emailcfg.ESP_SOFT
    # Hard guard: never let a gambling segment go to Mailchimp.
    if seg == "hard" and esp_name == "mailchimp":
        logger.error("[esp] refusing to route hard/gambling segment to Mailchimp")
        esp_name = "noop"
    logger.info(f"[esp] routing verticals={raw_v} seg={seg} esp={esp_name}")
    esp = _get(esp_name)
    ok = await esp.push(rec)
    return {"segment": seg, "esp": esp.name, "ok": ok,
            "error": (None if ok else getattr(esp, "last_error", None))}
