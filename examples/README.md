# The demo tree

`demo_repo/` is a small private repository belonging to an entirely invented company —
Sunrise Capital, run by Dave Olsen, with a teammate, an advisor, a contractor and three
machines. Every name, handle, host, address and number in it is fiction. The **shapes** are
real, because shape is what this pipeline is about.

It exists so you can run the whole thing in ten seconds and watch what happens, and so the
test suite has something to bite on.

## Run it

```bash
# from the repo root
python oss_publish/sanitize.py --rules rules.example.json \
       --src examples/demo_repo --dst build/public --apply --banner --report
python oss_publish/gate.py --rules rules.example.json build/public --paranoid
```

Then diff a file against its source and read what changed.

## What each file is there to prove

| file | the hard case it carries |
|---|---|
| `skills/daily-digest/SKILL.md` | prose substitution: names, handles, hosts, paths, ids, money, invite and meeting links — and the word `кириллица`, which must survive while `Кирилл` does not |
| `engines/digest.py` | every code-specific trap at once: shebang + coding line, `from __future__`, a real docstring, a hostname used as an identifier, a path in a non-raw literal, a handle glued into an env var and a lock filename, and a credential with no vendor prefix |
| `engines/investor_roster.py` | the class of file that substitution cannot save — refused by `deny_files`, by name, with a reason |

## Things worth noticing in the output

- `Кирилл` becomes a Cyrillic first name; `кириллица` is untouched. One negative lookahead
  is the whole difference ([GOTCHAS #1](../docs/GOTCHAS.md)).
- `KESTREL_HEALTH_LOCAL` becomes `LAPTOP1_HEALTH_LOCAL` — no hyphen, because it is an
  identifier — while the Markdown keeps the readable `LAPTOP-1`.
- `kestrel-health.json` becomes `laptop1-health.json`, lower case preserved.
- The chat id keeps its `-100…` supergroup shape and its digit count.
- The phone becomes a reserved `+1555…` test number and is **not** re-faked by the numeric
  id rule afterwards.
- `@acme_lab` survives untouched: it is the company's published channel, not personal data.
- `investor_roster.py` never reaches the output at all, and the run says why.

## Try breaking it

The fastest way to trust a gate is to watch it fire.

```bash
# 1. put something real into the "public" tree by hand, the way a README gets written
echo "ops box is WKSTN-4711, ping @dave_ops" > build/public/NOTES.md
python oss_publish/gate.py --rules rules.example.json build/public   # exit 1, two hits

# 2. now the point of the whole-tree rule: that file was never generated,
#    so no sanitizer would ever have touched it
```

Do the same with a fake `ghp_` token, a database URL with an inline password, or four rows of
`("Name", 400000001, "replied")` tuples, and watch which tier catches each one.
