[Deutsch](TODO.md) | [English](TODO.en.md) | [Übersicht](README.md) | [Änderungsprotokoll](CHANGELOG.md) | [Anleitungen](docs/README.md)

# TODO

Laufende Liste offener Punkte. Oben steht, was noch offen ist. Erledigtes wird
nicht gelöscht, sondern nach unten verschoben – mit dem Datum, an dem es fertig
wurde.

## Offen

### Muss vor dem ersten echten Einsatz passieren

- [ ] **Was als Anhang gilt, soll der Anwender festlegen können.** Nicht
  als Endungsliste zum Tippen, sondern als Gruppen zum Ankreuzen in der
  Einrichtung: Dokumente (PDF, Office, ODF, RTF), Tabellen und Daten (CSV,
  XML, JSON), Bilder, Archive, Kalender und Kontakte, alles übrige.

  **Gespeichert wird trotzdem alles.** Die Auswahl steuert nur, was als
  Anhang *gilt* – ob `hat:anhang` anschlägt, was in der Anhangsliste steht,
  was durchsucht wird. Die Datei bleibt in der Mail; alles andere bräche
  die Bytegenauigkeit und damit die Hash-Kette.

  Die Festlegung gehört in `archive.json` und bei einer Änderung ins
  Journal, nicht in die Programmeinstellungen: Für ein Geschäftsarchiv ist
  »was haben wir als Anhang behandelt« Teil der Verfahrensdokumentation.
  Wer später erklären muss, warum eine Datei nicht auffindbar war, will das
  belegen können.

- [ ] **Bestehende Archive einmal neu indizieren.** Wer von einer Fassung
  vor dem Anhangsvermerk kommt, hat in `attachments.text_zeichen` überall
  `-1` stehen; für diese Zeilen greift weiter die grobe Schätzung je Mail.
  An Stephans Bestand: 156 statt der erwarteten rund 700 Dokumente in der
  Warteschlange. `mailburg neuaufbau` richtet das. Offen ist, ob das
  Programm von selbst darauf hinweisen sollte.

- [ ] **Anmeldung per OAuth2.** Der Abruf läuft mit App-Passwörtern. Das
  genügt, ist aber nicht das, was Gmail und Outlook eigentlich wollen: Dort
  gehört OAuth2 hin. Bei Google hängt daran ein Prüfverfahren für die
  Anwendung, das Zeit kostet – deshalb später und nicht als Voraussetzung für
  den ersten Einsatz.

- [ ] **Grafische Oberfläche mit PySide6.** Dreispaltig: Kontenbaum,
  Trefferliste, Vorschau. Suchleiste mit Ergebnissen schon beim Tippen.
  **PySide6, nicht PyQt6** – PyQt6 steht unter GPLv3 und würde die
  MIT-Lizenz aushebeln, sobald fertige Binärpakete verteilt werden. Die API
  ist bis auf Kleinigkeiten dieselbe.

  Der Einrichtungsassistent steht (`ui/assistent.py`), das Hauptfenster
  fehlt noch – und damit auch ein Startbefehl. Zur Vorschau gehört:
  Anhangsliste unter der Mail, **Bilder gleich angezeigt**, alles andere
  per Doppelklick im zuständigen Programm.

- [ ] **Suchmaske nach dem Vorbild von MailStore.** Stephan hat die Maske
  der Serverfassung als Anhaltspunkt geliefert (2026-08-25). Grundsatz
  dabei: **Die Maske darf nichts können, was die Suchsprache nicht kann.**
  Sie baut einen Suchausdruck zusammen und zeigt ihn an – sonst entstehen
  zwei Wege, von denen einer immer hinterherhinkt, und die Kommandozeile
  wäre der schwächere.

  Anders als dort würde ich die fünf Ankreuzfelder für die Suchfelder
  weglassen: Sie stehen ohnehin alle auf »an«. Wer nur `rechnung` tippt,
  soll nichts weiter anfassen müssen; Einschränkungen kommen darunter.

  Dazu gehören **gespeicherte Suchen** (»Öffnen…«, »Speichern unter…«).

- [ ] **Gespeicherte Suchen.** In der MailStore-Maske »Öffnen…« und
  »Speichern unter…«. Wer denselben Auszug regelmäßig braucht – etwa alle
  Rechnungen eines Lieferanten –, soll ihn nicht jedes Mal neu
  zusammensetzen müssen.

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

- [ ] **Das Archiv selbst als IMAP-Server anbieten – als abschaltbare
  Erweiterung, nicht im Kern.** MailBurg stellt sein Archiv als nur lesbares
  IMAP-Konto bereit. Dann bindet es jedes Mailprogramm ein – Thunderbird,
  Outlook, Apple Mail, K-9 Mail, FairEmail –, auf jedem Gerät, ohne eine
  Zeile App-Code und ohne Play Console oder App Store. Wer es nicht braucht,
  schaltet es nicht ein und hat auch keinen offenen Port.

  Nebenbei löst das den Rückweg in den Mailclient von selbst: Wer eine
  archivierte Mail beantworten will, tut das im gewohnten Programm.

  **Zur Erreichbarkeit.** Eine Cloud braucht es dafür nicht – wohl aber ein
  Gerät, das läuft. Das ist der eigentliche Punkt. Nextcloud ist der
  *Ablageort der Dateien*; den IMAP-Dienst muss ein laufendes Programm
  anbieten. Liegt das Archiv in der Cloud, der Rechner ist aber aus, gibt es
  kein IMAP. Drei sinnvolle Aufstellungen: im Heimnetz vom eingeschalteten
  PC, von unterwegs per VPN ins Heimnetz, oder dauerhaft von einem NAS
  beziehungsweise Raspberry Pi.

  Günstig dabei: Der nur lesende Zugriff ist schon vorgesehen –
  `Archive.open(pfad, exclusive=False)` umgeht die Sperrdatei. Ein
  IMAP-Dienst auf dem NAS kann das Archiv also ausliefern, während der PC
  gleichzeitig weiter archiviert.

  **Sicherheit ist der springende Punkt.** Ein IMAP-Dienst, der ins offene
  Netz zeigt, ist eine Angriffsfläche vor einem Archiv mit jahrzehntealter
  Post. Standard muss deshalb sein: nur auf `127.0.0.1` lauschen,
  ausdrücklich freizuschalten fürs Heimnetz, und für unterwegs der Verweis
  auf VPN oder Tailscale statt einer Portfreigabe im Router.

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

- [ ] **Die Tests scheitern unter Windows – vollständig.** Am 2026-08-25 lief
  die CI 35-mal, und jedes Mal brach unter Windows praktisch jeder Test mit
  `ERROR` ab (`test_abruf`, `test_archive`, alles). Gesehen hat es niemand,
  weil die roten Läufe untergingen. Verdacht: Pfadtrennzeichen oder Dateien,
  die unter Windows noch offen sind, während der Test sie wegräumen will –
  `PermissionError` beim Aufräumen von Temp-Verzeichnissen ist der Klassiker.

  Das hängt an einer Entscheidung, die ohnehin ansteht (siehe CLAUDE.md): Das
  README verspricht Linux, Windows und macOS. Erprobt ist keines der beiden
  letzteren, ein Testgerät gibt es für keines. Entweder wird Windows repariert
  und dann auch wirklich benutzt – oder das Versprechen wird auf das
  zurückgenommen, was belegt ist. Ein drittes gibt es nicht.

- [ ] **Wie verhält sich der Nextcloud-Client bei laufender Archivierung?**
  Die Sperrdatei verhindert, dass zwei Rechner gleichzeitig schreiben. Ungeklärt
  ist, was passiert, wenn der Client eine Datei anfasst, während MailBurg sie
  gerade schreibt. Zu prüfen: ob das „erst daneben schreiben, dann umbenennen"
  aus `store.py` dafür schon ausreicht.

- [ ] **Wie schnell ist die Suche bei einer halben Million Mails wirklich?**
  Am 2026-08-25 an 5.187 echten Mails gemessen (1,2 GB aus einem
  Thunderbird-Profil): **9 bis 13 ms** je Anfrage, quer durch Freitext,
  Feldsuche und Anhangstyp. Der Index belegt 95 MB, also 12 % der
  Archivgröße – die Befürchtung, der Dreizeichenindex würde ihn sprengen,
  hat sich nicht bestätigt.

  Hochgerechnet auf 500.000 Mails wären das rund 9 GB Index. Offen bleibt,
  ob die Suchzeit dann noch unter 200 ms liegt; FTS5 sollte das packen,
  gemessen ist es aber nicht. Dafür braucht es einen Bestand dieser Größe.

- [ ] **Was passiert, wenn jemand einen IMAP-Ordner umbenennt?** MailBurg
  merkt sich den Fundort unter dem angezeigten Namen. Aus »Kunden« wird
  »Kunden 2025«, und schon ist der Höchststand für diesen Namen null: Der
  ganze Ordner wird erneut geholt und als zweiter Fundort ins Journal
  geschrieben. Verloren geht nichts, doppelt auf der Platte liegt auch
  nichts – aber das Journal wächst ohne Not, und im Ordnerbaum steht der
  Ordner zweimal. Ob sich das über die Ordner-Kennung aus RFC 8474
  (`OBJECTID`) sauber lösen lässt, ist zu prüfen; nicht jeder Server kann das.

- [ ] **Marken bleiben eine Momentaufnahme.** Ob eine Mail gelesen oder
  beantwortet war, wird beim Archivieren festgehalten und danach nie wieder
  angefasst. Für ein Archiv ist das vertretbar – die Frage ist, ob jemand
  das anders erwartet.

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
- [x] **Suchsprache erweitert.** Erledigt am 2026-08-25: `datei:*.jpg` mit
  Platzhaltern über GLOB, `archiviert:` für den Zeitpunkt der Aufnahme ins
  Archiv (aus dem Journal, nicht von der Uhr), `groesse:>5MB`,
  `wichtigkeit:hoch` aus allen drei gebräuchlichen Kopfzeilen, sowie `cc:`,
  `bcc:` und `direkt:` über eine eigene Empfängertabelle.
- [x] **IMAP-Abruf mit Kontenverwaltung.** Erledigt am 2026-08-25. Passwörter
  im Schlüsselbund, inkrementell über `UIDVALIDITY` und den Höchststand aus
  dem Archiv, gescheiterte Mails werden vorgemerkt. `CONDSTORE` blieb außen
  vor: Es hilft nur beim Nachziehen geänderter Marken, und die archivieren
  wir ohnehin nur als Momentaufnahme.
