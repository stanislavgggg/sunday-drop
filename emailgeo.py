"""
emailgeo.py — geo gating for gambling-adjacent email capture (EU focus).

This is a MECHANISM, not legal advice. Gambling-advertising rules differ per
EU member state and change often; the default deny-set below is a conservative
starting point covering markets widely known for strict gambling-ad regimes.
Confirm the actual policy with compliance/legal and override via env.

Env:
  EMAIL_GEO_MODE = allow_all | deny_list (default) | allow_list
  EMAIL_GEO_DENY = comma ISO-2 codes to block   (used in deny_list mode)
  EMAIL_GEO_ALLOW = comma ISO-2 codes to permit  (used in allow_list mode)

country_status(cc) -> ("allow" | "block", reason)
"""
import os

MODE = os.environ.get("EMAIL_GEO_MODE", "deny_list").strip().lower()

# Conservative default: markets with strict / restrictive gambling-ad regimes.
# EDIT THIS with compliance before launch — it is a starting point only.
_DEFAULT_DENY = {"IT", "ES", "DE", "NL", "BE", "PL", "FR"}

_DENY  = {c.strip().upper() for c in os.environ.get("EMAIL_GEO_DENY", "").split(",") if c.strip()} \
         or _DEFAULT_DENY
_ALLOW = {c.strip().upper() for c in os.environ.get("EMAIL_GEO_ALLOW", "").split(",") if c.strip()}


def country_status(cc: str):
    cc = (cc or "").strip().upper()
    if MODE == "allow_all":
        return "allow", "geo gating disabled"
    if MODE == "allow_list":
        if not cc:
            return "block", "unknown country, allow_list mode"
        return ("allow", "in allow list") if cc in _ALLOW else ("block", "not in allow list")
    # deny_list (default)
    if cc and cc in _DENY:
        return "block", f"{cc} in deny list (restricted gambling-ad market)"
    return "allow", "not denied"


def is_allowed(cc: str) -> bool:
    return country_status(cc)[0] == "allow"
