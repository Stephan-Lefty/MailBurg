[Deutsch](TODO.md) | [English](TODO.en.md) | [Overview](README.en.md) | [Changelog](CHANGELOG.md) | [Guides](docs/README.md)

# TODO

A running list. Open items at the top. Finished items are not deleted but moved
down, with the date they were completed.

## Open

### Needed before real-world use

- [ ] **The Server Edition: archive encryption is still missing.** Everything
  else has been in place since 2026-08-31 and exercised against the demo
  archive: users and permissions, the permission check inside search,
  passwords without a keyring, the service, and read access in the browser
  including the search form and attachments.

  Setting it up: [docs/server-einrichten.md](docs/server-einrichten.md)
  (German). The reasoning behind it: [docs/server.md](docs/server.md).

  **Why encryption belongs here** and not further down with the other
  plans: the decision of 2026-08-25 to do without it had a reason — without
  it a startup password would have been theatre, since the messages sit as
  files in a folder and whoever is at the machine reads them anyway. On a
  server, "whoever is at the machine" is no longer the same person as
  "whoever may see the data", and backups may travel to a cloud. That
  reasoning no longer holds there.

  The design for it is further down under "Encryption, selectable per
  archive".

  **What the server also cannot do yet:** write. Classifying, deleting and
  restoring to a mailbox stay with the command line and the window. That is
  the scope, not a defect — those operations write to the journal, and who
  may trigger them has to be settled first.

- [ ] **Dates follow the system language, the buttons do not.** A
  contradiction noticed on 2026-08-31, when the interface tests first ran in
  CI: `ui/app.py` pins Qt to German **deliberately** — the program is German
  throughout, and English buttons beside it would be a break. `ui/datum.py`
  asks `QLocale` instead, and thus the system setting.

  On an English system that puts "Weiter" next to "8/24/2026"; on a server
  with no locale, "24 08 2026". Either decision is defensible on its own;
  together they are inconsistent. To be settled.

- [ ] **Subject patterns as a rule field?** Deliberately left out: a subject can
  be forged, it changes over the course of an exchange, and a rule matching
  "invoice" would also catch the marketing mail pretending to be one. Folder and
  sender are more dependable. Should anyone ask for it, it would be two lines in
  `FELDER` — the question is not whether it can be done, but whether it should.

### Afterwards

- [ ] **Serve the archive itself over IMAP — as an optional add-on, not in the
  core.** MailBurg would offer its archive as a read-only IMAP account. Every
  mail client could then bind it: Thunderbird, Outlook, Apple Mail, K-9 Mail,
  FairEmail — on any device, without a line of app code and without Play Console
  or App Store. Anyone who does not need it never switches it on and has no open
  port either.

  It also solves the way back into the mail client by itself: to reply to an
  archived message, you do it in the program you already use.

  **On reachability.** This needs no cloud — but it does need a device that is
  running, and that is the actual point. Nextcloud is where the *files* live;
  the IMAP service has to be offered by a running program. If the archive sits
  in the cloud but the machine is off, there is no IMAP. Three sensible setups:
  from a switched-on PC on the home network, from outside via VPN into the home
  network, or permanently from a NAS or Raspberry Pi.

  Convenient here: read-only access already exists —
  `Archive.open(path, exclusive=False)` bypasses the lock file. So an IMAP
  service on the NAS can serve the archive while the PC keeps archiving into it.

  **Security is the crux.** An IMAP service facing the open internet is an
  attack surface in front of an archive holding decades of mail. The default
  must therefore be: listen on `127.0.0.1` only, opt in explicitly for the home
  network, and for access from outside point to VPN or Tailscale rather than a
  port forward in the router.

- [ ] **RFC 3161 timestamps.** Hooking a TSA service into the seal. The field is
  already provided for in the format. To be settled: which service, what happens
  without an internet connection, and whether a free provider such as FreeTSA
  carries enough evidentiary weight.

- [ ] **Encryption, selectable per archive.** Key derived from the passphrase via
  Argon2id, every file individually with AES-256-GCM. The file name may then no
  longer be the plaintext hash but `HMAC(key, hash)` — otherwise the directory
  alone reveals which messages the archive holds. On creation, a printable
  recovery key must be offered, along with a plain warning: without the
  passphrase a long-term archive is gone for good.

- [ ] **More mail sources.** Outlook PST/OST via `libpff`, Apple Mail `.emlx`.

- [ ] **Packages for all three systems.** `.deb` and AppImage for Linux,
  PyInstaller with Inno Setup for Windows, `.app` and `.dmg` for macOS. For macOS
  it remains to be settled how to deal with Gatekeeper as long as there is no
  signature.

### Open questions

- [ ] **OAuth2 against a real account.** The flow has only been verified against
  a mock provider running locally. Stephan's accounts live on his own servers and
  at Proton — there is no Microsoft account to test with.

  A second open question: whether Google's testing mode really does expire
  refresh tokens after seven days. If so, OAuth2 is unfit for scheduled retrieval
  with Gmail — which is why the guide still recommends an app password there.

- [ ] **How does the Nextcloud client behave during an ongoing archiving run?**
  The lock file prevents two machines from writing at once. What remains unclear
  is what happens if the client touches a file while MailBurg is writing it. To
  check: whether the "write beside it, then rename" from `store.py` is already
  enough.

- [ ] **How fast is search with half a million messages, really?** Measured on
  2026-08-25 against 5,187 real messages (1.2 GB from a Thunderbird profile):
  **9 to 13 ms** per query, across full text, field search and attachment type.
  The index takes 95 MB, or 12% of the archive size — the worry that the trigram
  index would blow it up did not materialise.

  Extrapolated to 500,000 messages that would be roughly 9 GB of index. What
  remains open is whether query time then stays below 200 ms; FTS5 should manage,
  but it has not been measured. That needs a corpus of that size — see
  "Postponed".

- [ ] **Why does the splash image never arrive in the `.exe`?** Removed on
  2026-08-30 because the reason for having it fell away — not because the
  question was answered. Anyone picking it up again will find the trail in
  `werkzeuge/mailburg.spec`: the image was flawless in the end, the build
  reported "Building Splash", and still all that appeared was an empty window.

- [ ] **Flags stay a snapshot.** Whether a message was read or replied to is
  recorded at archiving time and never touched again. For an archive that is
  defensible — the question is whether anyone expects otherwise.

### Postponed — for testing in mid-October 2026

Stephan on 2026-08-31: anything to do with Windows Server or the 700,000
messages moves to mid-October, because he cannot test it before then.

Both are built or prepared — they have simply never run. Until the test
they sit here and not in the running list.

- [ ] **The Windows service.** `mailburg/server/windows_dienst.py` via
  pywin32, as `mailburg[server-windows]`. Written to the pattern from the
  pywin32 examples, looked up on 2026-08-31 — but never run on Windows.

  Two findings drove the choice: Task Scheduler will start a program
  without a logged-in user but will not keep it alive — if it crashes, it
  stays down. And NSSM, the most widespread wrapper, has had no stable
  release in over a decade.

  **When setting it up the first time**, run `mailburg server` by hand
  alongside to verify the settings before touching the service.

- [ ] **Pull mail out of MailStore Home** — and with it the load test against
  roughly 700,000 messages. The Windows VM has been up since 2026-08-27;
  MailStore Home runs in it but cannot reach the archive: "Invalid crypt key".
  The cause is unresolved; it has been attempted once so far, under time
  pressure.

  **The archive will not be deleted before that has been seriously attempted.**
  On 2026-08-28 the question came up of simply throwing it away, on the
  assumption that its contents were in MailBurg anyway. That is not the case:
  imports came from Thunderbird and over IMAP; nobody has got at MailStore. What
  is in there, nobody knows.

  And it is not a small amount: **37 GB, 9,380 files, business correspondence
  from 2010 to 2024.** Retention periods therefore apply — six years for
  commercial letters, ten for accounting-relevant records. Everything from 2016
  onward is still mandatory today. A program meant to help meet such deadlines
  must not become the reason for breaching them.

  Open questions from back then: what does MailStore Home offer under "Export"?
  How many messages are there? The MailStore format itself will not be reverse
  engineered — an archive that pulls mail out of a reconstructed format cannot
  guarantee byte fidelity.

  **The order is the right one anyway** (Stephan, 2026-08-26): first it has to
  show how stably MailBurg runs over weeks. A load test on a corpus that cannot
  be replaced proves little while the foundation is unproven.

### Do not touch

- **The schedules are as Stephan wants them** (2026-08-26): retrieval into the
  business archive every 30 minutes, into the private archive once a day, backup
  of both monthly keeping two generations. That is not a misconfiguration but
  intent — in business someone is waiting for an answer, privately nothing is
  urgent.

## Done

### 2026-08-30

- [x] **The way back: "Open in mail client".** All three routes out of the
  archive now exist. Right-click a message and it opens in Thunderbird, Outlook
  or Apple Mail.

  Confirmed on Stephan's machine the same evening: "works perfectly". So the
  route is not merely built but exercised — on Linux with Thunderbird. Windows
  and macOS remain unverified; there it is `os.startfile` and `open` that decide
  what happens.

  **The question was never the opening, it was the file.** An `.eml` is the
  complete message — body, attachments, addresses. In a shared temp directory
  anyone on a multi-user machine could read it; it therefore lives in the user's
  cache, in a directory with `0700`, and the file itself has `0600`.

  **It has to disappear again, too.** Immediately is not an option — the mail
  client is still reading it. Cleanup happens twice: on the next open, everything
  older than four hours; on MailBurg exit, the whole directory. Anything Windows
  holds open stays until next time and aborts nothing.

- [x] **Exclusion rules for private mail.** Built as classification rules:
  `core/regeln.py`, `mailburg regeln`, *Mail → Classify on arrival …*,
  [docs/regeln.md](docs/regeln.md).

  **Different from what was originally intended here.** The item was called
  "exclusion" — exempting mail from being archived. Decided otherwise with
  Stephan on 2026-08-30: everything is fetched, the rule only determines the
  classification. A rule that prevents fetching throws away what it matches;
  whoever later notices it reached too far has lost that mail, if the mailbox has
  since been cleared. A wrong classification can be taken back.

  The original purpose is met — private mail is no longer subject to a retention
  period — but the data-protection thought behind the old entry only halfway: the
  message still *sits* in the business archive. Anyone who does not want it there
  at all deletes it; classified as private, no retention period stands in the way.

  The note from 2026-08-26 still holds and is now in the guide as well:
  **separating at the source is preferable.** Separate mailboxes are a fact; a
  rule is an assurance the program has to give. But whoever inherits a
  mixed-use company account can no longer restructure — the rule is for them.

- [x] **Windows 11 verified on real hardware.** The first run outside the VM,
  with a freshly built `.exe` from commit `70403ee`. Schedule, backup dialog and
  everything else worked — Stephan: "Everything else worked."

  Two findings no VM could have produced:

  **Startup takes seconds, not twenty.** In the VM it was 20–25 seconds; nearly
  all of that went to virtualisation, not to unpacking the 160 MB. That also
  settles whether a single file is the right delivery form — it is.

  **The splash image is gone.** It failed to appear on real hardware too — only
  an empty window: "it's exactly the same window that opens with nothing in it,
  just like in the VM". Two genuine bugs had been fixed before that (16-bit
  instead of 8, `always_on_top`), and the image was flawless in the end — why the
  resource never arrives is now under open questions.

  It was removed anyway, and for a different reason: with a startup of a few
  seconds the point of it is gone. An image that flashes up and vanishes unsettles
  more than the wait it was meant to cover — an empty one all the more. The
  reasoning is in `werkzeuge/mailburg.spec`; a test holds it in place.

- [x] **Rebuild the `.exe` before testing it.** That morning a screenshot showed
  the old scheduling error ("unexpected node", `RandomDelay`) — which had not been
  in the source since the previous day. The file that had been run was older than
  the fix.

  That is the expensive mistake of this kind: you test an old build and take the
  finding for current. Whoever sets up the next test builds first and writes down
  the commit it was built from.

  The same screenshot did produce a real find, though: the message read
  "enth„lt" instead of "enthält". Fixed, see the changelog.

- [x] **Fixed mangled umlauts in Windows error messages.** Console programs on
  Windows write in the OEM code page (cp850 in Germany), where byte 0x84 is "ä";
  Python decoded in the ANSI code page cp1252, where the same byte is a quotation
  mark. Every message returned by `schtasks.exe` was affected — precisely the
  sentences someone is meant to read when something went wrong.

- [x] **Fixed: the backup dialog silently overwrote its own setting.** It read
  back *whether* backups run and *where to*, but not how often and how many
  generations. "Monthly, two generations" therefore became a daily overwrite of
  the same file on the next confirmation.

- [x] **The Windows guide is complete.** The last missing image — the main window
  with the example archive — has been taken.

- [x] **Number agreement on the command line.** Twelve places, among them "hash
  chain: intact (1 entries)" — that one was on no list. Found by creating an
  archive with a single message and running every command once.

- [x] **WinError 123 is explained.** A path with an unresolved variable is not a
  "disk gone".

- [x] **The English TODO brought up to date.** It dated from before 2026-08-26 and
  listed OCR and OAuth2 as open although both have long existed. Anyone reading
  only English took MailBurg to be further behind than it is — the inverse of what
  `RECHTLICHES.md` demands, but wrong either way. While at it, both lists are back
  in the same order.

### 2026-08-29

- [x] **OAuth2.** Sign-in without an app password per RFC 7636 (PKCE), tokens in
  the keyring, refresh with lead time when the connection is opened, operable
  from both the GUI and the command line. [docs/oauth2.md](docs/oauth2.md). What
  remains unverified about it is under open questions above.

- [x] **Cleaned the images out of the history.** An old revision of
  `docs/bilder/automatisierung.png` showed the real backup path, with Stephan's
  first name in it. The text cleanup from the same day had not caught it:
  `git filter-repo --replace-text` works on text, and a PNG is binary.

  All forty image revisions in the history were checked with OCR; exactly one was
  affected. Verified against a fresh clone from GitHub afterwards: 39 image
  revisions, all clean. 196 commits, both tags in place, release v0.10.0 and its
  `.exe` intact.

- [x] **Ten bugs from the screenshot pass.** Triggered by an example archive
  holding exactly one message: "1 messages in archive" in the status bar, the same
  gap when classifying, in the retention report, when importing a backup and on
  the assistant's final page; plus "The archive is in None", an image that showed
  something other than its caption, seventeen empty alt texts, "? (2)" for
  messages without a readable date, and `C:/Users/…` instead of `C:\Users\…` on
  Windows. All fixed, with tests.

- [x] **The backup dialog proposes a folder.** Previously, confirming produced an
  error message about an empty field the dialog itself had left empty. Cloud
  before external disk before another drive; never the home folder, and no
  proposal at all rather than one on the archive's own disk.

- [x] **The image of the schedule dialog on Windows** is in the guide.

- [x] **What happens if someone renames an IMAP folder?** Reproduced and fixed.
  The suspicion held: the folder was tracked twice, every message gained a second
  location, and the journal doubled. Three messages produced six entries instead
  of three; five thousand, accordingly.

  It is detected via `UIDVALIDITY`, which stays the same across a rename — RFC
  3501 requires that. RFC 8474 (`OBJECTID`) would be the cleaner route, but far
  from every server knows it.

  **Only when exactly one folder vanished and exactly one is new.** Two folders
  can carry the same `UIDVALIDITY`; the standard only demands uniqueness within
  one folder over time. In case of doubt nothing happens — then it reads twice, as
  before. A wrongly merged folder would be considerably worse.

### 2026-08-28

- [x] **The `.exe` for Windows.** A single file, 152 MB, no Python and no
  installation. Built by GitHub itself and attached to
  [v0.10.0](https://github.com/Stephan-Lefty/MailBurg/releases/tag/v0.10.0). Text
  recognition is included — poppler, tesseract and the German language data.

- [x] **Tried out in the VM with a real mailbox.** Setup, IMAP retrieval, search,
  preview, text recognition and scheduled retrieval via the Windows Task
  Scheduler. Six bugs came to light that would never have shown on Linux — among
  them two that would have made the schedule unusable.

- [x] **Umlaut transliteration in search.** The question "is it worth the effort?"
  answered itself on measurement: it was not only `mueller` but also `strasse`
  against `straße` — and Switzerland has no ß at all. The query now fans out by
  itself.

- [x] **Does MailBurg report a missing backup destination?** Reproduced: it did
  not. MailBurg created the folder with `mkdir -p`, wrote the backup into it and
  returned 0. With a mount point whose volume was not mounted, the backup would
  have landed on the system disk — and it would only have been noticed when
  needed.

  MailBurg now places a marker in the destination and checks for it. If it is
  missing from an empty or absent folder, the scheduled run aborts with exit code
  1 instead of writing to the wrong place. Manual creation stays allowed —
  somebody standing in front of it is setting things up. Plus a warning if backup
  and archive would sit on the same volume.

- [x] **`konten zuordnung` shows archive names, not identifiers**, and groups the
  output by archive. The question is "what ends up in my business archive?", and a
  list repeating an identifier for every mailbox answered it only laboriously.
  Names MailBurg cannot resolve stay identifiers: an archive on a disconnected
  disk still has mailboxes.

- [x] **Retention categories: classification exists now.**
  `mailburg einstufen ARCHIVE QUERY CATEGORY`, with journal operation `classify`
  and a dry run unless `--wirklich` is given. The effect is demonstrated too: a
  message from 2019 is locked until the end of 2027 as an accounting record, and
  already free as a commercial letter.

  **In the interface as well:** *Mail → Set retention …*, with a window that says
  in advance how many messages are affected and how long they will be protected
  afterwards. Visible only in a business archive.

  Whether commercial letter and accounting record can be told apart automatically
  remains open and was deliberately left alone: a suggestion the user confirms
  presumes they can judge it — and with a wrong automation nobody notices.

- [x] **Retention due report.** `mailburg faellig` and a prompt in the interface,
  once a year from 1 May onward.

  The date goes back to Stephan: "then this question only comes once a year." Not
  from 1 January, when the periods lapse — a message that appears on every launch
  gets clicked away unread.

  **In private archives too**, also his suggestion, but in a different tone: no
  retention periods, just a note about mail older than ten years, and explicitly
  the sentence that age is no reason to delete.

- [x] **Subject access export under Art. 15 GDPR.** `mailburg auskunft` and
  *Archive → GDPR subject access …*. As a ZIP with the unmodified `.eml` files and
  a cover sheet, not as PDF: printing a message to PDF means altering it.

  The cover sheet names explicitly what MailBurg *cannot* decide — third-party
  data in the same messages (Art. 15(4)) and completeness across multiple
  addresses. The operation is journalled, because of the accountability duty in
  Art. 5(2).

- [x] **Generate procedural documentation.** `mailburg verfahrensdoku` and
  *Archive → Procedural documentation …*. Seven sections as Markdown; whatever
  MailBurg cannot know is left as `[BITTE ERGÄNZEN]` and counted on save.

  Only the mailboxes of *this* archive are listed. The account list applies to the
  whole program — anyone running two archives would otherwise have the same
  mailboxes in both documents, and neither would state the truth.

- [x] **What happens to an archive on a disk that disappears mid-run?**
  Reproduced by pulling the archive directory away during an import of 3,000
  messages — for the program much the same as an unplugged disk.

  **The archive stays intact.** 1,000 messages stored, hash chain unbroken,
  journal and storage in agreement. The order storage → journal → index holds what
  it promises. No torso is left at the original path either.

  **The message was no good.** A bare Python traceback came through — a wall of
  lines that fails to answer the only question that matters: is my archive broken
  now? It now says what happened, that nothing can have come to harm, and what to
  do. Exit code 4.

### 2026-08-27

- [x] **Windows exercised in operation.** The first real run at all. MailBurg
  starts, the interface appears, the assistant runs through, the free-space
  display is right, and passwords land in Credential Manager. Four bugs surfaced —
  the Python placeholder in `install.ps1`, a wrong version number in
  `pyproject.toml`, a greyed-out Next button without explanation, and an assistant
  that assigned mailboxes to no archive. All fixed.

  With that the Windows promise in the README is demonstrated rather than
  asserted. macOS remains untried, with no prospect of a test machine.

- [x] **Dark theme: delineating the panels.** Measuring showed it was not a colour
  problem but an edge problem: between window background and content area lies a
  contrast ratio of 1.15, in *every* theme. Borders are now drawn in the system
  colour `Mid` — for all windows, including the groups in first-time setup, which
  Stephan had named as the worst. Placeholder text gets 70% opacity in the dark
  instead of Qt's 50.

- [x] **Scans with enormous page dimensions.** A scan from the iPhone camera app
  measures 4507 × 6681 points; at 300 dpi that would be 523 megapixels, which
  tesseract choked on silently. Resolution now follows page size.
  Password-protected PDFs report that instead of passing themselves off as "no
  text recognised".

- [x] **Report documents that yielded almost no text.** Processed does not mean
  read — without being told, people later think their archive is incomplete.

- [x] **The newest message is on top when opening**, the same for every archive.

- [x] **Menu item "Help → About".** Author, version and the two routes for bug
  reports.

### 2026-08-26

- [x] **Recognise duplicate attachments only once.** An attachment on several
  messages went through tesseract repeatedly. Measured on the business archive:
  222 documents processed, but only 67 distinct ones — 70% of the compute time was
  copies. The attachment's bytes are now compared, across runs and archives;
  `mailburg vorrat` catches up on already-processed holdings.

- [x] **Graphical interface with PySide6.** Three panes, search as you type,
  preview with attachment list, double-click opens a message in its own window.
  Plus menus for Archive, Mail, Search, View, Settings and Help, a manual in ten
  chapters, and font sizes via Ctrl + / − / 0.

- [x] **Advanced search form modelled on MailStore.** It assembles a query and
  displays it — the form can do nothing the query language cannot.

- [x] **The way back into the mailbox**, two of three routes: "Restore…" via IMAP
  `APPEND` with the original date, into a different mailbox than the origin if
  wanted, and "Save as file…" as `.eml`. Attachments open on double-click.

- [x] **Re-index existing archives**, exercised on both archives. The program now
  points this out by itself when the index is empty but files are on disk.

- [x] **Text recognition from the interface.** In parallel across several cores,
  core count selectable, smallest documents first, keeps running in the background
  when the window is closed.

- [x] **Archive backup as a single compressed file**, with a schedule via systemd
  timers, one unit per archive.

### 2026-08-25

- [x] **Archive format with hash chain.**
- [x] **Byte-exact, content-addressed storage.**
- [x] **Tombstones and retention protection.**
- [x] **Search index with a second index over trigrams.**
- [x] **Mail parsing, robust against broken headers and encodings.**
- [x] **Thunderbird, Maildir and MBOX sources.**
- [x] **Command line and 121 tests.**
- [x] **Legal situation for DE/AT/CH worked through.**
- [x] **Query language extended:** `datei:*.jpg` with wildcards via GLOB,
  `archiviert:` for the time of ingestion into the archive (from the journal, not
  from the clock), `groesse:>5MB`, `wichtigkeit:hoch` from all three common
  headers, plus `cc:`, `bcc:` and `direkt:` via a dedicated recipient table.
- [x] **IMAP retrieval with account management.** Passwords in the keyring,
  incremental via `UIDVALIDITY` and the high-water mark from the archive, failed
  messages are set aside for a retry. `CONDSTORE` was left out: it only helps in
  catching up changed flags, and we archive those as a snapshot anyway.
