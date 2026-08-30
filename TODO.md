[Deutsch](TODO.md) | [English](TODO.en.md) | [Übersicht](README.md) | [Änderungsprotokoll](CHANGELOG.md) | [Anleitungen](docs/README.md)

# TODO

Laufende Liste offener Punkte. Oben steht, was noch offen ist. Erledigtes wird
nicht gelöscht, sondern nach unten verschoben – mit dem Datum, an dem es fertig
wurde.

## Offen

### Als Erstes, wenn ein echtes Windows greifbar ist

- [ ] **Das Startbild ist ungeprüft.** In der VM war es bis zuletzt nicht
  zu sehen – auch nicht, nachdem zwei echte Fehler behoben waren: Das Bild
  lag mit 16 Bit Farbtiefe vor (Tk kann nur 8), und `always_on_top` stand
  auf `False`, wodurch das randlose Fenster hinter den Desktop rutschte.

  Der Bau meldet »Building Splash«, aber ob die Ressource in der fertigen
  Datei ankommt, ließ sich von außen nicht feststellen. Eine VM ohne
  Grafikbeschleunigung ist für diese Frage der ungeeignete Ort: Dort kann
  ein randloses Fenster aus Gründen unsichtbar bleiben, die mit MailBurg
  nichts zu tun haben.

  **Auf dem Laptop zu prüfen:** Erscheint nach dem Doppelklick binnen
  einer Sekunde ein randloses Bild mit dem Logo? Läuft die Zeile darunter
  mit – erst Dateinamen, dann deutsche Sätze? Verschwindet es erst, wenn
  das Hauptfenster steht?

  Erscheint es weiterhin nicht, ist die nächste Frage nicht »warum«,
  sondern ob eine einzelne Datei überhaupt der richtige Weg ist. Ein
  Programmordner spart das Auspacken und damit die Wartezeit ganz – der
  Preis wäre, dass man nicht mehr eine Datei herunterlädt und
  doppelklickt.

- [ ] **Die Startzeit messen, wo sie zählt.** In der VM sind es 20–25
  Sekunden. Wie viel davon auf die Virtualisierung geht und wie viel auf
  das Auspacken der 154 MB, weiß niemand. Auf dem Laptop mit SSD lässt
  sich das trennen.

### Am 2026-08-29 erledigt

- [x] **Die Bilder aus der Historie bereinigt.** Auf einer alten Fassung
  von `docs/bilder/automatisierung.png` stand der echte Sicherungspfad –
  mit Stephans Vornamen darin. Die Textbereinigung vom selben Tag hatte sie
  nicht erfasst: `git filter-repo --replace-text` arbeitet auf Text, ein
  PNG ist Binärdatei.

  Alle vierzig Bildfassungen der Historie wurden mit Texterkennung
  geprüft; betroffen war genau eine. Ihr Inhalt ist gegen die saubere
  Fassung getauscht. Nachgeprüft an einem frischen Klon von GitHub: 39
  Bildfassungen, alle sauber – 39 statt 40, weil die getauschte Fassung nun
  mit der bestehenden zusammenfällt. 196 Commits, beide Tags stehen, das
  Release v0.10.0 samt `.exe` ist unversehrt.

  Sicherung: `/mnt/raid/VMs/MailBurg-vor-bildbereinigung-2026-08-29.bundle`

- [x] **Zehn Fehler aus dem Bilder-Durchgang.** Ausgelöst von einem
  Beispielarchiv mit genau einer Mail darin: „1 Mails im Archiv" in der
  Statuszeile, dieselbe Lücke beim Einstufen, bei den Fristen, beim
  Einlesen einer Sicherung und auf der Abschlussseite des Assistenten;
  dazu „Das Archiv liegt in None", ein Bild, das etwas anderes zeigte als
  seine Bildunterschrift, siebzehn Alternativtexte ohne Inhalt, „? (2)"
  für Mails ohne lesbares Datum und `C:/Users/…` statt `C:\Users\…` unter
  Windows. Alles behoben, mit Tests.

- [x] **Der Sicherungsdialog schlägt einen Ordner vor.** Vorher kam auf
  „Übernehmen" eine Fehlermeldung für ein leeres Feld, das der Dialog
  selbst leer gelassen hatte. Cloud vor externer Platte vor anderem
  Laufwerk; der Benutzerordner nie, und lieber kein Vorschlag als einer
  auf der Platte des Archivs.

- [x] **Das Bild des Zeitplandialogs unter Windows** ist in der Anleitung.

### Am 2026-08-30 erledigt

- [x] **Die Windows-Anleitung ist vollständig.** Das letzte fehlende Bild —
  das Hauptfenster mit dem Beispielarchiv — ist aufgenommen, mit der neuen
  `.exe` aus Commit `b3d1aa5`. Unten steht jetzt „1 Mail im Archiv" statt
  „1 Mails": die Gegenprobe für die Korrektur vom Vortag, an genau der
  Stelle, an der der Fehler aufgefallen war.

- [x] **Die Zahlwörter auf der Kommandozeile.** Zwölf Stellen, darunter
  „Hash-Kette: unversehrt (1 Einträge)" — die stand in keiner Liste.
  Gefunden, indem ein Archiv mit einer einzigen Mail angelegt und jeder
  Befehl einmal aufgerufen wurde.

- [x] **WinError 123 wird erklärt.** Ein Pfad mit unaufgelöster Variable ist
  kein „Platte weg". Die Behandlung stammte vom Windows-Durchgang am 28.08.
  und war nie committet worden.

### Als Nächstes dran

### Nicht anfassen

- **Die Zeitpläne stehen so, wie Stephan sie will** (2026-08-26): Abruf
  ins Geschäftsarchiv alle 30 Minuten, ins Privatarchiv einmal täglich,
  Sicherung beider monatlich mit zwei Ständen. Das ist keine
  Fehleinstellung, sondern Absicht – geschäftlich wartet jemand auf
  Antwort, privat eilt nichts.

### Am 2026-08-28 erledigt

- [x] **Die `.exe` für Windows.** Eine einzelne Datei, 152 MB, ohne Python
  und ohne Installation. Gebaut von GitHub selbst, an
  [v0.10.0](https://github.com/Stephan-Lefty/MailBurg/releases/tag/v0.10.0)
  angehängt. Die Texterkennung ist enthalten – poppler, tesseract und die
  deutschen Sprachdaten.

- [x] **In der VM ausprobiert, mit einem echten Postfach.** Einrichtung,
  IMAP-Abruf, Suche, Vorschau, Texterkennung und der regelmäßige Abruf
  über die Windows-Aufgabenplanung. Dabei kamen sechs Fehler ans Licht,
  die unter Linux nie aufgefallen wären – darunter zwei, die den Zeitplan
  unbrauchbar gemacht hätten.

- [x] **Umlaut-Umschreibungen in der Suche.** Die Frage »Lohnt der
  Aufwand?« hat sich beim Nachmessen beantwortet: Es ging nicht nur um
  `mueller`, sondern auch um `strasse` gegen `straße` – und in der Schweiz
  gibt es überhaupt kein ß. Die Suchanfrage fächert jetzt selbst auf.

### Alter Plan für den 2026-08-27

In dieser Reihenfolge, mit Stephan am 2026-08-26 abends verabredet.

- [ ] **3. Mails aus MailStore Home holen.** Die Windows-VM steht seit
  dem 2026-08-27; MailStore Home läuft darin, kommt aber nicht an das
  Archiv heran: »Invalid crypt key«. Die Ursache ist ungeklärt, versucht
  wurde es bisher einmal, unter Zeitdruck.

  **Das Archiv wird nicht gelöscht, bevor das nicht ernsthaft versucht
  wurde.** Am 2026-08-28 stand die Frage im Raum, es einfach wegzuwerfen –
  in der Annahme, der Inhalt liege ohnehin in MailBurg. Das trifft nicht
  zu: Importiert wurde aus Thunderbird und per IMAP, an MailStore ist
  niemand herangekommen. Was dort liegt, weiß niemand.

  Und es ist nicht wenig: **37 GB, 9.380 Dateien, Geschäftspost von 2010
  bis 2024** unter `/mnt/…/Firma/Mailarchiv`. Damit
  gelten Aufbewahrungsfristen – Handelsbriefe sechs Jahre, buchungs-
  relevante Unterlagen zehn. Alles ab 2016 ist heute noch pflichtig. Ein
  Programm, das beim Einhalten solcher Fristen helfen soll, darf nicht der
  Anlass sein, sie zu verletzen.

  Reihenfolge, am 2026-08-28 verabredet: erst die offenen TODOs, dann das
  Archiv.

  Alter Stand der Fragen: Was bietet MailStore Home unter »Exportieren«
  an? Wie viele Mails sind es? An das MailStore-Format selbst wird nicht
  herangegangen – ein Archiv, das Mails aus einem nachgebauten Format
  zieht, kann die Bytegenauigkeit nicht garantieren.

- [x] **4. Meldet MailBurg, wenn das Sicherungsziel fehlt?** (erledigt
  am 2026-08-28) Nachgestellt: Es meldete nichts. MailBurg legte den
  Ordner mit `mkdir -p` an, schrieb die Sicherung hinein und gab 0
  zurück. Bei einem Einhängepunkt ohne eingehängten Datenträger wäre sie
  damit auf der Systemplatte gelandet – und aufgefallen wäre es erst,
  wenn man sie braucht.

  MailBurg legt jetzt eine Marke im Zielordner ab und prüft sie. Fehlt
  sie in einem leeren oder fehlenden Ordner, bricht der Zeitplan mit
  Rückgabewert 1 ab, statt an den falschen Ort zu schreiben. Von Hand
  darf weiterhin angelegt werden – wer danebensteht, richtet gerade ein.
  Dazu ein Hinweis, wenn Sicherung und Archiv auf demselben Datenträger
  lägen; das stand bisher nur als Ratschlag im Dialogtext.

  **Zu Stephans Aufbau:** Die Sorge trifft ihn nicht.
  `/mnt/…/Storage-Box/` ist kein Einhängepunkt, sondern ein
  gewöhnlicher Ordner auf dem RAID – dort kann nichts „nicht eingehängt"
  sein. Und die Archive liegen auf der USB-Platte, also auf einem
  anderen Datenträger als die Sicherungen. Fehlt *die* Platte, meldet
  MailBurg „kein Archiv" und bricht ab (Rückgabewert 2).

- [x] **5. `konten zuordnung` soll Archivnamen zeigen, keine Kennungen.**
  (erledigt am 2026-08-28) Die Ausgabe ist zugleich nach Archiven
  gruppiert – die Frage lautet »was landet in meinem Geschäftsarchiv?«,
  und die beantwortete eine Liste, in der jedes Postfach seine Kennung
  wiederholt, nur mühsam. Namen, die MailBurg nicht auflösen kann, bleiben
  Kennungen: Ein Archiv auf einer abgezogenen Platte hat trotzdem
  Postfächer.

### Muss vor dem ersten echten Einsatz passieren

- [ ] **Der Rückweg: „In Mailprogramm öffnen".** Über eine temporäre
  `.eml` und `xdg-open`/`start`/`open`. Die beiden anderen Wege stehen
  (siehe Erledigtes); dieser fehlt noch, und mit ihm die Frage, wo die
  temporäre Datei liegt und wann sie wieder verschwindet. Bei einem
  Archiv, dem man Post anvertraut, ist eine `.eml`, die in `/tmp`
  liegenbleibt, kein Detail.

- [x] **Ausschlussregeln für private Mails** (2026-08-30). Gebaut als
  Einstufungsregeln: `core/regeln.py`, `mailburg regeln`, *Post → Beim
  Aufnehmen einstufen …*, [docs/regeln.md](docs/regeln.md).

  **Anders als hier ursprünglich gedacht.** Der Punkt hieß
  »Ausschluss« – Post von der Archivierung ausnehmen. Mit Stephan am
  2026-08-30 anders entschieden: Geholt wird alles, die Regel bestimmt
  nur die Einstufung. Eine Regel, die schon das Holen verhindert, wirft
  weg, was sie trifft; wer später merkt, dass sie zu weit griff, hat die
  Post verloren, falls sie im Postfach inzwischen gelöscht wurde. Eine
  falsche Einstufung lässt sich zurücknehmen.

  Damit ist der ursprüngliche Zweck erfüllt – private Post unterliegt
  keiner Aufbewahrungsfrist mehr –, der Datenschutzgedanke des alten
  Eintrags aber nur halb: Die Mail *liegt* weiterhin im Geschäftsarchiv.
  Wer sie dort gar nicht haben will, löscht sie; als privat eingestuft
  steht dem keine Frist entgegen.

  Der Hinweis von 2026-08-26 gilt weiter und steht jetzt auch in der
  Anleitung: **Die Trennung an der Quelle ist vorzuziehen.** Getrennte
  Postfächer sind eine Tatsache, eine Regel ist eine Zusicherung, die
  das Programm geben muss. Wer aber ein gemischt genutztes Firmenkonto
  erbt, kann nicht mehr neu strukturieren – für den ist die Regel da.

- [ ] **Betreffmuster als Regelfeld?** Bewusst weggelassen: Der Betreff
  lässt sich fälschen, er wechselt im Verlauf eines Austauschs, und eine
  Regel auf »Rechnung« träfe auch die Werbemail, die so tut. Ordner und
  Absender sind belastbarer. Sollte jemand danach fragen, wäre es ein
  Zweizeiler in `FELDER` – die Frage ist nicht, ob es geht, sondern ob es
  gut ist.


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

- [x] **Aufbewahrungskategorien: das Einstufen gibt es jetzt.** (erledigt
  am 2026-08-28) `mailburg einstufen ARCHIV SUCHE KATEGORIE`, mit
  Journalvorgang `classify` und Trockenlauf ohne `--wirklich`. Belegt ist
  auch die Wirkung: Eine Mail von 2019 ist als Buchungsbeleg bis Ende
  2027 gesperrt, als Handelsbrief schon frei.

  **Auch in der Oberfläche:** *Post → Aufbewahrung festlegen …*, mit
  einem Fenster, das vorher sagt, wie viele Mails betroffen sind und wie
  lange sie danach geschützt sind. Nur im Geschäftsarchiv sichtbar.

  Die Frage, ob sich Handelsbrief und Buchungsbeleg automatisch
  unterscheiden lassen, bleibt offen und ist bewusst nicht angefasst: Ein
  Vorschlag, den der Anwender bestätigt, setzt voraus, dass er ihn
  beurteilen kann – und bei einer falschen Automatik merkt es niemand.

- [x] **Fälligkeitsbericht.** (erledigt am 2026-08-28) `mailburg faellig`
  und eine Nachfrage in der Oberfläche, einmal im Jahr ab dem 1. Mai.

  Der Stichtag geht auf Stephan zurück: »Dann kommt diese Anfrage nur
  einmal im Jahr.« Nicht ab dem 1. Januar, wenn die Fristen ablaufen –
  eine Meldung bei jedem Öffnen wird weggeklickt, ohne gelesen zu
  werden.

  **Auch im Privatarchiv**, ebenfalls seine Anregung, aber mit anderem
  Ton: keine Fristen, nur ein Hinweis auf Post älter als zehn Jahre, und
  ausdrücklich der Satz, dass Alter kein Grund zum Löschen ist.

- [x] **Auskunftsexport nach Art. 15 DSGVO.** (erledigt am 2026-08-28)
  `mailburg auskunft` und *Archiv → Auskunft nach DSGVO …*. Als ZIP mit
  den unveränderten `.eml` und einem Begleitblatt, nicht als PDF: Eine
  Mail als PDF zu drucken heißt, sie zu verändern.

  Das Begleitblatt nennt ausdrücklich, was MailBurg *nicht* entscheiden
  kann – Daten Dritter in denselben Nachrichten (Art. 15 Abs. 4) und die
  Vollständigkeit bei mehreren Adressen. Der Vorgang steht im Journal,
  wegen der Rechenschaftspflicht aus Art. 5 Abs. 2.

- [x] **Verfahrensdokumentation erzeugen.** (erledigt am 2026-08-28)
  `mailburg verfahrensdoku` und *Archiv → Verfahrensdokumentation …*.
  Sieben Abschnitte als Markdown; was MailBurg nicht wissen kann, steht
  als `[BITTE ERGÄNZEN]` da und wird beim Speichern gezählt.

  Aufgeführt werden nur die Postfächer *dieses* Archivs. Die Kontenliste
  gilt für das ganze Programm – wer zwei Archive führt, hätte sonst in
  beiden Dokumentationen dieselben Postfächer stehen, und in keiner der
  beiden stünde die Wahrheit.

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

- [x] **Was passiert, wenn jemand einen IMAP-Ordner umbenennt?**
  (nachgestellt und behoben am 2026-08-29) Die Vermutung stimmte: Der
  Ordner wurde zweimal geführt, jede Mail bekam einen zweiten Fundort,
  das Journal verdoppelte sich. Bei drei Mails waren es sechs Einträge
  statt drei; bei fünftausend entsprechend.

  Erkannt wird es über `UIDVALIDITY` – die bleibt beim Umbenennen
  gleich, so verlangt es RFC 3501. RFC 8474 (`OBJECTID`) wäre der
  sauberere Weg, kennen aber längst nicht alle Server.

  **Nur bei genau einem verschwundenen und genau einem neuen Ordner.**
  Zwei Ordner können dieselbe `UIDVALIDITY` tragen; der Standard
  verlangt Eindeutigkeit nur innerhalb eines Ordners über die Zeit. Im
  Zweifel geschieht nichts – dann wird eben doppelt gelesen, wie bisher.
  Ein falsch zusammengeführter Ordner wäre deutlich schlimmer.

- [ ] **Marken bleiben eine Momentaufnahme.** Ob eine Mail gelesen oder
  beantwortet war, wird beim Archivieren festgehalten und danach nie wieder
  angefasst. Für ein Archiv ist das vertretbar – die Frage ist, ob jemand
  das anders erwartet.

- [x] **Was passiert bei einem Archiv auf einer Platte, die zwischendurch
  weggeht?** (geprüft am 2026-08-28) Nachgestellt, indem der Archivordner
  mitten in einem Import von 3.000 Mails weggezogen wurde – für das
  Programm fast dasselbe wie eine abgezogene Platte.

  **Das Archiv bleibt heil.** 1.000 Mails abgelegt, Hash-Kette
  unversehrt, Journal und Ablage stimmen überein. Die Reihenfolge
  Ablage → Journal → Index hält, was sie verspricht. Am ursprünglichen
  Pfad entsteht auch kein Torso.

  **Die Meldung taugte nicht.** Es schlug ein nackter Python-Traceback
  durch – ein Wall aus Zeilen, der die einzige wichtige Frage nicht
  beantwortet: Ist mein Archiv jetzt kaputt? Jetzt steht dort, was
  passiert ist, dass nichts zu Schaden gekommen sein kann und was zu tun
  ist. Rückgabewert 4.

## Erledigtes

- [x] **Windows im Betrieb erprobt.** Erledigt am 2026-08-27, der erste
  echte Lauf überhaupt. MailBurg startet, die Oberfläche erscheint, der
  Assistent läuft durch, die Platzanzeige stimmt, und Passwörter landen
  in der Anmeldeinformationsverwaltung. Vier Fehler kamen dabei zutage –
  der Python-Platzhalter in `install.ps1`, eine falsche Fassungsnummer
  in `pyproject.toml`, ein grauer Weiter-Knopf ohne Begründung und ein
  Assistent, der die Postfächer keinem Archiv zuordnete. Alle behoben.

  Damit ist das Windows-Versprechen im README belegt statt behauptet.
  macOS bleibt unerprobt und ohne Aussicht auf ein Testgerät.

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
