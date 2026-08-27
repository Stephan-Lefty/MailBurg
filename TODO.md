[Deutsch](TODO.md) | [English](TODO.en.md) | [Übersicht](README.md) | [Änderungsprotokoll](CHANGELOG.md) | [Anleitungen](docs/README.md)

# TODO

Laufende Liste offener Punkte. Oben steht, was noch offen ist. Erledigtes wird
nicht gelöscht, sondern nach unten verschoben – mit dem Datum, an dem es fertig
wurde.

## Offen

### Nicht anfassen

- **Die Zeitpläne stehen so, wie Stephan sie will** (2026-08-26): Abruf
  ins Geschäftsarchiv alle 30 Minuten, ins Privatarchiv einmal täglich,
  Sicherung beider monatlich mit zwei Ständen. Das ist keine
  Fehleinstellung, sondern Absicht – geschäftlich wartet jemand auf
  Antwort, privat eilt nichts.

### Plan für den 2026-08-27

In dieser Reihenfolge, mit Stephan am 2026-08-26 abends verabredet.

- [ ] **3. Mails aus MailStore Home holen – dafür zuerst eine
  Windows-VM.** MailStore Home läuft nur unter Windows; ohne VM kommt
  niemand an den Bestand heran (Stephan, 2026-08-26). Die VM ist damit
  Voraussetzung, nicht Nebensache – und sie erledigt nebenbei den
  Windows-Test aus den offenen Fragen weiter unten. Die EML-Quelle steht seit
  gestern. Offen sind drei Fragen an Stephan, die von hier aus nicht zu
  beantworten sind: Was bietet MailStore Home unter »Exportieren« an?
  Läuft es unter Windows oder Wine? Wie viele Mails sind es? An das
  MailStore-Format selbst wird nicht herangegangen – ein Archiv, das
  Mails aus einem nachgebauten Format zieht, kann die Bytegenauigkeit
  nicht garantieren.

- [ ] **4. Meldet MailBurg, wenn das Sicherungsziel fehlt?** Beide
  Sicherungen schreiben nach `/mnt/…/Storage-Box/`. Ist das
  am Monatsersten nicht eingehängt, schreibt der Dienst ins Leere. Ob
  das auffällt, ist ungeprüft – und eine Sicherung, die stillschweigend
  ausbleibt, ist schlimmer als keine.

- [ ] **5. `konten zuordnung` soll Archivnamen zeigen, keine Kennungen.**
  Derzeit steht dort `220b2cd0-f3b1-49ea-…`. Richtig wäre der Name des
  Archivs, mit der Kennung nur als Zusatz.

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

- [ ] **Anmeldung per OAuth2.** Der Abruf läuft mit App-Passwörtern. Das
  genügt, ist aber nicht das, was Gmail und Outlook eigentlich wollen: Dort
  gehört OAuth2 hin. Bei Google hängt daran ein Prüfverfahren für die
  Anwendung, das Zeit kostet – deshalb später und nicht als Voraussetzung für
  den ersten Einsatz.

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

- [ ] **Der Rückweg: „In Mailprogramm öffnen".** Über eine temporäre
  `.eml` und `xdg-open`/`start`/`open`. Die beiden anderen Wege stehen
  (siehe Erledigtes); dieser fehlt noch, und mit ihm die Frage, wo die
  temporäre Datei liegt und wann sie wieder verschwindet. Bei einem
  Archiv, dem man Post anvertraut, ist eine `.eml`, die in `/tmp`
  liegenbleibt, kein Detail.

- [ ] **Ausschlussregeln für private Mails.** Ordner, Absender oder
  Betreffmuster von der Archivierung ausnehmen. Der praktisch wichtigste
  Datenschutzbaustein: Wenn ein Firmenkonto auch privat genutzt werden darf,
  dürfen private Nachrichten nicht ohne Weiteres mitarchiviert werden. Siehe
  [RECHTLICHES.md](RECHTLICHES.md).

  **Für Stephans eigenen Bestand nicht dringend** (2026-08-26): Er würde
  bei beruflicher Nutzung einer Adresse die Postfächer neu strukturieren,
  statt sich auf Filter zu verlassen. Das ist der sauberere Weg – eine
  Ausschlussregel greift erst nach dem Abruf und ist eine Zusicherung, die
  das Programm geben muss; getrennte Postfächer sind eine Tatsache. Der
  Punkt bleibt trotzdem offen: MailBurg ist öffentlich, und wer ein
  gemischt genutztes Firmenkonto erbt, kann nicht mehr neu strukturieren.
  Dann sollte die Doku wenigstens sagen, dass die Trennung an der Quelle
  vorzuziehen ist.


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

- [ ] **Hält das Windows-Versprechen im README noch?** Die Tests laufen dort
  seit dem 2026-08-26 grün – der Grund für den Totalausfall war `fsync` auf
  einem nur lesend geöffneten Deskriptor, siehe CHANGELOG. Damit ist belegt,
  dass die Tests und die Einrichtung über `install.ps1` durchlaufen.

  Nicht belegt ist der Betrieb: kein Testgerät, kein echtes Postfach, keine
  Oberfläche unter Windows gestartet. Dieselbe Lücke gilt für macOS. Dass die
  CI grün ist, beantwortet die Frage nicht – sie war es ja gerade nicht, und
  trotzdem stand das Versprechen schon im README.

  **Stephan testet Windows selbst** (2026-08-26), sobald die Arbeit an
  seinem Linux-Rechner abgeschlossen ist. Bis dahin bleibt das README, wie
  es ist. Wird daraus nichts, muss dort stehen, was erprobt ist – ein
  Versprechen, das niemand eingelöst hat, ist schlimmer als eine Lücke,
  zu der man sich bekennt. macOS bleibt davon unberührt und ohne Aussicht
  auf ein Testgerät.

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

  **Der Test am Firmenarchiv (rund 700.000 Mails) wartet auf den
  Dauerbetrieb** (Stephan, 2026-08-26): Erst muss sich zeigen, wie stabil
  MailBurg auf einem einzelnen Rechner über Wochen läuft. Das ist die
  richtige Reihenfolge – ein Lasttest an einem Bestand, den man nicht
  ersetzen kann, beweist wenig, solange die Grundlage nicht steht.

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

- [x] **Dunkles Thema: die Bereiche abgrenzen.** Erledigt am 2026-08-27.
  Nachgemessen ergab sich, dass es kein Farb-, sondern ein
  Kantenproblem war: Zwischen Fensterhintergrund und Inhaltsbereich
  liegt ein Kontrastverhältnis von 1,15, in *jedem* Thema. Gezeichnet
  werden jetzt Rahmen in der Systemfarbe ``Mid`` – für alle Fenster,
  auch für die Gruppen der Ersteinrichtung, die Stephan als das
  Schlimmste benannt hatte. Platzhaltertexte bekommen im Dunkeln 70
  Prozent Deckkraft statt Qts 50.

  **Am Gerät noch nicht geprüft**: Stephan sieht es sich später auf dem
  14-Zoll-Laptop an. Ein einheitlicher Grauton für beide Themen wurde
  durchgerechnet und verworfen – er käme auf 3,90 in beide Richtungen,
  während die abgeleitete Lösung im Dunkeln 7,05 erreicht.
- [x] **Scans mit riesigen Seitenmaßen.** Erledigt am 2026-08-27. Ein
  Scan aus der iPhone-Kamera-App misst 4507 × 6681 Punkte; bei 300 dpi
  wären das 523 Megapixel, woran tesseract stumm erstickte. Die
  Auflösung richtet sich jetzt nach der Seitengröße. Passwortgeschützte
  PDF melden das, statt sich als »kein Text erkannt« auszugeben.
- [x] **Dokumente melden, aus denen kaum Text kam.** Erledigt am
  2026-08-27. Erledigt heißt nicht gelesen – wer das nicht erfährt,
  hält sein Archiv später für unvollständig.
- [x] **Beim Öffnen steht die jüngste Nachricht oben.** Erledigt am
  2026-08-27, für jedes Archiv gleich.
- [x] **Menüpunkt »Hilfe → Info«.** Erledigt am 2026-08-27: Urheber,
  Fassung und die beiden Wege für Fehlermeldungen.

- [x] **Doppelte Anhänge nur einmal erkennen.** Erledigt am 2026-08-26.
  Ein Anhang, der an mehreren Mails hängt, ging mehrfach durch tesseract.
  Am Geschäftsarchiv gemessen: 222 gelesene Dokumente, aber nur 67
  verschiedene – 70 Prozent der Rechenzeit waren Abschriften. Verglichen
  werden jetzt die Bytes des Anhangs, über Läufe und Archive hinweg;
  `mailburg vorrat` holt das für schon erkannte Bestände nach.
- [x] **Grafische Oberfläche mit PySide6.** Erledigt am 2026-08-26.
  Dreispaltig, Suche beim Tippen, Vorschau mit Anhangsliste, Doppelklick
  öffnet die Nachricht in einem eigenen Fenster. Dazu Menüs für Archiv,
  Post, Suchen, Ansicht, Einstellungen und Hilfe, ein Handbuch in zehn
  Kapiteln und Schriftgrößen über Strg + / − / 0.
- [x] **Suchmaske nach dem Vorbild von MailStore.** Erledigt am
  2026-08-26. Sie baut einen Suchausdruck zusammen und zeigt ihn an –
  die Maske kann nichts, was die Suchsprache nicht kann.
- [x] **Der Rückweg ins Postfach.** Erledigt am 2026-08-26, zwei von drei
  Wegen: „Zurücklegen…" per IMAP `APPEND` mit dem ursprünglichen Datum,
  auch in ein anderes Postfach als das der Herkunft, und „Als Datei
  speichern…" als `.eml`. Anhänge öffnen per Doppelklick.
- [x] **Bestehende Archive neu indizieren.** Erledigt am 2026-08-26 an
  beiden Archiven. Das Programm weist inzwischen von selbst darauf hin,
  wenn der Index leer ist, aber Dateien auf der Platte liegen.
- [x] **Texterkennung aus der Oberfläche.** Erledigt am 2026-08-26.
  Parallel über mehrere Kerne, Kernzahl wählbar, kleinste Dokumente
  zuerst, läuft beim Schließen des Fensters im Hintergrund weiter.
- [x] **Archivsicherung als eine komprimierte Datei.** Erledigt am
  2026-08-26, mit Zeitplan über systemd-Timer, eine Einheit je Archiv.

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
