# PROMPT.md — hand this to Claude Code or Codex

Copy everything below the line into an agent session opened **in the repository you want to
publish**. It will build your dictionary, run the pipeline, show you the diff, and refuse to
push until the gate is clean.

---

You are helping me open-source an internal repository without leaking private data. Use the
`oss-publish` pipeline: https://github.com/tonydzi/oss-publish

Work in this order and stop at every checkpoint marked **ASK ME**.

## 0. Get the tool

Clone `oss-publish` to a scratch directory outside this repo. It is Python 3, standard
library only — no install step. Verify it works before touching my code:

```
python -m unittest discover -s tests
```

41 tests must pass. If they do not, stop and tell me.

## 1. Learn my repo before writing any rule

Do not guess my dictionary. Derive candidates from the tree, then bring them to me.

Scan for and list, with file:line and a count of occurrences:

1. **Capitalised tokens that look like person names** — and be sceptical. When we did this
   on our own corpus, 89 candidates contained about 20 real people; the rest were `Agent`,
   `Bash`, `Money`, `Wolf`. Never assume a capitalised word is a human.
2. **Handles** — `@…`, and also bare slugs glued into env vars, lock files and paths
   (`SESSION_STRING_MYHANDLE`, `_refresh_myhandle.lock`, `/MyHandle`). Word boundaries will
   not find these; grep for the slug itself.
3. **Hostnames** — machine names in configs, log lines, comments, and as Python identifiers.
4. **Absolute paths** — check for BOTH `C:\Users\<me>` and `C:\\Users\\<me>`; a path inside a
   non-raw Python literal spells its separator with two characters.
5. **Numeric ids** — chat ids, user ids, group ids. Note which have meaningful prefixes.
6. **E-mails, phone numbers, private URLs** — invite links, chat links, meeting links.
7. **Credentials** — vendor-prefixed ones (`ghp_`, `sk-`, `AIza`), and also
   `token = <an ordinary-looking string>` with no prefix and an ordinary length. The second kind
   is invisible to every shape-based rule and has to be named by hand.
8. **Files whose PAYLOAD is other people's data** — contact rosters, lead lists, anything
   with repeated `("Name", id, "what they replied")` tuples.

**ASK ME** — show the candidate lists as a table and let me strike out the false positives
before anything is written. Ask specifically about #1 and #8.

## 2. Write my rules file

Start from `rules.example.json`. Fill in what I confirmed. Rules:

- Put the file **outside** the repo I am publishing, and tell me the path. It is a list of
  my private strings; it is the most sensitive file in the pipeline.
- Replacements must be **plausible fakes of the same shape**, never `<REDACTED>`. Same digit
  count, same id prefix, same script (a Cyrillic name gets a Cyrillic fake), same case.
- Check every short name against ordinary vocabulary and add a negative lookahead where it
  collides (`Кирилл(?!иц)`, `Mark(?!et)`).
- Remember JSON escaping: one regex backslash is written as two here, one literal path
  backslash as four. A mis-escaped rule compiles fine and silently never matches.
- Keep my **published** channels and my public author identity unsubstituted, and list them
  in `keep_handles`.
- Put anything from #8 into `deny_files` with a written reason.

## 3. Dry run and read the diff

```
python <path>/oss_publish/sanitize.py --rules <my-rules.json> \
       --src <this repo> --dst <a separate public checkout> --report
```

Dry run is the default; nothing is written. Read the report yourself first and flag:

- substitutions that broke a sentence or a code identifier;
- files that were **quarantined** (the dictionary could not clean them);
- files that were **skipped as binary** — images and PDFs are invisible to every rule, so
  list them for me by name;
- anything real that the diff did **not** touch.

**ASK ME** before the first `--apply`.

## 4. Apply, then gate the whole tree

```
python <path>/oss_publish/sanitize.py --rules <my-rules.json> --src <repo> --dst <public> --apply --banner
python <path>/oss_publish/gate.py    --rules <my-rules.json> <public> --paranoid
```

The gate must scan the **entire** public checkout, not the files that changed — including
the README, the LICENSE and anything hand-written that the sanitizer never generated. That
is precisely where leaks survive: nothing produced those files, so nothing substituted them.

Exit 1 means **do not publish**. Fix the dictionary and repeat; never override the gate.

Also read the soft tier out loud to me. It never fails the build, and it is where a session
string or a private endpoint shows up.

## 5. Prove it before you push

- Every published `.py` still compiles (`python -m py_compile`).
- A second full run is byte-for-byte identical (sha256 the tree twice) — if not, something
  is non-deterministic and the repo will churn on every publish.
- Read three published files end to end, as a stranger would. Do they still make sense?

**ASK ME** for explicit approval before `git push` or `gh repo create`. Never push on your
own initiative.

## 6. Tell me what you could not fix

Two things go in your final report, in plain words:

- Files you **denied** and why — a deliberate gap must be documented, never quiet.
- Any credential you substituted. **Substitution protects the next publish, not the last
  one.** If a live token was ever committed or published, it must be **rotated**, and only
  I can do that. Say so explicitly; do not let a renamed secret read as a fixed secret.
