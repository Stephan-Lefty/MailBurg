[Deutsch](TODO.md) | [English](TODO.en.md) | [Overview](README.en.md) | [Changelog](CHANGELOG.md) | [Guides](docs/README.md)

# TODO

A running list. Open items at the top. Finished items are not deleted but moved
down, with the date they were completed.

## Open

### Needed before real-world use

- [ ] **Text recognition for scanned PDFs.** The import now counts how many
  PDFs carry no text layer — those are documents somebody scanned, and they
  stay unfindable. Only OCR helps, via `ocrmypdf` or `tesseract`. Both are
  large foreign programs, so this stays optional and only runs where they are
  present. Open: whether it should run during archiving (slow) or later as a
  separate pass over existing holdings.

- [ ] **OAuth2 login.** Retrieval works with app passwords. That is enough, but
  it is not what Gmail and Outlook actually want — OAuth2 belongs there. At
  Google it involves an application review that takes time, so: later, and not
  a prerequisite for real-world use.

- [ ] **Graphical interface with PySide6.** Three panes: account tree, results,
  preview. Search bar with results as you type. Archive creation wizard.
  **PySide6, not PyQt6** — PyQt6 is GPLv3 and would override the MIT licence
  once binaries are distributed. The API is near-identical.

- [ ] **The route back into the mail client.** Three ways, because different
  situations need different ones: "open in mail program" via a temporary `.eml`
  and `xdg-open`/`start`/`open`; drag and drop from the result list into a
  Thunderbird window; "restore to…" via IMAP `APPEND` into a chosen folder.
  Plus opening attachments on double click.

- [ ] **Exclusion rules for private mail.** Exclude folders, senders or subject
  patterns from archiving. The most important data-protection building block in
  practice: where a company account may also be used privately, private
  messages must not simply be archived along with the rest.

### Afterwards

- [ ] **Serve the archive as an IMAP server.** Instead of a dedicated phone
  app: MailBurg offers its archive as a read-only IMAP account. Any mail
  program can then mount it — Thunderbird, Outlook, Apple Mail, K-9 Mail,
  FairEmail — on any device, without a line of app code and without the Play
  Console or App Store.

  It also solves the route back into the mail client by itself: replying to an
  archived message happens in the program you already use.

  **Security is the crux here.** An IMAP service exposed to the open internet
  is an attack surface in front of an archive holding decades of mail. The
  default must be: listen on `127.0.0.1` only, opt in explicitly for the local
  network, and point to VPN or Tailscale for remote access rather than a port
  forward.

- [ ] **Retention categories in the interface.** The arithmetic sits in
  `core/retention.py` and is tested, but there is no way yet to assign a
  category to a message. The `classify` journal operation is reserved. Open
  question: whether business letter and accounting document can be told apart
  automatically — probably only as a suggestion the user confirms.

- [ ] **Due-for-deletion report.** "These 342 messages have passed their
  retention period and should be deleted." Deletion only ever after explicit
  confirmation — a program that removes business records on its own initiative
  does more damage than any over-retention.

- [ ] **Subject access export (GDPR Art. 15).** Collect all mail concerning one
  person and export it as PDF or ZIP.

- [ ] **Generate process documentation.** MailBurg knows its own configuration
  and can pre-fill the technical part of a GoBD template. The organisational
  part is up to the user. The text must state unambiguously that responsibility
  rests with the taxpayer.

- [ ] **RFC 3161 timestamps.** Connect a TSA service to the seal operation. The
  field is reserved in the format. To settle: which service, what happens
  without an internet connection, and whether a free provider such as FreeTSA
  carries enough evidentiary weight.

- [ ] **Encryption, selectable per archive.** Key from the password via
  Argon2id, each file individually with AES-256-GCM. Filenames must then no
  longer be the plaintext hash but `HMAC(key, hash)` — otherwise the directory
  listing alone reveals which messages the archive holds. Archive creation must
  offer a printable recovery key with a blunt warning: without the password a
  long-term archive is gone for good.

- [ ] **Further mail sources.** Outlook PST/OST via `libpff`, Apple Mail
  `.emlx`.

- [ ] **Packages for all three systems.** `.deb` and AppImage for Linux,
  PyInstaller with Inno Setup for Windows, `.app` and `.dmg` for macOS. For
  macOS, decide how to handle Gatekeeper while unsigned.

### Open questions

- [ ] **How does the Nextcloud client behave during archiving?** The lock file
  prevents two machines writing at once. Unclear what happens if the client
  touches a file while MailBurg is writing it. To check: whether the
  write-beside-then-rename in `store.py` already covers this.

- [ ] **How fast is search at half a million messages, really?** Measured on
  2026-08-25 against 5,187 real messages (1.2 GB from a Thunderbird profile):
  **9 to 13 ms** per query, across free text, field search and attachment type.
  The index takes 95 MB, 12 % of the archive — the fear that the trigram index
  would blow it up did not bear out.

  Extrapolated to 500,000 messages that would be roughly 9 GB of index. Whether
  query time stays under 200 ms at that size is still unmeasured; FTS5 should
  manage it. That needs holdings of that size to confirm.

- [ ] **What happens when somebody renames an IMAP folder?** MailBurg records
  the location under the folder's display name. "Customers" becomes
  "Customers 2025" and the high-water mark for that name is zero: the whole
  folder is fetched again and journalled as a second location. Nothing is lost
  and nothing is duplicated on disk, but the journal grows for no reason and
  the folder shows up twice in the tree. Whether the folder identifier from
  RFC 8474 (`OBJECTID`) solves this cleanly needs checking — not every server
  supports it.

- [ ] **Flags are a snapshot.** Whether a message was read or replied to is
  recorded once at archiving time and never revisited. Defensible for an
  archive — the question is whether anyone expects otherwise.

- [ ] **Umlaut transliteration in search.** `von:muller` now finds "Müller",
  but `von:mueller` does not. Expanding ue→ü would have to happen in the query
  itself. Is it worth it?

- [ ] **What happens when the archive's drive disappears mid-operation?**
  External disk unplugged, network share dropped, cloud not mounted. Untested.

## Done

- [x] **Archive format with hash chain.** Done 2026-08-25.
- [x] **Byte-exact, content-addressed storage.** Done 2026-08-25.
- [x] **Tombstones and retention locking.** Done 2026-08-25.
- [x] **Search index with second trigram index.** Done 2026-08-25.
- [x] **Message parsing, robust against broken headers and encodings.** Done 2026-08-25.
- [x] **Thunderbird, Maildir and MBOX sources.** Done 2026-08-25.
- [x] **Command line and 121 tests.** Done 2026-08-25.
- [x] **Legal position for DE/AT/CH researched.** Done 2026-08-25.
- [x] **Full-text extraction from attachments** (PDF and office formats).
  Done 2026-08-25.
- [x] **IMAP retrieval with account management.** Done 2026-08-25. Passwords in
  the keyring, incremental via `UIDVALIDITY` and the high-water mark read back
  out of the archive, failed messages flagged for retry. `CONDSTORE` was left
  out: it only helps with tracking changed flags, and we archive those as a
  snapshot anyway.
