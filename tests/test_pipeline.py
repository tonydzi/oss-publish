# -*- coding: utf-8 -*-
"""Regression tests. Every one of these is a bug that shipped once.

    python -m unittest discover -s tests -v          (from the repo root)
    python tests/test_pipeline.py                    (same thing, no discovery)

A test here is not "does the function return something". It is a specific way this pipeline
was observed to leak, mangle or lie, pinned so it cannot come back. If you add a rule kind,
add the test that would have caught the mistake you nearly made writing it.
"""
from __future__ import unicode_literals

import io
import os
import re
import sys
import json
import shutil
import hashlib
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "oss_publish"))

import rules as rules_mod          # noqa: E402
import sanitize as san             # noqa: E402
import gate as gate_mod            # noqa: E402

RULES_PATH = os.path.join(ROOT, "rules.example.json")
DEMO = os.path.join(ROOT, "examples", "demo_repo")


def load():
    return rules_mod.load(RULES_PATH)


def clean(text, code=False, rules=None):
    return san.sanitize(text, rules or load(), code=code)


class TestSubstitution(unittest.TestCase):

    def test_substitution_replaces_the_person_and_spares_the_word(self):
        """`Кирилл` is a name; `кириллица` is the Cyrillic alphabet. The person goes, the
        alphabet stays.

        In THIS layer the trailing `(?![\\w])` the engine wraps every token in is what saves
        the word - see the gate test below for the layer where it is not enough."""
        out = clean("Кирилл писал заметки в кириллице, кириллица важна")
        self.assertNotIn("Кирилл ", out)
        self.assertEqual(2, out.count("кириллиц"))

    def test_gate_pattern_needs_its_own_lookahead(self):
        """GOTCHA #1, at the layer where it actually bites.

        Gate patterns are raw regexes - the gate does NOT wrap them in a boundary guard,
        because a gate rule has to be free to match a fragment. So a name that is a prefix
        of an ordinary word fires on the word, and the gate quarantines an innocent file
        (or, worse, gets switched off by whoever it annoys). The lookahead belongs here."""
        self.assertTrue(re.search("(?i)Кирилл", "заметки в кириллице"), "the naive rule")
        guarded = dict(load().gate)["real-name"]
        self.assertFalse(guarded.search("заметки в кириллице"), "must spare the alphabet")
        self.assertTrue(guarded.search("Кирилл прислал патч"), "must still catch the person")

    def test_slug_glued_to_an_identifier(self):
        """GOTCHA #2. Handles live GLUED into env vars, lock files and paths. Every rule
        with a \\b boundary walked straight past all three."""
        for probe in ("TELEGRAM_SESSION_STRING_DAVEOLSEN",
                      "_refresh_mbelova.lock",
                      "/api/v1/daveolsen/inbox"):
            out = clean(probe)
            self.assertNotIn("daveolsen", out.lower())
            self.assertNotIn("mbelova", out.lower())

    def test_slug_case_is_preserved(self):
        """An UPPERCASE env var must stay uppercase, or the published file stops working
        for a different reason than the one we were fixing."""
        self.assertIn("OWNER_ACCT", clean("SESSION_STRING_DAVEOLSEN"))
        self.assertIn("owner_acct", clean("path/to/daveolsen/file"))

    def test_lowercase_name_inside_a_slug(self):
        """GOTCHA #3. Names live inside slugs and filenames in lower case, where the
        capitalisation that every name rule keys on is gone. Substitution must be re.I."""
        out = clean("see note person-belova-intro.md")
        self.assertNotIn("belova", out.lower())

    def test_secrets_are_substituted_first(self):
        """GOTCHA #4. Run the credential table late and a name or id rule chews a piece out
        of the middle of the token, leaving a mangled string that no longer matches the
        table AND no longer looks like a secret to the gate. Ordering is the algorithm."""
        out = clean('BUS_TOKEN = "Kq7bus2Xmesh91"')
        self.assertIn("REPLACE_WITH_YOUR_BUS_TOKEN", out)
        self.assertNotIn("Kq7bus", out)

    def test_hostname_in_code_has_no_hyphen(self):
        """GOTCHA #5. A hostname is prose in markdown and an IDENTIFIER in python.
        `ANCHOR-1_HEALTH = ...` is not valid python, so .py gets the hyphenless form and
        markdown keeps the readable one."""
        code = clean("KESTREL_HEALTH_LOCAL = 1", code=True)
        self.assertIn("LAPTOP1_HEALTH_LOCAL", code)
        self.assertNotIn("LAPTOP-1", code)
        self.assertIn("LAPTOP-1", clean("runs on NB-KESTREL tonight", code=False))

    def test_hostname_case_is_preserved(self):
        """A lowercased hostname inside a filename must not come back SHOUTING."""
        self.assertIn("laptop1-health.json", clean('f = "kestrel-health.json"', code=True))

    def test_id_keeps_its_shape(self):
        """A supergroup id starts with 100 and a reader who knows that can tell a group
        from a user at a glance. Destroy the shape and the example stops teaching."""
        out = clean("chat_id = -1001732845096")
        self.assertRegex(out, r"-100\d{10}")
        self.assertNotIn("1732845096", out)

    def test_a_fake_is_never_re_faked(self):
        """The id rule runs last and cannot tell a real id from the fake phone number the
        phone table just wrote. Without the protected set, +15550001111 - an obviously
        reserved test number - came out as +96863211225, which reads like a real phone."""
        self.assertIn("+15550001111", clean("call +441632960122 now"))

    def test_substitution_is_stable_across_runs(self):
        """Same input, same fake, always - which is what makes re-publishing a no-op
        instead of a diff full of churn."""
        src = io.open(os.path.join(DEMO, "engines", "digest.py"), encoding="utf-8").read()
        self.assertEqual(clean(src, code=True), clean(src, code=True))

    def test_a_second_pass_re_fakes_ids_and_that_is_why_trees_may_not_overlap(self):
        """GOTCHA #10, and an honest limit rather than a fix.

        Everything except numeric ids survives a second pass unchanged: a fake handle is
        not in the handle table, a fake host is not in the host table. A fake ID is the one
        exception, because it is by construction still id-SHAPED - that is the whole point
        of it - so a second pass fakes it again.

        The tempting fix is to make fake ids self-recognising, and it is a trap: any rule
        that lets the engine pass an id through untouched will also pass through the real
        ids that happen to satisfy it. Trading a leak for a cosmetic property is not a
        trade. So the property is not fixed, it is FENCED: always publish from the private
        source, never re-sanitize the public tree, and publish() refuses overlapping paths
        so you cannot arrange it by accident."""
        once = clean("chat_id = -1001732845096")
        self.assertNotEqual(once, clean(once))
        with self.assertRaises(ValueError):
            san.publish(DEMO, os.path.join(DEMO, "out"), load())

    def test_path_replacement_may_contain_backslashes(self):
        """A Windows replacement (`%USERPROFILE%\\.config`) is handed to re.sub, where a
        backslash is an escape character and `\\1` means "group 1", not "backslash one".
        The engine escapes replacements for exactly this reason.

        The probe path is assembled from `sep` rather than written as a literal, for the
        same reason the roster fixture is: this repo is published through its own pipeline,
        and a literal `C:\\Users\\<name>` in a test file is a hit like any other. A tool
        that exempts itself from its own gate has stopped being a gate."""
        sep = chr(92)
        probe = "config at C:" + sep + "Users" + sep + "dave" + sep + ".config" + sep + "a.json"
        out = clean(probe)
        self.assertIn("%USERPROFILE%" + sep + ".config", out)
        self.assertNotIn("dave", out)

    def test_soft_tier_catches_a_passphrase_with_spaces(self):
        """A no-whitespace value rule cannot see `password = 'correct horse battery staple'`.
        The hard tier keeps its narrow rule (false positives there fail builds); the soft
        tier is allowed to be greedy, because there a false positive costs ten seconds."""
        rx = dict(load().gate_soft)["assigned-secret"]
        self.assertTrue(rx.search("password = 'correct horse battery staple'"))

    def test_email_catchall_covers_what_the_table_missed(self):
        out = clean("write to nobody.expected@some-domain.net")
        self.assertIn("someone@example.com", out)

    def test_published_channel_survives(self):
        """A published channel is not personal data. Faking it turned our own call-to-action
        into a pointer at an account that does not exist."""
        self.assertIn("@acme_lab", clean("mirrored to @acme_lab"))


class TestBanner(unittest.TestCase):

    def test_banner_lands_after_shebang_and_coding_line(self):
        src = "#!/usr/bin/env python\n# -*- coding: utf-8 -*-\nimport os\n"
        out = san.banner_for(src)
        self.assertTrue(out.startswith("#!/usr/bin/env python\n# -*- coding: utf-8 -*-\n#"))

    def test_banner_does_not_break_future_import_or_shadow_the_docstring(self):
        """GOTCHA #6. The banner was a string literal first. A bare string is a STATEMENT,
        so it made `from __future__ import ...` illegal; and a string before the author's
        own docstring silently BECOMES the docstring. Comments can do neither."""
        src = '"""Real docstring."""\nfrom __future__ import unicode_literals\nX = 1\n'
        out = san.banner_for(src)
        ns = {}
        exec(compile(out, "<banner>", "exec"), ns)             # would raise on a literal
        self.assertEqual(ns["__doc__"], "Real docstring.")

    def test_published_engine_still_compiles(self):
        src = io.open(os.path.join(DEMO, "engines", "digest.py"), encoding="utf-8").read()
        compile(san.banner_for(clean(src, code=True)), "<published>", "exec")


class TestGate(unittest.TestCase):

    def test_gate_fails_on_the_raw_source(self):
        out = io.StringIO()
        self.assertEqual(1, gate_mod.scan(DEMO, load(), out=out))
        self.assertIn("HIT", out.getvalue())

    def test_gate_passes_on_sanitized_output(self):
        tmp = tempfile.mkdtemp()
        try:
            code, _ = san.publish(DEMO, tmp, load(), apply=True, banner=True)
            self.assertEqual(0, code)
            out = io.StringIO()
            self.assertEqual(0, gate_mod.scan(tmp, load(), out=out))
            self.assertIn("CLEAN", out.getvalue())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_roster_shape_is_caught_without_naming_the_file(self):
        """Substitution cannot save a roster: there is no fake of the same shape for thirty
        investors, their funds and verbatim quotes of what they replied. The data IS the
        file. The shape rule refuses a NEW file of this class without anyone remembering to
        add it to deny_files.

        The roster is assembled at runtime on purpose - written out as a literal, it would
        put the very shape this repo refuses to publish into this repo."""
        rows = "".join('    ("%sndra Berg (Fund %d)", %d, "replied"),\n'
                       % (c, i, 400000000 + i) for i, c in enumerate("ABCD"))
        text = "TARGETS = [\n" + rows + "]\n"
        rx = dict(load().gate)["people-roster"]
        self.assertTrue(rx.search(text), "the roster shape must be refused")

    def test_gate_scans_every_text_extension_not_just_markdown(self):
        """A gate that quietly skips a file type is the 17-hit bug wearing a different hat:
        the tree looks CLEAN because nothing ever read the file. Every extension in
        text_ext must be scanned, so this checks a .py, a .json and a .yml."""
        tmp = tempfile.mkdtemp()
        try:
            for name in ("leak.py", "leak.json", "leak.yml", "leak.md"):
                with io.open(os.path.join(tmp, name), "w", encoding="utf-8") as fh:
                    fh.write('host = "WKSTN-4711"\n')
                out = io.StringIO()
                self.assertEqual(1, gate_mod.scan(tmp, load(), out=out), name)
                self.assertIn(name, out.getvalue())
                os.remove(os.path.join(tmp, name))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_a_wrong_path_is_never_reported_as_clean(self):
        """The worst defect this tool can have: a gate that did not look, reporting a
        green light. "I found no problems" and "I did not look" must not share an exit
        code. Both a missing directory and a scan that read zero files fail."""
        empty = tempfile.mkdtemp()
        try:
            out = io.StringIO()
            self.assertEqual(1, gate_mod.scan(os.path.join(empty, "typo"), load(), out=out))
            self.assertIn("REFUSING", out.getvalue())
            self.assertNotIn("CLEAN", out.getvalue())

            out = io.StringIO()
            self.assertEqual(1, gate_mod.scan(empty, load(), out=out))
            self.assertIn("REFUSING", out.getvalue())
        finally:
            shutil.rmtree(empty, ignore_errors=True)

    def test_soft_tier_never_fails_the_build(self):
        """A tier that cries wolf on every run is a tier people bypass. The soft tier is
        for a human to read, so it must not change the exit code."""
        tmp = tempfile.mkdtemp()
        try:
            with io.open(os.path.join(tmp, "note.md"), "w", encoding="utf-8") as fh:
                # Soft-tier material only: a private IP, a tailnet host, an unknown handle.
                # Each is legitimate somewhere, which is exactly why it may not fail a build.
                fh.write("host 10.0.0.10, box-7.ts.net, ping @some_reader\n")
            self.assertEqual(0, gate_mod.scan(tmp, load(), paranoid=True, out=io.StringIO()))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestTreeWalk(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _src(self, files):
        src = os.path.join(self.tmp, "src")
        for rel, body in files.items():
            p = os.path.join(src, rel.replace("/", os.sep))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with io.open(p, "w", encoding="utf-8") as fh:
                fh.write(body)
        return src

    def test_two_files_sharing_a_basename_both_survive(self):
        """GOTCHA #8. The report used to be keyed by BASENAME. Five different
        build_dashboard.py overwrote each other in it - and then the stale check, reading
        that same dict, declared the survivors' twins abandoned and --prune deleted a live
        file. The key is the destination PATH."""
        src = self._src({"a/build.py": "X = 1\n", "b/build.py": "X = 2\n"})
        dst = os.path.join(self.tmp, "dst")
        code, data = san.publish(src, dst, load(), apply=True)
        self.assertEqual(0, code)
        self.assertEqual(["a/build.py", "b/build.py"], data["published"])
        self.assertEqual("X = 1\n", io.open(os.path.join(dst, "a", "build.py")).read())
        self.assertEqual("X = 2\n", io.open(os.path.join(dst, "b", "build.py")).read())

    def test_prune_refuses_a_mass_delete(self):
        """GOTCHA #9. A mistyped --src makes EVERY published file look stale. Pruning then
        wipes the repo, prints nothing alarming and exits 0. Deleting most of what you
        publish is never a routine outcome, so it needs a human, not a flag."""
        src = self._src({"keep.md": "hello\n"})
        dst = os.path.join(self.tmp, "dst")
        san.publish(src, dst, load(), apply=True)
        for name in ("old1.md", "old2.md", "old3.md"):
            with io.open(os.path.join(dst, name), "w", encoding="utf-8") as fh:
                fh.write("stale\n")
        code, data = san.publish(src, dst, load(), apply=True, prune=True)
        self.assertEqual(1, code, "stale files must fail the run, not just warn")
        self.assertEqual(3, len(data["stale"]))
        self.assertTrue(os.path.exists(os.path.join(dst, "old1.md")), "must NOT be deleted")

    def test_prune_deletes_a_small_number(self):
        src = self._src(dict(("f%d.md" % i, "x\n") for i in range(10)))
        dst = os.path.join(self.tmp, "dst")
        san.publish(src, dst, load(), apply=True)
        with io.open(os.path.join(dst, "dropped.md"), "w", encoding="utf-8") as fh:
            fh.write("stale\n")
        code, data = san.publish(src, dst, load(), apply=True, prune=True)
        self.assertEqual(0, code)
        self.assertFalse(os.path.exists(os.path.join(dst, "dropped.md")))

    def test_denied_file_is_never_written(self):
        src = self._src({"engines/investor_roster.py": "TARGETS = []\n"})
        dst = os.path.join(self.tmp, "dst")
        code, data = san.publish(src, dst, load(), apply=True)
        self.assertIn("engines/investor_roster.py", data["denied"])
        self.assertFalse(os.path.exists(os.path.join(dst, "engines", "investor_roster.py")))

    def test_quarantined_file_is_never_written(self):
        """A file the dictionary could not clean must not reach dst at all - and the run
        must exit non-zero, or 'we printed a warning' becomes the whole defence."""
        src = self._src({"leak.md": "ghp_" + "a" * 36 + "\n"})
        dst = os.path.join(self.tmp, "dst")
        code, data = san.publish(src, dst, load(), apply=True)
        self.assertEqual(1, code)
        self.assertIn("leak.md", data["quarantined"])
        self.assertFalse(os.path.exists(os.path.join(dst, "leak.md")))

    def test_binary_is_skipped_loudly(self):
        """A silent skip is how a screenshot of a private dashboard ships."""
        src = self._src({"note.md": "hi\n"})
        with io.open(os.path.join(src, "shot.png"), "wb") as fh:
            fh.write(b"\x89PNG\r\n")
        code, _ = san.publish(src, os.path.join(self.tmp, "dst"), load(), apply=True)
        self.assertEqual(0, code)

    def test_empty_source_tree(self):
        src = os.path.join(self.tmp, "empty")
        os.makedirs(src)
        code, data = san.publish(src, os.path.join(self.tmp, "dst"), load(), apply=True)
        self.assertEqual(0, code)
        self.assertEqual([], data["published"])

    def test_a_missing_src_is_refused_not_reported_as_a_publish(self):
        """os.walk() on a path that does not exist yields nothing, so a typo used to print
        `passed the gate: 0` and `APPLIED`, and exit 0."""
        with self.assertRaises(ValueError):
            san.publish(os.path.join(self.tmp, "nosuch"),
                        os.path.join(self.tmp, "dst"), load(), apply=True)

    def test_unicode_filenames_and_nested_dirs(self):
        src = self._src({"заметки/日本語/файл.md": "Кирилл и кириллица\n"})
        dst = os.path.join(self.tmp, "dst")
        code, data = san.publish(src, dst, load(), apply=True)
        self.assertEqual(0, code)
        self.assertEqual(["заметки/日本語/файл.md"], data["published"])

    def test_output_is_always_lf(self):
        """CRLF written here reaches somebody else's clone as a file git refuses to apply
        patches to and diffs line-by-line forever."""
        src = self._src({"crlf.md": "one\r\ntwo\r\n"})
        dst = os.path.join(self.tmp, "dst")
        san.publish(src, dst, load(), apply=True)
        raw = io.open(os.path.join(dst, "crlf.md"), "rb").read()
        self.assertNotIn(b"\r\n", raw)

    def test_dry_run_writes_nothing(self):
        src = self._src({"a.md": "Dave Olsen\n"})
        dst = os.path.join(self.tmp, "dst")
        san.publish(src, dst, load())
        self.assertFalse(os.path.exists(dst))

    def test_whole_tree_publish_is_byte_identical_on_rerun(self):
        dst = os.path.join(self.tmp, "dst")
        san.publish(DEMO, dst, load(), apply=True, banner=True)
        first = self._hashes(dst)
        san.publish(DEMO, dst, load(), apply=True, banner=True)
        self.assertEqual(first, self._hashes(dst))

    @staticmethod
    def _hashes(root):
        out = {}
        for dp, _, fns in os.walk(root):
            for fn in fns:
                p = os.path.join(dp, fn)
                out[os.path.relpath(p, root)] = hashlib.sha256(
                    io.open(p, "rb").read()).hexdigest()
        return out


class TestRulesFile(unittest.TestCase):

    def test_bad_regex_fails_at_load_not_mid_run(self):
        """A broken rule used to blow up halfway through a tree, leaving a half-written
        output directory that looked like a successful publish."""
        with self.assertRaises(ValueError):
            rules_mod.Rules({"people": [["(unclosed", "x"]]})

    def test_unknown_pool_is_refused(self):
        with self.assertRaises(ValueError):
            rules_mod.Rules({"person_tokens": [["Smith", "middle"]]})

    def test_example_rules_load_and_every_pattern_compiles(self):
        r = load()
        self.assertTrue(r.gate, "the example must ship a hard tier")
        self.assertTrue(r.gate_soft, "the example must ship a soft tier")

    def test_literal_tables_are_sorted_longest_first(self):
        """Substitute `dave` before `daveolsen` and the long handle becomes `<fake>olsen`,
        which no later rule and no gate will recognise."""
        r = rules_mod.Rules({"slugs": {"ab": "X", "abcd": "Y", "abc": "Z"}})
        self.assertEqual(["abcd", "abc", "ab"], [k for k, _ in r.slugs])


if __name__ == "__main__":
    unittest.main(verbosity=2)
