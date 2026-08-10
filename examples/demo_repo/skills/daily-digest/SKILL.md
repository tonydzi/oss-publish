---
name: daily-digest
description: Collect yesterday's team chatter and post one digest to the ops channel.
---

# daily-digest

Runs nightly on **WKSTN-4711** (the always-on box). If that machine is down, **NB-KESTREL**
picks it up; the little **RASPI-ATTIC** node only holds the schedule, never the data.

## Inputs

| what | where |
|---|---|
| notes vault | `D:\Vault\Team-Notes` |
| scratch imports | `D:\Vault\_imports` |
| ops group | `-1001732845096` (supergroup) |
| founder DM | `418209934` |

## Who is who

- **Dave Olsen** (`@dave_ops`) — founder, gets the digest as a DM.
- **Marina Belova** (`@m_belova`) — runs the ops channel, decides what gets posted.
- **Harold Pike** (`@h_pike`) — advisor, mentioned only when a deal line moves.
- **Кирилл** — contractor who wrote the parser; his notes are in кириллица, so the
  transliteration step must not touch them.

Escalation goes to `dave.olsen@sunrise-capital.io`, or `+441632960122` if it is on fire.
Weekly review call: https://meet.google.com/kpz-mfsn-qxv

## Outputs

Posted to `@sunrisecap` (the corp channel) and mirrored to `@acme_lab`, which is our
published channel and stays exactly as written.

New joiners get the invite: https://t.me/+Xp7QmrLd91ka

## Thresholds

Flag a deal line if it moves by more than $25K in a day. Below that, it goes in the
weekly roll-up instead.

Config lives next to the engine, see `engines/digest.py`.
