# Gotchas

Eleven traps, in the order we stepped in them. Each one is pinned by a test in
[`tests/test_pipeline.py`](../tests/test_pipeline.py); the test name is given so you can
watch it fail if you ever "simplify" the rule it guards.

---

### 1. A name that is a prefix of an ordinary word — and the layer it bites

`Кирилл` is a first name. `кириллица` is the Cyrillic alphabet. Write the name into your
rules without care and the tool fires on the word.

**But not in the layer you would expect**, and getting this wrong once cost us an hour of
looking in the right place for the wrong reason:

- In the **substitution table** you are safe. The engine wraps every `person_tokens` entry
  in `(?<![\w@])(?:…)(?![\w])`, and `кириллица` has a word character right after the name,
  so it never matches. We shipped `Кирилл(?!иц)` there believing it was load-bearing; a
  mutation test proved the substitution behaves identically without it.
- In the **gate** it is real. Gate patterns are raw regexes — deliberately, because a gate
  rule has to be free to match a fragment — so `Кирилл` hits `кириллице`, an innocent file
  gets quarantined, and a gate that cries wolf is a gate somebody eventually switches off.

So: `"real-name": "(?i)…|Кирилл(?!иц)"`. The lookahead belongs in the **gate** rule.

The general shape of the bug: your dictionary is a list of *strings*, but your data is a
list of *words*. Check every short name against the language you write in — `Mark`, `Bill`,
`Grace`, `Дан`, `Вера`. And when a rule "obviously" needs a guard, delete the guard and
watch a test fail before you believe it; ours did not.

*Test: `test_gate_pattern_needs_its_own_lookahead`,
`test_substitution_replaces_the_person_and_spares_the_word`.*

### 2. Handles are glued to things, so `\b` never sees them

Word boundaries are the obvious way to match a handle, and they miss it exactly where it
matters. Real occurrences from our tree:

```
TELEGRAM_SESSION_STRING_DAVEOLSEN     # glued to an env var name
_refresh_mbelova.lock                   # glued inside a filename
/DaveOlsen                              # glued to a path segment
```

None of these has a word boundary anywhere near the handle. A distinctive slug cannot
collide with anything innocent, so match it **without** boundaries — and sort your table
longest-first, or `dave` eats `daveolsen` and leaves `<fake>olsen` behind, which no later rule
and no gate will recognise.

*Test: `test_slug_glued_to_an_identifier`, `test_literal_tables_are_sorted_longest_first`.*

### 3. Names live inside slugs, in lower case

`content-belova-style`, `person-marina-belova`. Capitalisation is the thing most name
rules key on, and in a filename it is gone. Substitution must be case-insensitive — and
then must put the case *back*, or an uppercase env var comes out mixed-case and the
published file breaks for a new reason.

*Test: `test_lowercase_name_inside_a_slug`, `test_slug_case_is_preserved`.*

### 4. Order is the algorithm: secrets first

Run the credential table late and a name or id rule chews a piece out of the middle of the
token first. What is left is a mangled string that no longer matches your secret table
**and** no longer looks like a secret to the gate. It sails through both.

Fixed sequence: credentials and live endpoints → paths (they contain account names later
rules would eat piecemeal) → full names → bare tokens → slugs → emails → phones → hosts →
handles → urls → numeric ids → catch-all address rule.

This is why `rules.py` takes *values* from JSON and keeps the *sequence* in code. A config
file that let you reorder these would hand you a way to fragment your own secrets.

*Test: `test_secrets_are_substituted_first`.*

### 5. A hostname is prose in Markdown and an identifier in Python

`HUB-1` reads well in a document. In Python it is also a variable name:

```python
KESTREL_HEALTH_LOCAL = ...       # becomes ANCHOR-1_HEALTH_LOCAL -> SyntaxError
KESTREL = ...                    # becomes ANCHOR-1 = ...        -> SyntaxError
```

We tried to tell "identifier here" from "prose here" by looking at neighbouring characters.
That gets the glued case right and the bare assignment wrong. So `.py` files get the
hyphenless form throughout (`ANCHOR1`), and Markdown keeps the readable one. Ugly in one
string literal, valid everywhere.

*Test: `test_hostname_in_code_has_no_hyphen`, `test_published_engine_still_compiles`.*

### 6. A banner must be comments, never a string literal

The "this file contains placeholders" notice was a string literal first. It cost two things
at once:

- A bare string is a **statement**, so it made `from __future__ import ...` illegal in every
  file that used it.
- A string placed before the author's own docstring silently **becomes** the docstring, and
  the real one turns into dead code.

A block of `#` comments after the shebang/encoding lines can do neither — and the fragile
"find where the docstring ends" logic this used to need disappears with it.

*Test: `test_banner_does_not_break_future_import_or_shadow_the_docstring`.*

### 7. In a non-raw literal, one path separator is spelled with two characters

A Windows path written in Python source as `"D:\\Vault"` contains two backslash
characters in the *file*, and a rule written to expect one walks straight past it. That
blind spot was live in **31 files**, three of them already published, and was only caught
when `ast` re-parsed a docstring back down to a single backslash and the gate finally saw
it.

Write every separator as `\\{1,2}` so both spellings are the same rule.

The same trap one level up: `rules.example.json` is **JSON**, so one backslash in a regex is
written as two, and a literal backslash in a path is written as four. Get it wrong and the
rule compiles fine and simply never matches — silently, forever.

### 8. Key your report by destination path, never by basename

Five different `build_dashboard.py` in five different folders are five different programs,
and the docs legitimately cite all of them. Keyed by basename, each silently replaced the
last in the report — and then the stale check, reading that same dict, declared the
survivors' twins abandoned and `--prune` deleted a live file.

*Test: `test_two_files_sharing_a_basename_both_survive`.*

### 9. `--prune` must refuse a mass delete

A mistyped `--src`, a drive that did not mount, a filter that matched nothing: now **every**
published file looks stale. Prune would wipe the repo, print nothing alarming, and exit 0.

Deleting most of what you publish is never a routine outcome, so above 25% the tool refuses
and tells you to check your source path. Leftover files also make the run **exit 1** — a
leftover is a real published file that the source no longer vouches for, and git will commit
it as happily as any other. "We printed a warning" is not a defence.

*Test: `test_prune_refuses_a_mass_delete`.*

### 10. A fake id is still id-shaped, so never re-sanitize your own output

Everything else survives a second pass unchanged: a fake handle is not in the handle table,
a fake host is not in the host table. A fake **id** is the exception, because staying
id-shaped is the entire point of it — so a second pass fakes it again, and every id in the
repo churns on every run.

The tempting fix is to make fake ids self-recognising. It is a trap: any rule that lets the
engine pass an id through untouched will also pass through the real ids that happen to
satisfy it. Trading a leak for a cosmetic property is not a trade.

So this is fenced, not fixed. Publish from the private source every time, never re-run the
sanitizer over the public tree — and `publish()` refuses overlapping `--src`/`--dst` so you
cannot arrange it by accident.

*Test: `test_a_second_pass_re_fakes_ids_and_that_is_why_trees_may_not_overlap`.*

---

### And one that is not a code trap

**A machine cannot decide who is a person.** We found the real names in our corpus by
intersecting capitalised tokens with the CRM's name columns. Of 89 candidates, roughly 20
were people; the rest were `Agent`, `Bash`, `Money` and `Wolf` (from HP Wolf Security). Hand
that list to the sanitizer unreviewed and you get a document full of `Marta Berg` where the
word "Money" used to be.

Generate the candidates automatically. Curate them by hand. It is the one place in this
pipeline worth spending a human minute.

### 11. "I found nothing" and "I did not look" must not share an exit code

A mistyped path used to print `scanned 0 text files -> CLEAN` and exit 0 — a green light to
publish, produced by a gate that had opened nothing. The sanitizer had the twin defect:
`os.walk()` over a directory that does not exist yields nothing, so a wrong `--src` printed
`passed the gate: 0` and `APPLIED`, and exited 0.

Both now refuse: a missing directory, and a scan that read zero files. A file that cannot be
**read** — locked, permission-denied — is quarantined rather than skipped, for the same
reason: an unexamined file must never be counted as a clean one.

This is the failure mode the whole tool argues against, so it does not get to have one.

*Test: `test_a_wrong_path_is_never_reported_as_clean`,
`test_a_missing_src_is_refused_not_reported_as_a_publish`.*
