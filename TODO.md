[Deutsch](TODO.md) | [English](TODO.en.md) | [Übersicht](README.md) | [Änderungsprotokoll](CHANGELOG.md)

# TODO

Laufende Liste offener Punkte. Oben steht, was noch offen ist. Erledigtes wird
nicht gelöscht, sondern nach unten verschoben – mit dem Datum, an dem es fertig
wurde.

## Offen

### Muss vor dem ersten echten Einsatz passieren

- [ ] **Anhänge im Volltext lesen.** Bisher werden nur die Dateinamen
  indiziert, nicht der Inhalt. Gebraucht werden PDF (`pypdf`, mit `pdftotext`
  aus poppler als schnellerem Weg, wenn vorhanden), DOCX, XLSX, PPTX, ODF,
  RTF. **Kein PyMuPDF** – das steht unter AGPL und würde ein MIT-Projekt
  anstecken. Die Verarbeitung muss in einen `ProcessPoolExecutor`, weil
  PDF-Auswertung rechenintensiv ist und sonst am GIL hängen bleibt.

- [ ] **IMAP-Abruf.** Kontenverwaltung für bis zu 30 Adressen, Passwörter im
  Schlüsselbund des Betriebssystems (`keyring`), niemals in einer
  Konfigurationsdatei. Inkrementell über `UIDVALIDITY` und die höchste gesehene
  UID je Ordner, `CONDSTORE` wenn der Server es beherrscht. Für den Anfang mit
  App-Passwörtern – OAuth2 braucht bei Google ein längeres Prüfverfahren und
  kommt später.

- [ ] **Grafische Oberfläche mit PySide6.** Dreispaltig: Kontenbaum,
  Trefferliste, Vorschau. Suchleiste mit Ergebnissen schon beim Tippen.
  Assistent zum Anlegen eines Archivs. **PySide6, nicht PyQt6** – PyQt6 steht
  unter GPLv3 und würde die MIT-Lizenz aushebeln, sobald fertige Binärpakete
  verteilt werden. Die API ist bis auf Kleinigkeiten dieselbe.

- [ ] **Der Rückweg in den Mailclient.** Drei Wege, weil unterschiedliche
  Situationen unterschiedliche brauchen: „In Mailprogramm öffnen" über eine
  temporäre `.eml` und `xdg-open`/`start`/`open`; Drag & Drop aus der
  Trefferliste ins Thunderbird-Fenster; „Wiederherstellen nach…" per IMAP
  `APPEND` zurück in einen wählbaren Ordner. Dazu Anhänge per Doppelklick
  öffnen.

- [ ] **Ausschlussregeln für private Mails.** Ordner, Absender oder
  Betreffmuster von der Archivierung ausnehmen. Der praktisch wichtigste
  Datenschutzbaustein: Wenn ein Firmenkonto auch privat genutzt werden darf,
  dürfen private Nachrichten nicht ohne Weiteres mitarchiviert werden. Siehe
  [RECHTLICHES.md](RECHTLICHES.md).

### Danach

- [ ] **Aufbewahrungskategorien in der Oberfläche.** Das Rechenwerk steht in
  `core/retention.py` und ist getestet, aber es gibt noch keinen Weg, einer
  Mail eine Kategorie zuzuweisen. Der Journalvorgang `classify` ist vorgesehen.
  Offen ist, ob sich Handelsbrief und Buchungsbeleg brauchbar automatisch
  unterscheiden lassen – vermutlich nur als Vorschlag, den der Anwender
  bestätigt.

- [ ] **Fälligkeitsbericht.** „Diese 342 Mails haben ihre Frist überschritten
  und sollten gelöscht werden." Gelöscht wird nur nach ausdrücklicher
  Bestätigung, nie von selbst – ein Programm, das eigenmächtig
  Geschäftsunterlagen entfernt, richtet mehr Schaden an als jede zu lange
  Aufbewahrung.

- [ ] **Auskunftsexport nach Art. 15 DSGVO.** Alle Mails zu einer Person
  zusammenstellen und als PDF oder ZIP herausgeben.

- [ ] **Verfahrensdokumentation erzeugen.** MailBurg kennt seine eigene
  Konfiguration und kann den technischen Teil einer Vorlage nach GoBD
  vorausfüllen. Den organisatorischen Teil ergänzt der Anwender. Im Text muss
  unmissverständlich stehen, dass die Verantwortung dafür beim Steuerpflichtigen
  liegt.

- [ ] **Zeitstempel nach RFC 3161.** Anbindung an einen TSA-Dienst für das
  Siegel. Das Feld ist im Format vorgesehen. Zu klären: welcher Dienst, was bei
  fehlender Internetverbindung geschieht, und ob ein kostenloser Anbieter wie
  FreeTSA für den Beweiswert genügt.

- [ ] **Verschlüsselung, pro Archiv wählbar.** Schlüssel aus dem Passwort über
  Argon2id, jede Datei einzeln mit AES-256-GCM. Der Dateiname darf dann nicht
  mehr der Klartext-Hash sein, sondern `HMAC(key, hash)` – sonst verrät schon
  das Verzeichnis, welche Mails im Archiv liegen. Beim Anlegen muss ein
  ausdruckbarer Wiederherstellungsschlüssel angeboten werden, samt deutlicher
  Warnung: ohne Passwort ist ein Langzeitarchiv unwiederbringlich weg.

- [ ] **Weitere Mailquellen.** Outlook PST/OST über `libpff`, Apple Mail
  `.emlx`.

- [ ] **Pakete für alle drei Systeme.** `.deb` und AppImage für Linux,
  PyInstaller mit Inno Setup für Windows, `.app` und `.dmg` für macOS. Für
  macOS ist zu klären, wie mit Gatekeeper umgegangen wird, solange keine
  Signatur vorliegt.

### Offene Fragen

- [ ] **Wie verhält sich der Nextcloud-Client bei laufender Archivierung?**
  Die Sperrdatei verhindert, dass zwei Rechner gleichzeitig schreiben. Ungeklärt
  ist, was passiert, wenn der Client eine Datei anfasst, während MailBurg sie
  gerade schreibt. Zu prüfen: ob das „erst daneben schreiben, dann umbenennen"
  aus `store.py` dafür schon ausreicht.

- [ ] **Wie schnell ist die Suche bei einer halben Million Mails wirklich?**
  Bisher nur an Kleinstbeständen gemessen. Ziel sind unter 200 ms. Zu klären
  ist auch, wie groß der Index dann tatsächlich wird – die Schätzung für den
  Dreizeichenindex ist bislang nur eine Schätzung.

- [ ] **Umlaut-Umschreibungen in der Suche.** `von:muller` findet inzwischen
  „Müller", aber `von:mueller` nicht. Die Auffächerung ue→ü müsste die
  Suchanfrage selbst leisten. Lohnt der Aufwand?

- [ ] **Was passiert bei einem Archiv auf einer Platte, die zwischendurch
  weggeht?** Externe Platte abgezogen, Netzlaufwerk getrennt, Cloud nicht
  eingehängt. Bisher ungetestet.

## Erledigtes

- [x] **Archivformat mit Hash-Kette.** Erledigt am 2026-08-25.
- [x] **Bytegenaue, inhaltsadressierte Ablage.** Erledigt am 2026-08-25.
- [x] **Grabsteine und Fristenschutz.** Erledigt am 2026-08-25.
- [x] **Suchindex mit zweitem Index über Dreizeichengruppen.** Erledigt am 2026-08-25.
- [x] **Mailparsing, robust gegen kaputte Kopfzeilen und Kodierungen.** Erledigt am 2026-08-25.
- [x] **Thunderbird-, Maildir- und MBOX-Quellen.** Erledigt am 2026-08-25.
- [x] **Kommandozeile und 121 Tests.** Erledigt am 2026-08-25.
- [x] **Rechtslage DE/AT/CH aufgearbeitet.** Erledigt am 2026-08-25.
