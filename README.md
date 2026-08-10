# oss-publish

Open up your internal work without leaking it.

This is the pipeline we run before every public release: it **replaces** personal data with
plausible fakes of the same shape — it does not black it out — and then a fail-closed gate
re-scans the **entire** repo before the push.

Built and used daily at [Palo Alto AI Research Lab](https://github.com/tonydzi/Palo-Alto-AI-Research-Lab).
Every kit we ship went through exactly this: 101 skills, 246 engines, one gate.

Python 3, standard library only. No dependencies, no network, no telemetry.

---

## The idea in one diff

Your private source:

```markdown
Runs nightly on **WKSTN-4711**. Notes live in `D:\Vault\Team-Notes`.
Ops group `-1001732845096`, founder DM `418209934`.

- **Dave Olsen** (`@dave_ops`) — founder, gets the digest as a DM.
- **Кирилл** — contractor; his notes are in кириллица, do not transliterate.

Escalate to `dave.olsen@sunrise-capital.io` or `+441632960122`.
```

What ships:

```markdown
Runs nightly on **HUB-1**. Notes live in `%VAULT%`.
Ops group `-1009838258101`, founder DM `265977610`.

- **Omar Tanaka** (`@owner_acct`) — founder, gets the digest as a DM.
- **Тимур** — contractor; his notes are in кириллица, do not transliterate.

Escalate to `someone@example.com` or `+15550001111`.
```

Nothing is missing. The document still **works**: a supergroup id still looks like a
supergroup id, a path still looks like a path, the Cyrillic contractor still has a Cyrillic
name — and the word `кириллица` was left alone, because it is an alphabet, not a person.

That is the whole product. The rest of this README is why each of those details is there.

---

## 1. Substitute, do not redact

`<REDACTED>` is a hole. It teaches a reader nothing, breaks every example, and turns
documentation into a puzzle — so people quietly stop publishing, or publish with the holes
filled back in by hand, which is worse. A **plausible fake of the same shape** keeps the
docs working. The code still parses and still runs; it just talks to nothing until the
reader points it at their own accounts.

Substitution is **deterministic** (sha256-derived), so the same input always produces the
same fake — in every file, on every run, on every machine. Two consequences:

- Re-publishing is a no-op instead of a diff full of churn. *Proven, not asserted: a second
  full run over the demo tree is byte-for-byte identical, sha256 compared, in the test suite.*
- A reader can follow one fake person across twelve files and see a coherent system,
  instead of twelve unrelated strangers.

**Shape carries meaning.** A Telegram supergroup id starts with `100`; someone who knows
that can tell a group from a user at a glance. Destroy the shape and the example stops
teaching. So fakes preserve digit count, the `100` prefix, script (a Cyrillic name gets a
Cyrillic fake), and case (an uppercase env var stays uppercase).

**Kept on purpose:** your own published channels, your public author identity, vendor and
product names. A published channel is not personal data — faking ours once turned a
call-to-action into a pointer at an account that does not exist.

## 2. The gate runs over the WHOLE tree, every time

Not over the files you changed. Over the tree you are about to push.

> **The measurement that made this rule.** On 2026-07-28 we re-scanned a repo that had been
> public for weeks. **17 hits** in already-published files: colleagues' real names, a real
> hostname, absolute paths off a real drive. Some sat in a hand-maintained `INDEX.md` that
> the sanitizer never writes — so nothing had ever substituted it, and nothing ever would.

**"Already published" is not a synonym for "already checked."** Run the gate over the
finished checkout, as the last thing that happens before `git push`. Exit 1 means do not
publish.

**A gate hit does not mean "publish it with a warning."** The sanitizer checks every file
*before writing it*, and a file that trips the hard tier is **quarantined**: never written
to the public tree, named in the run output, and the run exits non-zero. So a value your
dictionary never knew about does not leak — it stops the publish. That is the difference
between a linter and a gate, and it is why the dictionary being incomplete is survivable
while the gate being incomplete is not.

Two tiers, deliberately:

- **Hard** — a hit fails the build. Catches shapes somebody already thought of.
- **Soft** (`--paranoid`) — prints for a human, never fails. Private IPs, env vars named
  `TOKEN`, 200-character base64 blobs: usually innocent, occasionally an account takeover.
  A tier that cries wolf on every run is a tier people start bypassing.

The hard tier is *literally the same compiled rule list* the sanitizer checks each file
against. Two gates that disagree about one string is how a file gets held back by one,
waved through by the other, and shipped anyway.

## 3. Some files cannot be saved by substitution

The test is not "does this file mention someone" — almost every file in a working system
does. It is: **is third-party personal data the POINT of the file?**

A contact roster with names, funds, chat ids and verbatim quotes of what people replied has
nothing left once you fake it, and leaves other people's personal data in a public repo if
you don't. Those files are named in `deny_files` with a reason a human can read, and a
shape rule refuses *new* files of the same class without anyone remembering to add them.

**And a machine cannot pick that list for you.** We found the real names in our corpus by
intersecting capitalised tokens with the CRM's name columns. Of 89 candidates, about 20 were
people. The rest were `Agent`, `Bash`, `Money`, and `Wolf` — from HP Wolf Security. Curate
this list by hand. It is the one place worth spending a human minute.

## 4. Quickstart

```bash
git clone https://github.com/tonydzi/oss-publish.git
cd oss-publish
python -m unittest discover -s tests        # 41 tests, ~0.1s, stdlib only
```

Run the pipeline over the bundled demo (an invented company, safe to publish):

```bash
python oss_publish/sanitize.py --rules rules.example.json \
       --src examples/demo_repo --dst build/public --apply --banner --report
```

Then gate what you are about to push:

```bash
python oss_publish/gate.py --rules rules.example.json build/public --paranoid
```

Now do it for real:

1. Copy `rules.example.json` and fill in **your** names, handles, hosts, paths and ids.
   Keep that file **outside** the repo you publish — a substitution table is made *of* the
   private data it hides, which makes it the most sensitive file in the pipeline.
2. Dry-run without `--apply` and read the report until the diff is boring.
3. `--apply`, gate the whole tree, then push.

Dry run is the default. Nothing is written without `--apply`.

## 5. The lazy path

Open Claude Code (or Codex), paste [`PROMPT.md`](PROMPT.md), point it at your repo. It reads
your tree, drafts your dictionary, runs the dry run, shows you the diff, and refuses to push
until the gate is clean.

## 6. What this is NOT

It is not a secret scanner, and it will not save you from a credential that already shipped.

**Substitution protects the NEXT publish. It does nothing about the last one.** A live token
that reached a public repo must be **rotated**, not renamed — it is in the clone, the fork,
the mirror and somebody's scraper. Read [`docs/SECURITY.md`](docs/SECURITY.md) before you
decide a substituted secret is a fixed secret.

## Contents

| | |
|---|---|
| [`oss_publish/sanitize.py`](oss_publish/sanitize.py) | the substitution engine + tree walker |
| [`oss_publish/gate.py`](oss_publish/gate.py) | the whole-tree gate, hard + soft tiers |
| [`oss_publish/rules.py`](oss_publish/rules.py) | rule loading; values from JSON, **order from code** |
| [`rules.example.json`](rules.example.json) | a dictionary over an entirely invented cast |
| [`examples/demo_repo/`](examples/demo_repo/) | a private tree that exercises every hard case |
| [`docs/GOTCHAS.md`](docs/GOTCHAS.md) | ten traps, each one paid for |
| [`docs/SECURITY.md`](docs/SECURITY.md) | the honest boundary |
| [`tests/test_pipeline.py`](tests/test_pipeline.py) | one test per bug that shipped once |

## Sibling kits

- [telegram-mcp-kit](https://github.com/tonydzi/telegram-mcp-kit) — connect Claude to your Telegram in ~15 minutes
- [whatsapp-mcp-kit](https://github.com/tonydzi/whatsapp-mcp-kit) — the WhatsApp pairing procedure that actually works

## License

MIT. Take it, fork it, ship your own internals.
