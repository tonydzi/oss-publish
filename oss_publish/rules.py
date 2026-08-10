# -*- coding: utf-8 -*-
"""Rule loading for the sanitizer and the gate.

The dictionary lives in JSON, never in the engine. That split is not tidiness: the
dictionary is the one part of this pipeline that is *made of* the private data it hides -
real colleagues' names, real handles, real hostnames. Ship the engine, keep your dictionary
in your own repo (or outside it entirely), and the tool itself is publishable.

The engine, on the other hand, must NOT be configurable in its ORDER. Which table runs
first is load-bearing (see sanitize.py), and a config file that let a user reorder it would
hand them a way to fragment their own secrets. So: values from JSON, sequence from code.

Schema (every key optional; see rules.example.json for a filled-in example):

  keep_handles      [str]        handles that must survive - your OWN published channels
  secret_literals   {str: str}   verbatim credentials -> placeholder. ROTATE THEM TOO.
  infra             {str: str}   reachable hosts / private addresses / workspace ids
  paths             [[rx, str]]  absolute paths -> portable variables
  people            [[rx, str]]  name stems -> fake stems (regex, applied case-insensitively)
  full_names        [str]        "First Last" - substituted before bare tokens
  person_tokens     [str]        single-token names (regex allowed: "Kirill(?!ic)")
  slugs             {str: str}   account slugs matched WITHOUT word boundaries
  handles           {str: str}   @handle -> @fake_handle
  emails            {str: str}   exact address -> exact fake
  bare              {str: str}   fragments of addresses that appear without a domain
  phones            {str: str}   exact literal -> exact fake (no regex, no boundaries)
  machines          {str: str}   hostname -> fake. Hyphens are stripped in .py files.
  money             [[rx, str]]  live deal figures -> round fakes
  private_urls      [[rx, str]]  private chat / invite / meeting links -> placeholders
  fake_pools        {str: [str]} first/last/ru_first/ru_last, drawn by hash
  id_min_digits     int          numeric ids of at least this length get faked (default 9)
  id_shape_prefixes [str]        prefixes whose shape must survive, e.g. "100" for Telegram
  email_catchall    bool         rewrite any surviving address to someone@example.com
  text_ext          [str]        which extensions are text (everything else is copied/skipped)
  gate              {str: rx}    HARD tier: a hit here means do not publish. exit 1.
  gate_soft         {str: rx}    SOFT tier: printed for a human, never fails the build
  gate_soft_allow   {str: rx}    per-category allowlist for the soft tier (kills the noise)
  deny_files        {str: str}   basename -> why this file can never be published at all

One gate, two callers. sanitize.py checks each file it writes and gate.py re-checks the
whole tree, and both compile `gate` from THIS object. Two gates with drifting rules is how
a file gets held back by one, waved through by the other, and shipped anyway.
"""
import io
import re
import json

DEFAULT_TEXT_EXT = [".md", ".py", ".txt", ".json", ".js", ".cmd", ".ps1", ".sh",
                    ".yml", ".yaml", ".sql", ".html", ".toml", ".ini", ".cfg"]

# Fallback name pools, so a rules file that lists `person_tokens` without `fake_pools`
# still produces plausible people instead of crashing.
DEFAULT_POOLS = {
    "first": ["Alex", "Marta", "Ivan", "Yuki", "Omar", "Lena", "Tomas", "Priya", "Nils",
              "Sofia", "Karim", "Dana", "Pavel", "Mei", "Hugo", "Irina", "Samir", "Nora"],
    "last": ["Berg", "Costa", "Novak", "Tanaka", "Haddad", "Moreau", "Rao", "Larsen",
             "Ferreira", "Ozturk", "Klein", "Chen", "Silva", "Lind"],
    "ru_first": ["Игорь", "Максим", "Тимур", "Олег", "Артём", "Глеб", "Марк", "Юрий"],
    "ru_last": ["Соколов", "Морозова", "Зайцев", "Орлова", "Волков", "Крылова"],
}


class Rules(object):
    """Compiled, order-normalised rules. Attribute names match the JSON keys."""

    # Tables matched as literals. Sorted longest-first at load time, because a short key
    # that is a prefix of a long one eats it: substitute `dave` before `daveolsen` and the
    # long handle becomes `<fake>olsen`, which no later rule and no gate will recognise.
    _LITERAL_MAPS = ("secret_literals", "infra", "emails", "bare", "phones",
                     "machines", "handles", "slugs")
    _REGEX_PAIRS = ("paths", "people", "money", "private_urls")

    def __init__(self, raw, source="<dict>"):
        self.source = source
        self.raw = raw
        for key in self._LITERAL_MAPS:
            setattr(self, key, sorted(raw.get(key, {}).items(), key=lambda kv: -len(kv[0])))
        for key in self._REGEX_PAIRS:
            setattr(self, key, [(p, r) for p, r in raw.get(key, [])])
        self.keep_handles = set(h.lower() for h in raw.get("keep_handles", []))
        self.full_names = sorted(raw.get("full_names", []), key=len, reverse=True)
        # A token may be written as "Belova" or as ["Belova", "last"]. Without the hint
        # every bare token drew from the first-name pool, so a surname became a first name
        # and the docs filled up with people called "Polina Sofia" - plausible enough to
        # pass a gate and odd enough that a reader stops trusting the examples.
        self.person_tokens = []
        for entry in raw.get("person_tokens", []):
            tok, pool = (entry, None) if isinstance(entry, str) else (entry[0], entry[1])
            self.person_tokens.append((tok, pool))
        self.person_tokens.sort(key=lambda tp: -len(tp[0]))
        self.pools = dict(DEFAULT_POOLS)
        self.pools.update(raw.get("fake_pools", {}))
        self.id_min_digits = int(raw.get("id_min_digits", 9))
        self.id_shape_prefixes = list(raw.get("id_shape_prefixes", ["100"]))
        self.email_catchall = bool(raw.get("email_catchall", True))
        self.text_ext = set(e.lower() for e in raw.get("text_ext", DEFAULT_TEXT_EXT))
        self.deny_files = dict(raw.get("deny_files", {}))
        self.gate = _compile_map(raw.get("gate", {}), "gate")
        self.gate_soft = _compile_map(raw.get("gate_soft", {}), "gate_soft")
        self.gate_soft_allow = _compile_map(raw.get("gate_soft_allow", {}), "gate_soft_allow")
        self.id_re = re.compile(r"(?<![\d.\-])(-?\d{%d,})(?![\d.])" % self.id_min_digits)
        # Digit runs that are ALREADY fakes, because an earlier table put them there. The
        # id rule runs last and cannot tell a real id from the fake phone number the phone
        # table just wrote, so without this it re-fakes the fake: +15550001111 (an obvious
        # reserved test number a reader recognises at a glance) came out as +96863211225,
        # which reads like somebody's actual phone. Substitution has to be idempotent
        # against ITSELF, not just across runs.
        self.protected_ids = set()
        for key in ("phones", "machines", "infra", "emails", "handles", "slugs"):
            for _, v in getattr(self, key):
                self.protected_ids.update(re.findall(r"\d{%d,}" % self.id_min_digits, v))
        self._check()

    def _check(self):
        """Fail at load, not mid-run. A rules file with a broken regex used to blow up
        halfway through a tree, leaving a half-written output directory that looked like a
        successful publish."""
        for key in self._REGEX_PAIRS:
            for pat, _ in getattr(self, key):
                _try(pat, "%s: %r" % (key, pat))
        for tok, pool in self.person_tokens:
            _try(tok, "person_tokens: %r" % tok)
            if pool and pool not in self.pools:
                raise ValueError("person_tokens: %r asks for pool %r, which fake_pools "
                                 "does not define" % (tok, pool))

    def keeps_handle(self, handle):
        return handle.lower().rstrip("_") in self.keep_handles


def _try(pattern, where):
    try:
        re.compile(pattern)
    except re.error as e:
        raise ValueError("bad regex in %s -- %s" % (where, e))


def _compile_map(d, where):
    """Gate patterns are compiled with no flags. Case-insensitivity is written inline as
    `(?i)` in the JSON, so the rules file states it where a reader can see it - rather than
    having the engine apply a flag the author of the pattern never asked for. It matters
    here more than elsewhere: a path rule made case-insensitive by an invisible default
    starts matching `/users/` inside ordinary URLs and gets deleted by whoever it annoys."""
    out = []
    for name, pat in sorted(d.items()):
        _try(pat, "%s.%s" % (where, name))
        out.append((name, re.compile(pat)))
    return out


def load(path):
    with io.open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    return Rules(raw, source=path)
