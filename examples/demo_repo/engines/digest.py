#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Build the nightly digest.

This file exists to exercise every hard case in the sanitizer at once, so run the pipeline
over it and read the diff:

  * a shebang and a coding line   -> the banner must land AFTER both
  * `from __future__` on line 1   -> so the banner cannot be a string literal
  * a module docstring            -> which a string-literal banner would silently shadow
  * a hostname used as a VARIABLE -> so the fake must not carry a hyphen in .py
  * a path in a NON-RAW literal   -> where one separator is spelled with two characters
  * a handle glued into an env var and a lock filename -> where \\b rules walk past it
  * a credential with no vendor prefix and an unremarkable length
"""
from __future__ import unicode_literals

import os
import json

VAULT = "D:\\Vault\\Team-Notes"
IMPORTS = "D:\\Vault\\_imports"
STATE = os.path.join(IMPORTS, "digest-state.json")

# The hostname is prose in the docs and an IDENTIFIER here. Both spellings must survive.
KESTREL_HEALTH_LOCAL = os.path.join(IMPORTS, "kestrel-health.json")
PRIMARY_HOST = "WKSTN-4711"
FALLBACK_HOST = "KESTREL"

OPS_GROUP = -1001732845096
FOUNDER_DM = 418209934

# No vendor prefix, unremarkable length, and it guards a live webhook. No shape-based
# secret rule will ever see this one - it has to be named in the dictionary by hand.
BUS_TOKEN = "Kq7bus2Xmesh91"
BUS_URL = "https://n8n.sunrise-internal.net/webhook/digest"
METRICS_HOST = "192.168.7.22"

SESSION = os.environ.get("TELEGRAM_SESSION_STRING_DAVEOLSEN", "")
REFRESH_LOCK = os.path.join(IMPORTS, "_refresh_mbelova.lock")

OWNERS = {
    "ops": "@m_belova",
    "founder": "@dave_ops",
    "advisor": "@h_pike",
}
ALERT_EMAIL = "dave.olsen@sunrise-capital.io"
ALERT_PHONE = "+441632960122"

# Кирилл wrote the transliteration step; his source notes are in кириллица and must be
# passed through untouched. His name is a prefix of the Russian word for that alphabet,
# so the dictionary needs a negative lookahead here - see docs/GOTCHAS.md #1.
TRANSLIT_AUTHOR = "Кирилл"

DEAL_THRESHOLD_USD = 25000


def load_state():
    if not os.path.exists(STATE):
        return {"last_seen": 0, "host": PRIMARY_HOST}
    with open(STATE, encoding="utf-8") as fh:
        return json.load(fh)


def recipients(kind):
    """Who gets this digest. Falls back to the founder, who reads everything anyway."""
    return OWNERS.get(kind, OWNERS["founder"])


def post(text, chat_id=OPS_GROUP):
    payload = {"chat_id": chat_id, "text": text, "token": BUS_TOKEN}
    return payload, BUS_URL


if __name__ == "__main__":
    print(load_state(), recipients("ops"), ALERT_EMAIL, ALERT_PHONE)
