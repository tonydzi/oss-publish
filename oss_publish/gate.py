# -*- coding: utf-8 -*-
"""The final gate: scan an ENTIRE repo tree for anything real that must not ship.

    python oss_publish/gate.py --rules rules.json <repo>              # exit 1 = do not publish
    python oss_publish/gate.py --rules rules.json <repo> --paranoid   # + a soft tier to read

WHY THE WHOLE TREE, EVERY TIME
    Because of what we found on 2026-07-28. Twenty-two skills had been published weeks
    earlier by an earlier version of the sanitizer, and nobody had looked at them since.
    Re-scanning the tree - not the new files, the TREE - turned up 17 hits in what was
    already public: colleagues' real names, a real hostname, absolute paths off a real
    drive. Some sat in a hand-maintained INDEX.md that the sanitizer never writes, so it
    had never been substituted by anything, ever.

    "Already published" is not a synonym for "already checked". Run this over the finished
    checkout, right before the push, as the last thing that happens.

TWO TIERS, ON PURPOSE
    The HARD tier catches shapes somebody already thought of. That works for the names and
    handles you know about and is useless against the leak nobody predicted, so it fails
    the build and stays quiet otherwise.

    The SOFT tier flags things that are USUALLY innocent - a private IP, an env var called
    TOKEN, a 200-character base64 blob - and asks a human to look. It never fails the
    build, because a tier that cries wolf on every run is a tier people start bypassing.
    The one that has actually earned its place is `session-string`: a messenger session
    string is a full account takeover in one line of base64, and no name-based rule would
    ever notice it going past.

The rules come from the same JSON the sanitizer uses, and the hard tier is literally the
same compiled list it checks each file against. Two gates that disagree about one string is
how a file gets held back by one, waved through by the other, and shipped anyway.
"""
from __future__ import unicode_literals

import io
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rules as rules_mod                                          # noqa: E402
from sanitize import SKIP_DIRS                                     # noqa: E402


def scan(root, rules, paranoid=False, out=None):
    """Exit 0 means: I read files, and they were clean. Nothing else may exit 0.

    A mistyped path used to print `scanned 0 text files -> CLEAN` and exit 0 - a green
    light to publish, produced by a gate that had not looked at anything. "I found no
    problems" and "I did not look" must never share an exit code, so both a missing
    directory and an empty scan are failures here."""
    out = out or sys.stdout
    if not os.path.isdir(root):
        out.write("REFUSING to scan: not a directory: %s\n" % root)
        return 1
    bad, n = 0, 0
    soft = {}
    for dirpath, dirs, fns in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in sorted(fns):
            if os.path.splitext(fn)[1].lower() not in rules.text_ext:
                continue
            p = os.path.join(dirpath, fn)
            n += 1
            with io.open(p, encoding="utf-8", errors="replace") as fh:
                t = fh.read()
            rel = os.path.relpath(p, root).replace("\\", "/")
            for name, rx in rules.gate:
                m = rx.search(t)
                if m:
                    bad += 1
                    out.write("  HIT %-14s %s :: %r\n" % (name, rel, m.group(0)[:48]))
            if not paranoid:
                continue
            for name, rx in rules.gate_soft:
                allow = dict(rules.gate_soft_allow).get(name)
                for m in rx.finditer(t):
                    hit = m.group(0)
                    if allow and allow.match(hit):
                        continue
                    soft.setdefault(name, []).append(
                        (rel, t[:m.start()].count("\n") + 1, hit[:70]))

    if not n:
        out.write("REFUSING: scanned 0 text files in %s. A tree you are about to publish "
                  "has files in it, so this is a wrong path or a wrong text_ext list - "
                  "not a clean repo.\n" % root)
        return 1
    out.write("scanned %d text files -> %s\n"
              % (n, "CLEAN" if not bad else "%d HITS" % bad))
    if paranoid:
        out.write("\n--- soft tier: %d categories, review by hand ---\n"
                  % len([k for k, v in soft.items() if v]))
        for name, rows in sorted(soft.items(), key=lambda kv: -len(kv[1])):
            out.write("\n  %s : %d\n" % (name, len(rows)))
            seen = set()
            for f, ln, hit in rows:
                if hit.lower() in seen:
                    continue
                seen.add(hit.lower())
                if len(seen) > 15:
                    out.write("     ... %d more occurrences\n" % (len(rows) - 15))
                    break
                out.write("     %-48s:%-5d %s\n" % (f, ln, hit))
    return 1 if bad else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Final publication gate over a whole tree.")
    ap.add_argument("repo", nargs="?", default=".", help="the tree about to be pushed")
    ap.add_argument("--rules", required=True, help="path to your rules JSON")
    ap.add_argument("--paranoid", action="store_true", help="also print the soft tier")
    a = ap.parse_args(argv)
    return scan(a.repo, rules_mod.load(a.rules), a.paranoid)


if __name__ == "__main__":
    sys.exit(main())
