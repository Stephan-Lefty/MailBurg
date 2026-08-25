[Deutsch](README.md) | [English](README.en.md) | [Changelog](CHANGELOG.md) | [TODO](TODO.en.md) | [Legal](RECHTLICHES.md)

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/banner-dark-1600.png">
    <img src="assets/banner-1600.png" alt="MailBurg – E-Mails. Sicher bewahrt." width="620">
  </picture>
</p>

# MailBurg

An email archive that lives where *you* decide.

MailBurg collects mail from any number of accounts, stores it in one place and
makes it searchable — message bodies, headers and the contents of attachments.
Where that place is, is up to you: internal disk, external disk, a folder
synchronised by Nextcloud.

Runs on Linux, Windows and macOS.

## Why

Good tools exist for this, but they have limits: Windows only, a cap on the
number of accounts, or an archive format you cannot get your mail out of
without the program itself.

MailBurg does the opposite:

- **No limit on accounts.** Thirty addresses is the design target; more is fine.
- **Your archive, an open format.** Every message is a plain `.eml` file. You
  can reach any of them without MailBurg.
- **The search index is disposable.** It can be rebuilt from the archive at any
  time, so it never needs backing up.

## Status

**Early.** The foundation is in place and tested; the graphical interface and
IMAP retrieval are still missing. What works today works from the command line.
See [TODO.en.md](TODO.en.md).

## How it works

An archive is a directory:

```
MyArchive/
├── archive.json     identity, operating mode, retention policy
├── mail/            the messages, by month
│   └── 2026/08/3f/3f8a9c1e….eml.zst
└── meta/            the journal with its hash chain
```

Each message is named after the SHA-256 of its content. Two consequences:
importing the same source twice creates no second copy, and a corrupted file
announces itself on read.

Messages are stored **byte for byte** as received — no normalised line endings,
no repaired headers. That is what keeps a DKIM signature verifiable.

### Two operating modes

**Private archive.** No retention periods, no overhead, delete whenever you
like. This matches the law: someone archiving only their own mail falls under
the GDPR household exemption and is not subject to the regulation at all.

**Business archive.** Every operation enters a hash chain — each entry carries
the hash of its predecessor, so tampering visibly breaks the chain. Deletion
works through tombstones: the content goes, the record of its removal stays.
That satisfies the right to erasure and immutability at the same time.
Retention periods for Germany, Austria and Switzerland guard against deleting
too early.

> **Important:** MailBurg *supports* audit-proof operation, it does not
> *establish* it. That also requires process documentation and organisational
> discipline. No software alone can deliver this. See
> [RECHTLICHES.md](RECHTLICHES.md) (German).

### Searching

The query language is German and runs over two indexes:

```
rechnung                    anywhere in body, subject or attachment
von:müller rechnung         both must match
betreff:"offene posten"     quote multi-word phrases
hat:anhang typ:pdf jahr:2025
konto:firma ordner:Gesendet
-werbung                    excludes matches
```

`betreff:rechnung` also finds **Schluss**rechnung. In German that is not a
special case but the norm — we run words together. Hence a second index over
character trigrams alongside the word index. And `von:muller` finds "Müller"
too, for when the umlaut is hard to type.

## Getting started

Requires Python 3.11 or newer. The core needs no further packages.

```bash
git clone https://github.com/Stephan-Lefty/MailBurg.git
cd MailBurg

python3 -m mailburg anlegen ~/Archive --modus privat
python3 -m mailburg importieren ~/Archive ~/.thunderbird/xxxx.default --konto private
python3 -m mailburg suchen ~/Archive betreff:rechnung jahr:2025
python3 -m mailburg info ~/Archive
python3 -m mailburg pruefen ~/Archive
```

Sources can be a Thunderbird profile, a Maildir directory or a single MBOX
file. Thunderbird profiles are imported with all accounts and their nested
folder structure.

## On Nextcloud

An archive inside a synchronised folder works because the storage layout is
built for it: one file per message, and old month folders never change again —
so they sync exactly once.

The **search index deliberately lives outside the archive**, in the local
application directory. SQLite on a synchronised drive will eventually corrupt;
that is the most common way people destroy an archive. Nothing is lost when it
does — `neuaufbau` recreates the index in minutes.

While one machine has the archive open, a lock file sits inside it. Two
machines writing at once would otherwise produce a sync conflict nobody can
resolve.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## Licence

MIT — see [LICENSE](LICENSE).
