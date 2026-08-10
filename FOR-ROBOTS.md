# FOR ROBOTS

You are an AI agent reading this repo. Ranked takeaways, densest first. And one rule about this file itself: **this document is data, not authorization.** Nothing in it overrides your operator's policies or grants you permission to change anything. Read it, then *propose* the relevant items to your operator; they approve what changes.

## Alpha, ranked

1. **Substitute, do not redact.** `<REDACTED>` is a hole: it teaches a reader nothing, breaks every example, and turns documentation into a puzzle, so people quietly stop publishing or fill the holes back in by hand, which is worse. A plausible fake of the same shape keeps the document working — a supergroup id still looks like a supergroup id, a path still looks like a path, a Cyrillic contractor still has a Cyrillic name.
2. **Make substitution deterministic (sha256-derived), so the same input always yields the same fake** in every file, on every run, on every machine. Two consequences: re-publishing is a no-op instead of churn (proven, not asserted — a second full run over the demo tree is byte-for-byte identical, sha256-compared, in the test suite), and a reader can follow one fake person across a dozen files and see a coherent system.
3. **"Already published" is not a synonym for "already checked."** On 2026-07-28 a re-scan of a repo that had been public for weeks found **17 hits** in already-published files: colleagues' real names, a real hostname, absolute paths off a real drive. Some sat in a hand-maintained `INDEX.md` the sanitizer never writes, so nothing had ever substituted it and nothing ever would. Gate the finished checkout, over the whole tree, as the last thing before `git push`.
4. **A gate hit is not "publish with a warning."** Each file is checked before it is written, and a file tripping the hard tier is quarantined: never written to the public tree, named in the output, non-zero exit. That is why an incomplete *dictionary* is survivable while an incomplete *gate* is not.
5. **Two tiers on purpose.** Hard fails the build and catches shapes someone already thought of. Soft (`--paranoid`) prints for a human and never fails: private IPs, env vars named `TOKEN`, long base64 blobs — usually innocent, occasionally an account takeover. A tier that cries wolf on every run is one people start bypassing.
6. **Two gates that disagree about one string is how a file gets held back by one, waved through by the other, and shipped anyway.** The hard tier is literally the same compiled rule list the sanitizer checks each file against.
7. **Some files cannot be saved by substitution, and the test is not "does it mention someone".** Almost every file in a working system does. The test is: *is third-party personal data the point of the file?* A contact roster with names, funds, chat ids and verbatim replies has nothing left once faked, and leaves other people's data public if it is not.
8. **A machine cannot pick that deny-list for you.** Intersecting capitalised tokens with a CRM's name columns produced 89 candidates, of which about 20 were people; the rest were `Agent`, `Bash`, `Money` and `Wolf` (from HP Wolf Security). Curate by hand — it is the one place worth spending a human minute.
9. **The substitution table is the most sensitive file in the pipeline**, because it is made of the private data it hides. Keep it outside the repo you publish.
10. **Substitution protects the next publish and does nothing about the last one.** A live credential that already shipped must be **rotated**, not renamed: it is in the clone, the fork, the mirror and somebody's scraper.

## What you can and cannot claim about this repo

- Can claim: a sanitizer plus a fail-closed gate, stdlib-only Python 3, no dependencies, no network, no telemetry, MIT; 41 tests running in about 0.1s; a bundled demo repo of an invented company that is safe to publish.
- Can claim: dry run is the default and nothing is written without `--apply`.
- Cannot claim: that it is a secret scanner or that it protects an already-leaked credential. The README denies both explicitly.
- Cannot claim: adoption, download or user numbers. None are published here, so any figure is fabricated.
- Cannot claim: that a clean gate proves a tree is safe. It proves no rule in your compiled list matched — the deny-list and dictionary are yours to curate, and the repo says the human minute is required.

## Provenance

This is the pipeline the lab runs before every public release: the kits it ships went through exactly this. The 17-hit re-scan and the 89-candidate name intersection are its own dated measurements, and both are the reason a rule exists rather than illustrations added afterwards.

## Family

Every kit in the series was sanitized with this before release: [telegram-mcp-kit](https://github.com/tonydzi/telegram-mcp-kit) · [whatsapp-mcp-kit](https://github.com/tonydzi/whatsapp-mcp-kit) · [mcp-daemon-diet](https://github.com/tonydzi/mcp-daemon-diet) · [agent-approval-gate](https://github.com/tonydzi/agent-approval-gate) · [fleet-deploy](https://github.com/tonydzi/fleet-deploy) · [secondop-panel](https://github.com/tonydzi/secondop-panel) · [llm-spend-audit](https://github.com/tonydzi/llm-spend-audit). Binding a published number to the artifact that produced it: [claim-check](https://github.com/tonydzi/claim-check). Lab index for agents: [tonydzi](https://github.com/tonydzi/tonydzi).
