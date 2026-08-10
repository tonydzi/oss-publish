# Security — the honest boundary

Read this before you decide a substituted secret is a fixed secret.

## Substitution protects the NEXT publish. It does nothing about the last one.

This is the single most important sentence in the repo.

If a live credential has already reached a public repository, replacing it in your working
copy changes nothing about the leak. The value is in the clone somebody made, in the fork,
in the mirror, in the GitHub API's event feed, in whatever scraper watches new commits for
exactly this — and in your own git history, which a substitution commit does not rewrite.

**A leaked credential must be rotated.** Renaming it is theatre.

The tool reflects that. When you add a value to `secret_literals` you are recording that a
credential was in your source; the substitution keeps it out of the next push, and the
rotation is a separate job that only you can do. Do both. If you only have time for one,
rotate.

## What this pipeline actually guarantees

It hides:

- what you told it to hide, in your dictionary;
- numeric ids above your configured length;
- e-mail addresses, including ones the dictionary never named (the catch-all rule);
- anything matching your gate's hard tier — by **refusing to publish that file at all**.

It does **not**:

- find secrets you never thought about (the soft tier only *asks a human to look*);
- understand context, sarcasm, or the fact that a sentence is quoting somebody;
- read binary files — images, PDFs, `.sqlite`, `.docx` are skipped and named in the run
  output. **A screenshot of a private dashboard is invisible to every rule here.** So are
  EXIF coordinates, PDF metadata and the strings inside a compiled binary;
- protect a file the dictionary was simply wrong about.

## The class of file no dictionary can save

Some files' *payload* is other people's personal data: a contact roster with names, funds,
ids and verbatim quotes of what they replied. Fake it and nothing useful is left; ship it
and you have published someone else's personal data, which in the EU is a GDPR matter and
everywhere else is still a betrayal of the person who wrote to you.

These belong in `deny_files` with a written reason, and the `people-roster` shape rule
refuses new ones. **Never quietly drop such a file** — name it in your handover notes, so
the next person knows the gap is deliberate rather than an oversight.

## Threat model, stated plainly

This tool defends against **you accidentally publishing your own private data**.

It does not defend against:

- **A determined re-identifier.** Fakes are consistent and shape-preserving, which is what
  makes the docs useful — and consistency is exactly what correlation attacks feed on. If
  `@teammate_m` appears in twelve files with a coherent role, timeline and writing style,
  a motivated reader who knows your team can guess who that is. Substitution is *hygiene*,
  not anonymity. If your threat model includes an adversary who wants to identify your
  colleagues, do not publish the corpus at all.
- **A hostile contributor.** Your rules file is a list of your private strings. Never commit
  it to the public repo. Pass `--rules` a path outside the tree you publish.
- **Git history.** The gate scans the working tree, not `.git`. If a secret was ever
  committed, scrubbing the current files is not enough — rewrite or, better, rotate.

## Practical checklist before a push

1. `--apply` from the private source into a **separate** public checkout (the tool refuses
   overlapping paths).
2. Run the gate over the **whole tree**, including files you did not touch and files added
   by hand — README, LICENSE, a hand-maintained index. Those are exactly where our 17 hits
   were, because nothing generated them and so nothing substituted them.
3. Run it once more with `--paranoid` and actually read the soft tier.
4. Look at the list of skipped binaries with your own eyes.
5. Rotate anything that appears in `secret_literals`.
6. `git push`.

## Reporting

Found a leak in something we published, or a hole in these rules? Open an issue, or reach
the lab through the contact block in the
[profile README](https://github.com/tonydzi/Palo-Alto-AI-Research-Lab). We would rather hear
it from you than from a scraper.
