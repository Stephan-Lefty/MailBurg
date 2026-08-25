[Deutsch](TODO.md) | [English](TODO.en.md) | [Overview](README.en.md) | [Changelog](CHANGELOG.md)

# TODO

A running list. Open items at the top. Finished items are not deleted but moved
down, with the date they were completed.

## Open

### Needed before real-world use

- [ ] **Full-text extraction from attachments.** Only filenames are indexed so
  far, not contents. Needed: PDF (`pypdf`, with poppler's `pdftotext` as the
  faster path where available), DOCX, XLSX, PPTX, ODF, RTF. **Not PyMuPDF** —
  it is AGPL and would infect an MIT project. Extraction must run in a
  `ProcessPoolExecutor`, since PDF parsing is CPU-bound and would otherwise sit
  on the GIL.

- [ ] **IMAP retrieval.** Account management for up to 30 addresses, passwords
  in the operating system keyring, never in a config file. Incremental via
  `UIDVALIDITY` and the highest UID seen per folder, `CONDSTORE` where the
  server supports it. App passwords first — OAuth2 requires a lengthy review
  process at Google and comes later.

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

- [ ] **How fast is search at half a million messages, really?** Only measured
  on tiny sets so far. Target is under 200 ms. Also unclear how large the index
  actually grows — the trigram estimate is still just an estimate.

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
