# -*- coding: utf-8 -*-
r"""Publish a private tree in public with its personal data SUBSTITUTED, not stripped.

    python oss_publish/sanitize.py --rules rules.json --src <private> --dst <public>
    python oss_publish/sanitize.py --rules rules.json --src <private> --dst <public> --apply
    python oss_publish/sanitize.py ... --report        # per-file list of what changed
    python oss_publish/sanitize.py ... --apply --prune # delete files the source no longer has
    python oss_publish/sanitize.py ... --banner        # prepend a "placeholders inside" notice to .py

Dry run by default. Nothing is written without --apply.

THE POLICY
    Every value that identifies a private person, a private chat or one of your own
    accounts is replaced by a PLAUSIBLE FAKE OF THE SAME SHAPE. Not `<REDACTED>`.

    A redaction is a hole. `chat_id=<REDACTED>` teaches a reader nothing, breaks every
    example, and turns documentation into a puzzle - so people stop publishing, or publish
    with the holes filled back in by hand, which is worse. A fake of the same shape keeps
    the docs WORKING: a supergroup id still looks like a supergroup id, a path still looks
    like a path, and the code still parses and still runs - it just talks to nothing until
    the reader points it at their own accounts.

    Substitution is deterministic (hash-derived), so the same input always yields the same
    fake, in every file, on every run. That is what makes re-publishing a no-op instead of
    a diff full of churn - and it means a reader can follow one fake person across twelve
    files and see a coherent system.

THE ORDER IS THE ALGORITHM
    Tables run in a fixed sequence, and the sequence is load-bearing. Credentials and live
    endpoints go first, while they are still intact: run them later and a name or id rule
    chews a piece out of the middle, leaving a mangled string that no longer matches the
    secret table and no longer looks like a secret to the gate. Paths come next because
    they contain account names that later rules would otherwise eat piecemeal. Full names
    precede bare tokens so "Dave Olsen" never becomes "Omar Olsen".

    This is why the JSON supplies values and the engine owns the sequence.

WHAT THIS IS NOT
    It is not a secret scanner. It hides what you TELL it to hide, plus ids, emails and
    (optionally) any surviving address. The gate below is what catches your mistakes, and
    docs/SECURITY.md is honest about the rest: substitution protects the NEXT publish. A
    credential that already shipped must be rotated, not renamed.
"""
from __future__ import unicode_literals

import io
import os
import re
import sys
import json
import hashlib
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rules as rules_mod                                          # noqa: E402

BANNER = """\
# ---------------------------------------------------------------------------
# PUBLISHED SAMPLE - the paths and identifiers below are placeholders, not live
# values. Chat ids, handles, phone numbers and e-mail addresses were swapped for
# fakes of the SAME SHAPE, so this file still reads and still parses - but it
# talks to nothing until you point it at your own accounts and paths.
# ---------------------------------------------------------------------------"""


# ---------------------------------------------------------------------------
# deterministic fakes
# ---------------------------------------------------------------------------
def _pick(pool, seed):
    return pool[int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16) % len(pool)]


def fake_person(rules, name, full=False, pool=None):
    """Same name in, same fake out - forever, on any machine, in any order. sha256, not
    random and not a counter: a counter depends on the order files were walked, so adding
    one file at the top of the tree would rename everybody below it and produce a diff
    nobody can review.

    Script follows script: a Cyrillic name gets a Cyrillic fake. Swap the alphabet and a
    reader who knows the language sees a system that was clearly machine-mangled, which is
    the opposite of the point."""
    cyr = bool(re.search(r"[А-Яа-яЁё]", name))
    if full:
        f = rules.pools["ru_first" if cyr else "first"]
        l = rules.pools["ru_last" if cyr else "last"]
        return "%s %s" % (_pick(f, name), _pick(l, name + "L"))
    if pool:
        pool = ("ru_" + pool) if (cyr and ("ru_" + pool) in rules.pools) else pool
        return _pick(rules.pools[pool], name)
    return _pick(rules.pools["ru_first" if cyr else "first"], name)


def fake_id(rules, real, id_map):
    """A fake id of the SAME SHAPE. Shape carries meaning: a Telegram supergroup id starts
    with 100 and a reader who knows that can tell a group from a user at a glance. Destroy
    the shape and the example stops teaching."""
    if real.lstrip("-") in rules.protected_ids:
        return real                     # already a fake somebody else wrote; see rules.py
    if real in id_map:
        return id_map[real]
    neg = real.startswith("-")
    digits = real.lstrip("-")
    h = int(hashlib.sha256(real.encode("utf-8")).hexdigest(), 16)
    body = None
    for pref in rules.id_shape_prefixes:
        if digits.startswith(pref) and len(digits) > len(pref):
            n = len(digits) - len(pref)
            body = pref + str(h % (10 ** n)).zfill(n)
            break
    if body is None:
        body = str(h % (10 ** len(digits))).zfill(len(digits))
        if body[0] == "0":          # keep the digit count honest: no leading zero
            body = "7" + body[1:]
    out = ("-" if neg else "") + body
    id_map[real] = out
    return out


# ---------------------------------------------------------------------------
# the substitution itself
# ---------------------------------------------------------------------------
def sanitize(text, rules, code=False, id_map=None):
    """code=True when the file is python. See the hostname loop for the only difference."""
    id_map = {} if id_map is None else id_map

    # 1. credentials and live endpoints, while they are still intact
    for k, v in rules.secret_literals:
        text = text.replace(k, v)
    for k, v in rules.infra:
        text = re.sub(re.escape(k), v, text, flags=re.I)

    # 2. paths, which contain account names later rules would mangle piecemeal.
    #    Replacements are escaped: a Windows replacement like %VAULT%\_originals is passed
    #    to re.sub, where a backslash is an escape character, and \1 in a replacement means
    #    "group 1", not "backslash one".
    for pat, rep in rules.paths:
        text = re.sub(pat, rep.replace("\\", "\\\\"), text, flags=re.I)

    # 3. people: stems, then full names, then bare tokens
    for pat, rep in rules.people:
        text = re.sub(pat, rep, text, flags=re.I)
    for nm in rules.full_names:
        text = re.sub(r"(?<![\w])" + re.escape(nm) + r"(?![\w])",
                      fake_person(rules, nm, full=True), text, flags=re.I)
    for tok, pool in rules.person_tokens:
        # case-insensitive on purpose: these names also live INSIDE slugs and filenames
        # (person-marina-belova, content-belova-style) where the capitalisation is gone.
        text = re.sub(r"(?<![\w@])(?:" + tok + r")(?![\w])",
                      fake_person(rules, tok, pool=pool), text, flags=re.I)

    # 4. account slugs: NO word-boundary guard. A distinctive slug cannot collide with
    #    anything innocent, and it appears GLUED into env vars, lock files and paths -
    #    TELEGRAM_SESSION_STRING_DAVEOLSEN, _refresh_mbelova.lock, /DaveOlsen - which is
    #    exactly where every \b rule silently walked past it. Longest first (rules.py sorts
    #    them) so `daveolsen` is not eaten by `dave`.
    for slug, rep in rules.slugs:
        text = re.sub(re.escape(slug),
                      lambda m, r=rep: r.upper() if m.group(0).isupper() else r,
                      text, flags=re.I)

    for k, v in rules.emails:
        text = re.sub(re.escape(k), v, text, flags=re.I)
    for k, v in rules.bare:
        text = re.sub(re.escape(k), v, text, flags=re.I)
    for k, v in rules.phones:
        text = text.replace(k, v)

    # 5. hostnames need care the other tables do not. Their replacements carry a hyphen
    #    (HUB-1), and in python a hostname is not only prose - it is also a variable name
    #    (KESTREL = ...) and half of a longer one (KESTREL_HEALTH_LOCAL). Substituting the
    #    hyphen form there yields ANCHOR-1_HEALTH_LOCAL, which no parser accepts, and the
    #    published file stops being valid python. Telling "identifier" from "prose" by
    #    looking at neighbouring characters gets the glued case right and the bare
    #    assignment wrong, so python simply gets the hyphenless form throughout.
    #    Case is preserved the same way slugs are: a hostname also appears lowercased
    #    inside filenames (kestrel-health.json), and writing HUB-1 into the middle of one
    #    produces a name no reader would have chosen.
    for k, v in rules.machines:
        rep = v.replace("-", "") if code else v
        text = re.sub(re.escape(k), lambda m, r=rep: r.lower() if m.group(0).islower() else r,
                      text, flags=re.I)

    for k, v in rules.handles:
        text = re.sub(re.escape(k) + r"\b", v, text, flags=re.I)
    for pat, rep in rules.private_urls + rules.money:
        text = re.sub(pat, rep, text)

    text = rules.id_re.sub(lambda m: fake_id(rules, m.group(1), id_map), text)

    # 6. any address the tables did not name. Last, so the specific fakes above win.
    if rules.email_catchall:
        text = re.sub(r"\b[A-Za-z0-9._%+-]+@(?!example\.com|example\.org|s\.whatsapp\.net"
                      r"|users\.noreply)[A-Za-z0-9.-]+\.[a-z]{2,}\b",
                      "someone@example.com", text)
    return text


def gate_hits(text, rules):
    """What must never survive into the output. Same compiled rules the whole-tree gate
    uses - see rules.py on why there is only one list."""
    return [name for name, rx in rules.gate if rx.search(text)]


def banner_for(text):
    """Insert the notice as COMMENTS, right after any shebang/encoding line.

    It was a string literal first, which cost two things at once: a bare string is a
    STATEMENT, so it made `from __future__ import ...` illegal in every file that uses it,
    and a string placed before the author's own docstring silently BECOMES the docstring.
    Comments are invisible to the parser, so neither can happen."""
    lines = text.split("\n")
    i = 0
    while i < len(lines) and (lines[i].startswith("#!") or "coding" in lines[i][:30]):
        i += 1
    return "\n".join(lines[:i] + [BANNER] + lines[i:])


# ---------------------------------------------------------------------------
# walking a tree
# ---------------------------------------------------------------------------
SKIP_DIRS = {".git", "__pycache__", ".stversions", "node_modules", ".venv", ".idea"}


def _read(path):
    """Decoded with errors='replace': a text file with a few undecodable bytes still gets
    scanned and published rather than crashing the run. Bytes that cannot be decoded come
    out as U+FFFD, so genuinely binary content lands in the output looking like rubbish -
    which is why the extension allowlist, not this function, is what keeps binaries out."""
    with io.open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _refuse_overlap(src, dst):
    """The public tree may not live inside the private one, or the other way round.

    Nesting them means the walk eventually reads its own output and sanitizes it a second
    time. Most tables survive that - a fake handle is not in the handle table - but a fake
    ID does not, because it is still id-shaped by design, so it gets faked again and every
    id in the repo churns on every run. There is no safe way to make an id recognise itself
    (any rule that passes fakes through also passes through the real ids that satisfy it),
    so the arrangement is refused instead of survived."""
    a = os.path.normcase(os.path.abspath(src)) + os.sep
    b = os.path.normcase(os.path.abspath(dst)) + os.sep
    if a.startswith(b) or b.startswith(a):
        raise ValueError("--src and --dst overlap (%s / %s). Publish from the private tree "
                         "into a separate public checkout; never re-sanitize your own "
                         "output." % (src, dst))


def publish(src, dst, rules, apply=False, banner=False, prune=False, show_report=False):
    """Sanitize the WHOLE source tree into dst.

    Whole tree, every run, on purpose. The first version of this tool only handled files
    that were not published yet, which made it a one-shot: the source kept changing and the
    public copy quietly went stale, with nobody watching the gap. "Already published" is
    not a state this tool believes in.
    """
    # A missing --src is not an empty repo. os.walk() on a path that does not exist yields
    # nothing at all, so without this the run prints "passed the gate: 0", "APPLIED", and
    # exits 0 - a typo reading as a successful publish. Silent success is the failure mode
    # this whole tool exists to argue against; it does not get to have one.
    if not os.path.isdir(src):
        raise ValueError("--src is not a directory: %s" % src)
    _refuse_overlap(src, dst)
    id_map = {}
    written, quarantined, denied, skipped_bin, report = [], {}, {}, [], {}

    for root, dirs, fnames in os.walk(src):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in sorted(fnames):
            p = os.path.join(root, fn)
            rel = os.path.relpath(p, src).replace("\\", "/")
            ext = os.path.splitext(fn)[1].lower()
            if ext not in rules.text_ext:
                # Binary is not sanitizable and not reviewable. Naming it is the point:
                # a silent skip is how a screenshot of a private dashboard ships.
                skipped_bin.append(rel)
                continue
            if fn in rules.deny_files:
                denied[rel] = rules.deny_files[fn]
                continue
            try:
                raw = _read(p)
            except (IOError, OSError) as e:
                # A file we cannot read is a file we cannot vouch for. Quarantine (which
                # fails the run) rather than skip: skipping would let a locked or
                # permission-denied file sit in the source, unexamined, while the run
                # reports success.
                quarantined[rel] = ["unreadable: %s" % e.__class__.__name__]
                continue
            clean = sanitize(raw, rules, code=(ext == ".py"), id_map=id_map)
            if banner and ext == ".py":
                clean = banner_for(clean)
            hits = gate_hits(clean, rules)
            if hits:
                quarantined[rel] = hits
                continue
            diff = [(i, a.strip()[:120], b.strip()[:120]) for i, (a, b)
                    in enumerate(zip(raw.split("\n"), clean.split("\n")), 1) if a != b]
            # Keyed by DESTINATION path, never by basename. Two files can share a name and
            # legitimately both ship (n8n/build_dashboard.py and orphans/build_dashboard.py
            # are different programs). Keyed by name, the second silently replaced the
            # first here - and then the stale check, reading this same dict, declared the
            # survivor's twin abandoned and --prune deleted a live file.
            report[rel] = {"src": p, "lines_changed": len(diff),
                           "changes": [{"line": i, "from": a, "to": b} for i, a, b in diff]}
            written.append(rel)
            if apply:
                out = os.path.join(dst, rel)
                d = os.path.dirname(out)
                if d:
                    os.makedirs(d, exist_ok=True)
                # newline="\n" always. A CRLF written here reaches someone else's clone as
                # a file git refuses to apply patches to and diffs line-by-line forever.
                with io.open(out, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(clean)

    stale = _stale(dst, report, rules, apply, prune)

    print("source files      : %d" % (len(report) + len(quarantined) + len(denied)))
    print("passed the gate   : %d" % len(written))
    print("QUARANTINED       : %d" % len(quarantined))
    for n, probs in sorted(quarantined.items()):
        print("   %-44s %s" % (n, probs))
    print("DENIED (never publish): %d" % len(denied))
    for n, why in sorted(denied.items()):
        print("   %-44s %s" % (n, why))
    print("binary skipped    : %d %s" % (len(skipped_bin), skipped_bin[:4]))
    print("files with >=1 substitution: %d of %d"
          % (sum(1 for v in report.values() if v["lines_changed"]), len(written)))
    print("distinct ids remapped: %d" % len(id_map))
    if show_report:
        for n, v in sorted(report.items(), key=lambda kv: -kv[1]["lines_changed"]):
            if not v["lines_changed"]:
                continue
            print("\n--- %s (%d lines)" % (n, v["lines_changed"]))
            for c in v["changes"][:12]:
                print("   %4d - %s" % (c["line"], c["from"]))
                print("        + %s" % c["to"])
            if len(v["changes"]) > 12:
                print("   ... %d more" % (len(v["changes"]) - 12))
    print("APPLIED to %s" % dst if apply else "(dry run - nothing written)")
    return 1 if (quarantined or stale) else 0, {"published": sorted(report),
                                                "quarantined": quarantined,
                                                "denied": denied, "stale": stale,
                                                "id_map": id_map}


def _stale(dst, report, rules, apply, prune):
    """Files sitting in the public tree that this run did not produce.

    Publishing writes file-by-file rather than wiping dst, because dst is a live git
    checkout with a .git, a LICENSE and a README that were never in the source. So a file
    dropped from the source keeps its published copy forever, unreviewed - report it rather
    than let the directory quietly disagree with its source.
    """
    if not (apply and os.path.isdir(dst)):
        return []
    expected = set(os.path.normcase(os.path.join(dst, r.replace("/", os.sep)))
                   for r in report)
    stale = []
    for dp, dirs, fns in os.walk(dst):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in fns:
            p = os.path.join(dp, fn)
            if (os.path.splitext(fn)[1].lower() in rules.text_ext
                    and os.path.normcase(p) not in expected):
                stale.append(os.path.relpath(p, dst).replace("\\", "/"))
    if not stale:
        return []
    print("STALE in %s (published before, not produced by this run): %d" % (dst, len(stale)))
    for s in stale[:20]:
        print("   %s" % s)
    # Never let --prune do a mass delete. If the source comes back empty or tiny - a
    # mistyped path, a drive that did not mount, a filter that matched nothing - then EVERY
    # published file looks stale, and prune would wipe the repo, print nothing alarming and
    # exit 0. Deleting most of what you publish is never a routine outcome.
    share = len(stale) / float(len(report) + len(stale))
    if prune and share > 0.25:
        print("   REFUSING to prune: %d of %d published files look stale (%.0f%%)."
              % (len(stale), len(report) + len(stale), share * 100))
        print("   That is a broken source path, not a cleanup. Check --src before "
              "deleting anything.")
    elif prune:
        for s in stale:
            os.remove(os.path.join(dst, s.replace("/", os.sep)))
        print("   pruned %d stale file(s)" % len(stale))
        return []
    else:
        print("   re-run with --prune to delete them, or delete by hand.")
    # A leftover file is a failure, not a note: it is a real published file that the source
    # no longer vouches for, and git will commit it as happily as any other.
    return stale


def main(argv=None):
    ap = argparse.ArgumentParser(description="Sanitize a private tree for publication.")
    ap.add_argument("--rules", required=True, help="path to your rules JSON")
    ap.add_argument("--src", required=True, help="the private tree to publish")
    ap.add_argument("--dst", required=True, help="the public checkout to write into")
    ap.add_argument("--apply", action="store_true", help="actually write (default: dry run)")
    ap.add_argument("--banner", action="store_true", help="prepend a notice to .py files")
    ap.add_argument("--prune", action="store_true", help="delete files the source dropped")
    ap.add_argument("--report", action="store_true", help="print every substituted line")
    ap.add_argument("--json", help="write the machine-readable report here")
    a = ap.parse_args(argv)

    try:
        rules = rules_mod.load(a.rules)
        code, data = publish(a.src, a.dst, rules, apply=a.apply, banner=a.banner,
                             prune=a.prune, show_report=a.report)
    except ValueError as e:
        # A misconfiguration, not a crash. Say it in one line the operator can act on;
        # a traceback here reads as "the tool is broken" instead of "your path is wrong".
        sys.stderr.write("REFUSING: %s\n" % e)
        return 2
    if a.json:
        with io.open(a.json, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(data, ensure_ascii=False, indent=1))
    return code


if __name__ == "__main__":
    sys.exit(main())
