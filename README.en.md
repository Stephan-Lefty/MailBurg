[Deutsch](README.md) | [English](README.en.md) | [Changelog](CHANGELOG.md) | [TODO](TODO.en.md) | [Guides](docs/README.md) | [Legal](RECHTLICHES.md)

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

**Linux and Windows.** Developed and used daily on Linux; on Windows there is
a ready-made `MailBurg.exe` — no Python, no installation, with text
recognition built in, and setup, retrieval, search and scheduled background
retrieval have all been exercised there.

**macOS is not there yet.** The test suite and the setup demonstrably pass,
but nobody has actually used MailBurg on macOS. For an archiving program that
is too little to recommend it: what goes wrong during capture only surfaces
years later. macOS is therefore planned for version 1.1, with a machine to
verify it on.

<p align="center">
  <img src="assets/uebersicht-2000.png" alt="Overview: mailboxes, mail clients and the Proton bridge are only ever read; MailBurg stores every message byte for byte in an archive whose location you choose, with a journal and hash chain. The search index lives outside the archive and can be rebuilt at any time. Access via the interface or the command line." width="960">
</p>

<sub>Die Grafik ist auf Deutsch – wie die Oberfläche und die Suchsprache.</sub>

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
- **Encryption for mail that leaves the house.** Optional at creation time:
  messages and journal are then written encrypted, file names masked. Plus a
  recovery key to print — an archive outlasts decades, a passphrase in your
  head does not.

## Status

**Version 1.0.1, in daily use.** Archive format, IMAP retrieval, search, the
graphical interface, text recognition for scanned PDFs, backups and scheduled
retrieval are all in place and used every day — on Linux with a corpus of more
than 16,000 messages, on Windows with the ready-made `MailBurg.exe`.

OAuth2 is implemented, but only tested against a mock provider: nobody has yet
signed in with a real Microsoft or Google account. For those, an app password
remains the safer choice for now.

Encrypted archives have been available since 2026-08-31 — built and tested,
but not yet exercised in daily use. See
[docs/verschluesselung.md](docs/verschluesselung.md) (German).

Still missing: Outlook `.pst`, ready-made packages (`.deb`, AppImage, `.dmg`),
RFC 3161 timestamps and verified operation on macOS. Full list in
[TODO.en.md](TODO.en.md).

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

When a matter went back and forth, MailBurg shows the **whole conversation**
for any message in it — held together by the headers every mail client carries,
not by the subject. Subjects change along the way, and two messages with
"Invoice" in the subject usually have nothing to do with each other.

## Getting started

Requires Python 3.11 or newer. The core needs no further packages.

```bash
git clone https://github.com/Stephan-Lefty/MailBurg.git
cd MailBurg
./install.sh
```

This sets MailBurg up inside your home directory — no administrator rights, no
changes to the system — and creates the `mailburg` command. On Windows,
`.\install.ps1` does the same; see [docs/windows.md](docs/windows.md).
`./install.sh --entfernen` removes it again, leaving the archive untouched.

If you would rather decide where things go, use `pip install ".[alles]"` — or
skip installing altogether and run `python3 -m mailburg` from the source
directory.

Note that the command names are German throughout: `anlegen` (create),
`importieren` (import), `abrufen` (fetch), `suchen` (search), `pruefen`
(verify), `konten` (accounts).

```bash
mailburg anlegen ~/Archive --modus privat
mailburg importieren ~/Archive ~/.thunderbird/xxxx.default --konto private
mailburg suchen ~/Archive betreff:rechnung jahr:2025
mailburg info ~/Archive
mailburg pruefen ~/Archive
```

Sources can be a Thunderbird profile, a Maildir directory or a single MBOX
file. Thunderbird profiles are imported with all accounts and their nested
folder structure.

## Fetching from mailboxes

For ongoing archiving, MailBurg collects mail straight from the mailbox:

```bash
# Set up a mailbox — the password is prompted for, never passed as an argument
mailburg konten hinzufuegen Firma \
    --server imap.example.org --benutzer post@example.org

# See what is configured and which folders would be archived
mailburg konten liste
mailburg konten pruefen Firma

# Fetch — everything the first time, only what is new afterwards
mailburg abrufen ~/Archive
mailburg abrufen ~/Archive --konto Firma
```

This is meant for scheduling: `mailburg abrufen ~/Archive` in a nightly cron job
is all it takes.

**Your mailbox stays untouched.** Every folder is opened read-only and messages
are fetched with `BODY.PEEK[]`. Unread mail is still unread afterwards — an
archiver that gets this wrong is worse than useless.

**Passwords live in the operating system's keyring**, never in a configuration
file. This needs the `keyring` package; without it everything still runs, the
password is simply asked for on every fetch. It is not written to the account
list either way.

Gmail, GMX, Web.de and Outlook do not accept your web password for outside
access — they require an app-specific password. OAuth2 sign-in exists as well
by now, but has only been tested against a mock provider — see
[docs/oauth2.md](docs/oauth2.md) (German).

**What is skipped:** trash, spam and drafts. The user already sorted that mail
out once; pulling it into the archive would undo that decision. On Gmail, "All
Mail" is skipped as well — it contains every message a second time.

**Only what is new.** How MailBurg knows where it left off is the genuinely
delicate part: the high-water mark is not written down, it is read back out of
the archive itself. If a fetch is interrupted mid-folder, the next one picks up
exactly the remainder. And a single message MailBurg choked on is flagged and
requested again next time — otherwise it would be missing forever, with nobody
any the wiser.

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
