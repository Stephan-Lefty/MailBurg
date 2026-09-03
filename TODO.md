[Deutsch](TODO.md) | [English](TODO.en.md) | [Übersicht](README.md) | [Änderungsprotokoll](CHANGELOG.md) | [Anleitungen](docs/README.md)

# TODO

Laufende Liste offener Punkte. Oben steht, was noch offen ist. Erledigtes wird
nicht gelöscht, sondern nach unten verschoben – mit dem Datum, an dem es fertig
wurde.

## Offen

### Aus dem dritten Nutzer-Feedback (2026-09-03)

Derselbe Anwender, der sich JMAP gewünscht hatte – er hat es an einem
eigens aufgesetzten **Stalwart** ausprobiert, mit 5.000 besorgten
Testmails. Sein Urteil: »JMAP funktioniert einwandfrei und das Teil ist
echt schnell. Für 200 Mails benötige ich weniger als 5 Sekunden.«

- [x] **Nach der Installation ließ sich MailBurg nicht aus der Konsole
  starten.** (2026-09-03) Seine Vermutung – »das liegt vermutlich an
  fish« – stimmte, und der Fehler lag bei uns, gleich doppelt.

  `install.sh` prüfte **seinen eigenen** Suchpfad, also den von bash, in
  dem es läuft. Viele Distributionen tragen `~/.local/bin` in
  `/etc/profile` ein, das fish nicht liest: bash findet den Ordner, das
  Skript schweigt, und in der Shell des Anwenders fehlt er trotzdem.

  Und der Hinweis nannte `~/.bashrc` – eine Datei, die weder fish noch
  zsh anfassen. **Ein Hinweis, der auf die falsche Datei zeigt, ist
  schlimmer als keiner**, denn wer die Zeile dort einträgt, sucht danach
  überall, nur nicht mehr im Suchpfad. Jetzt wird die Anmelde-Shell
  gefragt und die passende Zeile genannt (`fish_add_path`, `~/.zshrc`,
  `~/.bashrc`); vier Tests in `tests/test_install.py` führen den Block
  wirklich aus.

- [ ] **Zurückspielen als eigener Vorgang – Sicherung und Rückgabe
  entkoppeln.** Sein Wunsch für die Zukunft, und der größte offene Punkt
  aus allen drei Rückmeldungen: »Ich würde mir ein Restore wünschen, wie
  in MailStore Home. Dann wäre das mein 1. Wahl Backup-Tool. […] Also
  unabhängige Backups und Restores.«

  Zwei Beispiele nennt er selbst: vom Mailserver sichern und nach
  Thunderbird zurückspielen; aus einem Thunderbird-Profil sichern und
  per IMAP auf einen Server legen.

  **Was davon schon steht:** das Holen aus beliebigen Quellen (IMAP,
  JMAP, Thunderbird, Maildir, MBOX) und `core/rueckgabe.py` – dort ist
  ausdrücklich vorgesehen, dass das Ziel *nicht* die Herkunft sein muss.

  **Was fehlt, und das ist der eigentliche Punkt:** Heute geht die
  Rückgabe nur für **eine** markierte Nachricht in den **Posteingang**
  eines gewählten Kontos (`ui/zurueck.py`). Ein Restore im Sinne von
  MailStore wäre: eine Suche oder ein ganzer Postfachbaum als Menge,
  ein frei gewähltes Ziel – IMAP-Konto, Maildir, MBOX oder
  Thunderbird-Profil –, die Ordnerstruktur wahlweise erhalten, und ein
  Lauf, der sich abbrechen und fortsetzen lässt.

  **Dass es das geben soll, steht nicht in Frage.** Der Kopf von
  `core/rueckgabe.py` sagt es seit dem 26.08.: »Ein Archiv, aus dem
  nichts wieder herauskommt, ist ein Grab.« Was hier steht, ist die
  Liste dessen, was dazugehört – nicht ein Einwand.

  **Erstens weitet es die einzige Ausnahme.** MailBurg liest fremde
  Postfächer sonst nur (`EXAMINE`, `BODY.PEEK[]`); geschrieben wird
  ausschließlich beim Zurücklegen, auf Befehl, für einzelne benannte
  Nachrichten, nie im Hintergrund. Zehntausend Mails auf einen fremden
  Server zu schieben ist etwas anderes als eine – dafür braucht es eine
  Vorschau vorher, eine Bestätigung und einen Bericht darüber, was
  tatsächlich ankam.

  **Zweitens, und das ist der schwierige Teil: `APPEND` legt jedes Mal
  eine neue Kopie an.** Wer zweimal in dasselbe Postfach restauriert,
  hat alles doppelt, und der Server vergibt neue UIDs, an denen sich
  nichts wiedererkennen lässt. Der einzige belastbare Anker wäre die
  `Message-ID` – die müsste MailBurg vor dem Schreiben aus dem Ziel
  auslesen (`UID SEARCH HEADER Message-ID`), und bei zehntausend Mails
  ist das ein eigener Durchlauf. MailStore Home hat dasselbe Problem;
  dort fällt es nur seltener auf.

- [ ] **Sein Angebot: ein Testpostfach mit bis zu 500.000 Mails.**
  »Falls du ein Postfach für eigene Tests brauchst, sag Bescheid.« Er
  hat ein Stalwart aufgesetzt und 5.000 Testmails aus dem Netz
  hochgeladen – »kann bei Bedarf auf bis zu 500.000 Mails erhöhen«.
  Echte Post ist ausdrücklich keine dabei.

  **Das beantwortet zwei Fragen, die hier seit Wochen offenstehen** –
  ohne auf MailStore und die Windows-VM zu warten (siehe »Vertagt«):
  wie schnell die Suche bei einer halben Million Mails wirklich ist, und
  ob der Abruf über einen so großen Bestand durchhält.

  **Entscheidung liegt bei Stephan.** Zu bedenken: Ein fremder Server
  ist ein Zugang, den jemand anders verwaltet – die Zugangsdaten gehören
  in den Schlüsselbund und nicht ins Repo, und der Bestand belegt
  hochgerechnet rund 9 GB Suchindex plus Ablage.

### Aus dem zweiten Nutzer-Feedback (2026-09-03)

Fedora Silverblue, MailBurg in einer Toolbox, Umsteiger von Thunderbird
auf Evolution. Fünf Punkte, vier davon in der 1.2.0 erledigt.

- [ ] **Der PDF-Betrachter ließe sich einstellen.** Beim Rückmelder
  öffnete ein PDF-Anhang den Browser mit `localhost:8000` – einer
  Adresse, die bei ihm Paperless-ngx belegt. Sein Vorschlag: »Wenn
  MailBurg nicht selber PDF-Dokumente darstellen kann, dann sollte der
  PDF-Viewer konfigurierbar sein.«

  **Die Ursache ist aber eine andere, und das ändert die Frage.** Er
  läuft in einer Toolbox: Die Datei lag im `/tmp` des Containers,
  Firefox läuft außerhalb und sieht sie nicht – also zeigte es die
  letzte Sitzung. Seit der 1.2.0 liegen Anhänge im geschützten
  Cache-Ordner, und wenn das Öffnen scheitert, sagt MailBurg das mitsamt
  Pfad und dem Hinweis auf »Als Datei speichern«.

  **Erst nachfragen, dann bauen.** Ein eigenes Feld für den Betrachter
  wäre eine Einstellung, die auf jedem gewöhnlichen System niemand
  braucht. Ob es nach der 1.2.0 noch nötig ist, weiß nur er.

- [ ] **Gmail über OAuth2 hat er übersprungen** – »wegen der bekannten
  OAuth-Probleme«. Damit ist es der zweite Rückmelder, bei dem Gmail
  offen bleibt. Siehe den Punkt weiter unten.

### Aus dem ersten Nutzer-Feedback (Linux-Guides-Forum, 2026-09-01)

Der erste Rückmelder von außerhalb. Vier Punkte, drei davon sofort
behoben – der vierte ist Geschmack und braucht eine Entscheidung.

- [x] **Der Oberfläche fehlte Struktur.** (2026-09-01) Wörtlich: »Für
  meinen Geschmack fehlen da ein paar Rahmen oder farbliche
  Abhebungen.«

  Vier Bereiche heben sich jetzt ab: der Suchbereich oben, der
  Postfachbaum, der Kopf einer Nachricht und die Statuszeile. Dazu sind
  die Griffe der Teiler sichtbar – vorher wusste niemand, dass sich die
  Bereiche verschieben lassen.

  Alle Farben stammen aus der Systempalette; ein Wächtertest prüft das
  Stylesheet Hexwert für Hexwert. Gemessen: Kante gegen Inhalt 1,98 im
  hellen und 2,59 im dunklen Thema.

  **Dabei fiel auf, dass die Anleitung ein anderes MailBurg zeigte als
  das Programm** – `werkzeuge/screenshots.py` setzte das Stylesheet gar
  nicht.

- [x] **Die DBus-Meldung beim ersten Start.** (2026-09-01)
  `qt.qpa.services: Failed to register with host portal` –
  `setDesktopFileName` ist statisch und stand nach der Erzeugung der
  `QApplication`. Der zweite Registrierungsversuch scheiterte, weil die
  Verbindung schon eine Kennung hatte. Jetzt steht sie davor.

  Harmlos war die Meldung immer; sie stand aber als Erstes im Terminal,
  wenn jemand MailBurg zum ersten Mal startet.

- [x] **Der Knopf zur Ordnerwahl war zu übersehen.** (2026-09-01)
  Heißt jetzt »Ordner auswählen …«, hat ein Ordnersymbol und ist der
  Vorgabeknopf der Seite. Wo das Archiv liegt, ist die wichtigste
  Entscheidung des Assistenten – wer den Knopf nicht findet, nimmt den
  Vorschlag, statt zu wählen.

- [x] **Die Passwortfelder gingen unter.** (2026-09-01) Sie standen weit
  rechts vom Kontonamen, weil sich die Namensspalte dehnte. Jetzt stehen
  sie daneben, mit der Beschriftung »Passwort:« davor.

- [ ] **Gmail-Abruf schlug fehl.** Der Rückmelder schaut selbst nach
  (»das schau ich mir später mal an«), aber es lohnt sich, die Ursache
  zu erfahren: Gmail ist in der Liste unter »Noch nicht getestet« der
  wichtigste offene Punkt, und OAuth2 ist an einem echten Konto nie
  gelaufen. Nachfragen, sobald er sich meldet.

### Beim nächsten Mal zuerst

- [ ] **Das rote Wappen fehlt in der Weboberfläche.**
  `werkzeuge/server_logo.py` erzeugt es, `assets/server/` enthält es in
  allen Größen samt `.ico` – benutzt wird es an keiner einzigen Stelle.
  Die Anmeldeseite zeigt »MailBurg SERVER« als Text, ein Favicon gibt
  es nicht. Stephan hat am 2026-09-03 danach gesucht und es nicht
  gefunden; seit dem Tag steht es wenigstens über den beiden
  Anleitungen.

  **Was dafür fehlt:** eine Route, die `assets/server/icon-*.png`
  ausliefert. Bisher liefert der Dienst nur erzeugtes HTML – es gäbe
  also erstmals statische Dateien, und damit die Frage, ob sie aus dem
  Paket kommen (`importlib.resources`) oder von der Platte. Aus dem
  Paket, sonst fehlen sie in der `.exe`.

- [ ] **Die Fenstergrößen am echten Bildschirm nachsehen.** Am
  2026-08-31 hat Stephan in sechs Runden gemeldet, dass Text fehlt:
  erst in einem Auswahlfeld, dann in der Höhe, dann in der Breite. Jede
  Runde brachte einen echten Fehler zutage, aber die letzte konnte ich
  nicht mehr abschließend prüfen.

  **Der Grund, und er ist wichtig für den nächsten Anlauf:** Qt meldet
  im Offscreen-Betrieb »does not support propagateSizeHints«.
  Fenstergrößen sind dort nicht verlässlich zu messen – `werkzeuge/
  lesbarkeit.py` sieht sauber aus, und trotzdem kann es am echten
  Bildschirm klemmen. Was das Werkzeug findet, ist echt; was es *nicht*
  findet, ist damit nicht erledigt.

  Zu prüfen, mit vergrößerter Schrift (Strg++ mehrfach):

  1. *Was von selbst laufen soll* – Höhe und Breite, alle vier Absätze
     vollständig, kein Rollbalken bei gewöhnlicher Schrift.
  2. Die anderen acht Fenster, die das Werkzeug kennt.
  3. Die Menüs der Menüleiste beim Aufklappen.

  **Und die Regel dazu, von Stephan:** In der Standardgröße muss immer
  alles ohne Rollen lesbar sein. Der Rollbereich ist die Rückfalllinie
  für kleine Bildschirme, nicht der Normalzustand.

### Für die 1.2

- [ ] **macOS.** Tests und Einrichtung laufen dort in der CI durch,
  benutzt hat MailBurg dort noch niemand. Für ein Archivprogramm ist das
  zu wenig, um es zu empfehlen: Was beim Aufnehmen schiefgeht, fällt erst
  Jahre später auf. Seit der 1.0 sagt das README das auch so, und die
  Classifier in `pyproject.toml` nennen nur noch Linux und Windows.

  **Was fehlt, ist ein Gerät.** Zu prüfen wären dann: der Schlüsselbund
  (macOS statt gnome-keyring/ksecretd), Apple Mail als Quelle (`.emlx`),
  `launchd` für den Zeitplan – dafür gibt es bisher nur eine
  Beispieldatei in [docs/zeitsteuerung.md](docs/zeitsteuerung.md), nie
  gelaufen –, und ob die Oberfläche dort brauchbar aussieht.

  **Und die Frage nach dem `.dmg`.** Ohne Signatur meldet Gatekeeper das
  Programm als nicht überprüfbar; Anwender müssten es über einen
  versteckten Rechtsklick-Umweg starten. Ein Entwicklerkonto bei Apple
  kostet 99 $ im Jahr – das ist eine Entscheidung, keine technische
  Frage.

- [ ] **Die Verschlüsselung an einem echten Archiv erproben.** Gebaut und
  getestet ist sie seit dem 2026-08-31, aber noch nie hat jemand damit
  im Alltag gearbeitet. Zu prüfen, in dieser Reihenfolge:

  1. Ein kleines verschlüsseltes Archiv anlegen, ein paar Mails abrufen,
     schließen, öffnen, suchen, eine Nachricht zurückholen.
  2. **Den Notschlüssel wirklich benutzen** – nicht nur ausdrucken.
     Ein zweiter Weg hinein, den niemand je gegangen ist, ist keiner.
  3. Sichern, die Sicherung in ein neues Archiv einspielen, prüfen.
  4. Das Passwort wechseln und danach beides probieren: neues Passwort
     und Notschlüssel.
  5. Den Zeitplan mit hinterlegtem Passwort über Nacht laufen lassen.
     Das ist der Punkt, an dem ein Fehler am längsten unbemerkt bliebe.

  **Und dann die Frage, ob Stephans zwei laufende Archive umziehen.**
  Nachträglich verschlüsseln geht nicht; der Weg führt über eine
  Sicherung in ein neues Archiv, und dabei beginnt die Hash-Kette von
  vorn. Für das Geschäftsarchiv ist das eine Abwägung, keine
  Selbstverständlichkeit: Der Schnitt in der Nachweiskette will begründet
  sein, und das alte Archiv muss bleiben, solange Fristen laufen.

- [ ] **Was der Server nicht kann:** schreiben. Einstufen, Löschen und
  das Zurücklegen ins Postfach bleiben der Kommandozeile und dem Fenster
  vorbehalten. Das ist der Zuschnitt, nicht ein Mangel – die Vorgänge
  schreiben ins Journal, und dort muss vorher geklärt sein, wer sie
  auslösen darf. Steht hier, damit es eine Entscheidung bleibt und nicht
  ein Versehen wird.

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

- [ ] **Auch den Suchindex verschlüsseln.** Die offene Flanke der
  Archivverschlüsselung: Er liegt außerhalb des Archivs und enthält
  Betreff, Absender und Volltext im Klartext.

  Für den Anlass, um den es ging – Sicherung in der Cloud, verlorene
  Platte –, genügt der jetzige Zuschnitt, denn der Index wandert dort
  nicht mit. Auf einem Server liegt er aber neben dem Archiv, und dort
  hilft nur eine verschlüsselte Platte.

  **Warum es nicht einfach ist:** SQLite mit FTS5 braucht Klartext, um
  zu suchen. SQLCipher wäre der übliche Weg, ist aber ein zu
  kompilierendes Fremdpaket. Alles im Arbeitsspeicher zu halten, scheidet
  aus: 5.187 Mails ergeben 95 MB Index, 700.000 wären rund 13 GB.
  Feldweise zu verschlüsseln macht die Volltextsuche kaputt.

  Solange das offen ist, muss der Hinweis in `krypto.hinweis_suchindex()`
  stehen bleiben und in jeder Anleitung auftauchen. Eine Verschlüsselung
  mit einer Lücke, die niemand nennt, ist schlimmer als keine.

- [ ] **Weitere Mailquellen.** Outlook PST/OST über `libpff`, Apple Mail
  `.emlx`.

- [ ] **Pakete für alle drei Systeme.** `.deb` und AppImage für Linux,
  PyInstaller mit Inno Setup für Windows, `.app` und `.dmg` für macOS. Für
  macOS ist zu klären, wie mit Gatekeeper umgegangen wird, solange keine
  Signatur vorliegt.

### Offene Fragen

- [ ] **OAuth2 an einem echten Konto.** Geprüft ist der Ablauf nur gegen
  einen nachgebauten Anbieter auf dem eigenen Rechner. Stephans Konten
  liegen auf eigenen Servern und bei Proton – ein Microsoft-Konto zum
  Testen gibt es nicht.

  Zweite offene Frage: ob Googles Testmodus die Erneuerungs-Token
  wirklich nach sieben Tagen verfallen lässt. Falls ja, taugt OAuth2 bei
  Gmail nicht für den Zeitplan – die Anleitung rät dort deshalb weiterhin
  zum App-Passwort.

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
  gemessen ist es aber nicht.

  **Seit dem 2026-09-03 gibt es einen zweiten Weg dorthin**, und der
  hängt nicht an MailStore: Ein Anwender bietet ein Stalwart-Postfach
  mit bis zu 500.000 Testmails an. Siehe ganz oben unter »Aus dem
  dritten Nutzer-Feedback«.

- [ ] **Warum kommt das Startbild nicht in der `.exe` an?** Ausgebaut am
  2026-08-30, weil der Anlass wegfiel – nicht, weil die Frage beantwortet
  wäre. Wer sie wieder aufnimmt, findet die Spuren in
  `werkzeuge/mailburg.spec`: Das Bild war zuletzt einwandfrei, der Bau
  meldete »Building Splash«, und sichtbar wurde trotzdem nur ein leeres
  Fenster.

- [ ] **Marken bleiben eine Momentaufnahme.** Ob eine Mail gelesen oder
  beantwortet war, wird beim Archivieren festgehalten und danach nie wieder
  angefasst. Für ein Archiv ist das vertretbar – die Frage ist, ob jemand
  das anders erwartet.

### Vertagt – zum Test Mitte Oktober 2026

Stephan am 2026-08-31: »Alles was mit Windows Server, den 700.000
Mails zu tun hat, können wir auf Mitte Oktober dann zum Test
verschieben! Das kann ich vorher nicht testen!«

Beides ist gebaut oder vorbereitet – nur eben nie gelaufen. Bis zur
Prüfung steht es hier und nicht in der laufenden Liste.

- [ ] **Der Windows-Dienst.** `mailburg/server/windows_dienst.py` über
  pywin32, mit `mailburg[server-windows]`. Geschrieben nach dem Muster
  aus den pywin32-Beispielen, nachgeschlagen am 2026-08-31 – aber auf
  keinem Windows gelaufen.

  Zwei Befunde der Recherche, die die Wahl bestimmt haben: Die
  Aufgabenplanung startet ein Programm auch ohne angemeldeten
  Benutzer, hält es aber nicht am Leben – stürzt es ab, bleibt es
  unten. Und NSSM, der verbreitetste Wrapper, hat seit über einem
  Jahrzehnt kein stabiles Release mehr.

  **Beim ersten Einrichten** `mailburg server` von Hand danebenlaufen
  lassen, um die Einstellungen zu prüfen, bevor der Dienst dran ist.

- [ ] **Mails aus MailStore Home holen** – und damit der Lasttest an
  rund 700.000 Mails. Die Windows-VM steht seit dem 2026-08-27;
  MailStore Home läuft darin, kommt aber nicht an das Archiv heran:
  »Invalid crypt key«. Die Ursache ist ungeklärt, versucht wurde es
  bisher einmal, unter Zeitdruck.

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

  Offene Fragen von damals: Was bietet MailStore Home unter
  »Exportieren« an? Wie viele Mails sind es? An das MailStore-Format
  selbst wird nicht herangegangen – ein Archiv, das Mails aus einem
  nachgebauten Format zieht, kann die Bytegenauigkeit nicht garantieren.

  **Die Reihenfolge ist ohnehin die richtige** (Stephan, 2026-08-26):
  Erst muss sich zeigen, wie stabil MailBurg über Wochen läuft. Ein
  Lasttest an einem Bestand, den man nicht ersetzen kann, beweist wenig,
  solange die Grundlage nicht steht.

### Nicht anfassen

- **Die Zeitpläne stehen so, wie Stephan sie will** (2026-08-26): Abruf
  ins Geschäftsarchiv alle 30 Minuten, ins Privatarchiv einmal täglich,
  Sicherung beider monatlich mit zwei Ständen. Das ist keine
  Fehleinstellung, sondern Absicht – geschäftlich wartet jemand auf
  Antwort, privat eilt nichts.

## Erledigtes

### Am 2026-09-01

- [x] **JMAP als zweiter Abrufweg.** (2026-09-01) Von einem Anwender
  gewünscht. `sources/jmap.py`, Anleitung in [docs/jmap.md](docs/jmap.md).

  Der Gewinn ist `Email/changes`: Es beantwortet in einer Anfrage, was
  seit dem letzten Lauf dazugekommen ist. Über IMAP baut MailBurg das
  über die höchste bekannte Nachrichtennummer je Ordner nach – eine
  Näherung, bei der nachträglich einsortierte Mails durchrutschen.

  Ordner werden über ihre Rolle beurteilt, nicht über den Namen; der
  Gmail-Fall (`all` enthält alles doppelt) ist mit abgedeckt. Die
  Nachricht kommt byteweise über die Download-Adresse.

  **Offen war: ein echter Anbieter.** Geprüft war nur gegen
  `tests/fake_jmap.py`. **Erledigt am 2026-09-03** – der Anwender, der
  JMAP gewünscht hatte, hat rund 5.000 Nachrichten aus einem selbst
  betriebenen Stalwart geholt, 200 davon in unter fünf Sekunden.

  Fastmail bleibt offen und ist nicht dasselbe: Dort meldet man sich mit
  einer Zugriffsmarke an statt mit Benutzername und Passwort, und die
  Ordnerrollen kommen von einem fremden Anbieter. Ein kostenloses
  Probekonto gibt es dort.

- [x] **Eine verwaiste Sperre räumt MailBurg selbst weg** (2026-09-01),
  und wo es nicht sicher ist, fragt es. Vier Lagen: keine Sperre,
  verwaist auf diesem Rechner, laufender Vorgang, fremder Rechner – nur
  die letzte braucht eine Entscheidung, und die trifft der Anwender.

- [x] **Der Neuaufbau holt den erkannten PDF-Text zurück.**
  (2026-09-01) Der Kommentar in `erkennung.py` sagte seit jeher,
  welcher Schlüssel dafür da ist; abgeholt hat ihn niemand. Wer den
  Index neu baute, fand seine Scans nicht mehr – ohne Meldung.

### Am 2026-08-31

- [x] **Zeitstempel nach RFC 3161.** (2026-08-31)
  `mailburg siegel ARCHIV --zeitstempel freetsa` holt eine Beglaubigung
  von dritter Seite. Die Hash-Kette beweist die *Reihenfolge* der
  Einträge, nicht den Zeitpunkt – die Uhrzeit darin stammt vom eigenen
  Rechner, und die lässt sich stellen.

  Übertragen wird ein SHA-256, 32 Byte. Der Dienst erfährt, dass jemand
  um 14:03 Uhr *etwas* gestempelt hat. Trotzdem ausdrücklich
  einzuschalten und nirgends voreingestellt: MailBurg verspricht, sich
  nur mit den eingetragenen Mailservern zu verbinden.

  ASN.1 von Hand (`core/der.py`), keine Fremdbibliothek – geprüft
  gegen `openssl`, das die Anfragen liest und die Stempel verifiziert.
  Die Signatur des Dienstes prüft MailBurg nicht selbst; dafür
  schreibt `siegel --ausgeben` Stand und Stempel als Dateien heraus,
  mitsamt dem `openssl ts -verify`, der beides prüft.

  **Offen geblieben:** Es hat noch nie jemand einen echten Dienst
  gefragt. Geprüft ist gegen eine selbst aufgesetzte Zeitstempelstelle
  aus `openssl ts`. FreeTSA und die DFN-Stelle sind als Kurznamen
  hinterlegt, aber ungetestet – wie bei OAuth2 fehlt die Gegenprobe am
  echten Gegenüber.

- [x] **Die Lesbarkeit der Oberfläche.** (2026-08-31) Aus einer
  Meldung Stephans über ein zu schmales Auswahlfeld wurden sechs
  Runden und vier Fehlerklassen: Auswahlfelder so breit wie das Layout
  statt wie ihr Inhalt; aufgeklappte Listen, die bei 120 px blieben,
  während die Box mitwuchs; Dialoggrößen als geratene Zahlen; und
  umbrechende Texte, die zusammengedrückt wurden, weil Qt nur auf
  ausdrückliche Ansage nach der nötigen Höhe fragt.

  Dazu: Die Schriftgröße wirkte nur auf das Hauptfenster – Menüs,
  Dialoge und das Lesefenster sind eigene Fenster. Und **Strg++ tat
  gar nichts**, weil dasselbe Kürzel zweimal an derselben Aktion hing;
  Qt hält das für mehrdeutig und löst dann keines aus.

  `werkzeuge/lesbarkeit.py` macht die Prüfung wiederholbar.

- [x] **Die Archivverschlüsselung.** (2026-08-31) Der letzte offene
  Brocken der Server Edition. `mailburg anlegen … --verschluesseln` oder
  das Häkchen im Assistenten; verschlüsselt werden Mails und Journal,
  also alles im Archivordner. Anleitung:
  [docs/verschluesselung.md](docs/verschluesselung.md).

  Zwei Ebenen (Archivschlüssel, eingewickelt in Passwort *und*
  Notschlüssel), damit ein Passwortwechsel nicht 700.000 Dateien neu
  schreiben muss. Auch die Dateinamen sind verdeckt – der Klartext-Hash
  hätte verraten, ob eine bestimmte Mail im Archiv liegt.

  scrypt statt Argon2id, gegen den ursprünglichen Entwurf: Es steckt in
  `hashlib`, und ein Archivprogramm sollte in zwanzig Jahren ohne
  nachzuinstallierende Pakete an seine Schlüssel kommen.

  **Der Suchindex bleibt offen** – siehe oben unter »Auch den Suchindex
  verschlüsseln«. Das steht in jeder Anleitung dabei.

  Drei Fehler kamen dabei ans Licht, zwei in altem Code: die Kennwerte
  der Ableitung, die nicht zu dem passten, womit abgeleitet wurde; die
  abgebrochene Journalzeile, die das Archiv aussperrte; und wieder die
  Sperrdatei, die liegenblieb.

- [x] **Der Gesprächsverlauf.** (2026-08-31) Ging eine Sache mehrmals hin
  und her, zeigt MailBurg jetzt den ganzen Austausch: in der Vorschau als
  Zeile (*Gespräch: 7 Nachrichten – erste vom …, letzte vom …*), im
  Browser als anklickbare Liste unter der Nachricht.

  **Über die Kopfzeilen, nicht über den Betreff.** Jede Antwort trägt in
  `References` die Kennungen ihrer Vorgänger; die erste davon ist die
  Wurzel, und alles mit derselben Wurzel gehört zusammen. Der Betreff
  wechselt im Verlauf (»Re:«, »AW:«, »Fwd:«), und zwei Mails mit
  »Rechnung« im Betreff haben meistens nichts miteinander zu tun. Am
  Testarchiv belegt: Von vier Mails mit dem Betreff »Angebot« sind drei
  verkettet – der Verlauf findet genau diese drei.

  Die Kennungen stehen mal mit spitzen Klammern in der Mail und mal ohne.
  Wer sie übernimmt, wie sie kommen, baut Verläufe, die nie
  zusammenfinden; sie werden deshalb einheitlich abgelegt.

  Der Verlauf geht durch dieselbe Rechteprüfung wie die Suche – der Test
  in `tests/test_sicht.py` besteht darauf.

  **Bestehende Archive brauchen einen `mailburg neuaufbau ARCHIV`.** Die
  Angaben stehen in jeder Mail, wurden bis 0.12 aber nicht in den
  Suchindex übernommen (`SCHEMA_VERSION` 1 → 2); ein älteres Archiv
  öffnet sich erst danach. Die Spalte leer nachzurüsten wäre bequemer
  und gefährlicher gewesen – dann sähen Verläufe vollständig aus und
  wären halb. Verloren ist nichts, und der Befehl aus der Meldung kommt
  auch an ein Archiv mit veraltetem Index heran.

- [x] **Das Datum folgt jetzt auch dem Rest: Deutsch.** (2026-08-31)
  `ui/datum.py` fragte `QLocale` und damit die Systemeinstellung,
  während `ui/app.py` Qts eigene Beschriftungen **fest** auf Deutsch
  stellt. Heraus kam »Weiter« neben »8/24/2026«, auf einem Bauserver
  ohne Spracheinstellung »24 08 2026«.

  Stephans Entscheidung: alles auf Deutsch. Die Umrechnung liegt jetzt
  in `core/sprache.py` – damit Fenster und Weboberfläche dieselbe
  benutzen. Auch die Eingabefelder der Suchmaske folgen ihr, denn wer
  dort tippt, tippt in derselben Schreibweise wie in die Suchsprache
  (`seit:01.01.2025`).

  Der Test, der vorher festhielt, dass die Sprache das Format bestimmt,
  hält jetzt das Gegenteil fest.

### Am 2026-08-30

- [x] **Der Rückweg: „In Mailprogramm öffnen".** Damit stehen alle drei
  Wege aus dem Archiv. Rechte Maustaste auf eine Nachricht, und sie geht
  in Thunderbird, Outlook oder Apple Mail auf.

  Noch am selben Abend an Stephans Rechner bestätigt: »funktioniert
  1a«. Damit ist der Weg nicht nur gebaut, sondern gelaufen – unter
  Linux mit Thunderbird. Windows und macOS bleiben ungeprüft; dort
  entscheidet `os.startfile` beziehungsweise `open`, was passiert.

  **Die Frage war nie das Öffnen, sondern die Datei.** Eine `.eml` ist
  die vollständige Nachricht – Text, Anhänge, Adressen. In `/tmp` darf
  auf einem Mehrbenutzersystem jeder mitlesen; sie liegt deshalb im
  Zwischenspeicher des Benutzers, in einem Ordner mit `0700`, und die
  Datei selbst hat `0600`.

  **Verschwinden muss sie auch.** Sofort geht nicht – das Mailprogramm
  liest sie ja noch. Aufgeräumt wird zweimal: beim nächsten Öffnen
  alles, was älter als vier Stunden ist, und beim Beenden von MailBurg
  der ganze Ordner. Was sich nicht löschen lässt, weil Windows es
  festhält, bleibt bis zum nächsten Mal liegen und bricht nichts ab.

- [x] **Ausschlussregeln für private Mails.** Gebaut als
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

- [x] **Windows 11 auf echter Hardware geprüft.** Der erste Durchgang
  außerhalb der VM, mit einer frisch gebauten `.exe` aus Commit
  `70403ee`. Zeitplan, Sicherungsdialog und alles Übrige liefen –
  Stephan: »Ansonsten haben alle Dinge funktioniert.«

  Zwei Ergebnisse, die keine VM hätte liefern können:

  **Der Start dauert Sekunden, nicht zwanzig.** In der VM waren es 20–25
  Sekunden; davon ging fast alles auf die Virtualisierung, nicht auf das
  Auspacken der 160 MB. Damit ist auch die Frage erledigt, ob eine
  einzelne Datei der richtige Weg ist – sie ist es.

  **Das Startbild ist ausgebaut.** Es erschien auch auf echter Hardware
  nicht, sondern nur ein leeres Fenster: »es ist genau das selbe Fenster
  was ohne Inhalt aufgeht, wie in der VM«. Zwei echte Fehler waren zuvor
  behoben (16 Bit statt 8, `always_on_top`), das Bild war zuletzt
  einwandfrei – warum die Ressource nicht ankommt, steht jetzt unter den
  offenen Fragen.

  Ausgebaut wurde es trotzdem, und aus einem anderen Grund: Bei einem
  Start von wenigen Sekunden ist der Anlass weg. Ein Bild, das aufblitzt
  und verschwindet, verunsichert mehr als die Wartezeit, gegen die es
  antreten sollte – ein leeres erst recht. Die Begründung steht in
  `werkzeuge/mailburg.spec`, ein Test hält sie fest.

- [x] **Die `.exe` vor dem Prüfen neu bauen.** Am Vormittag lag ein
  Bildschirmfoto vor, das den alten Zeitplanfehler zeigte
  (»unerwarteter Knoten«, `RandomDelay`) – der steckte seit dem Vortag
  nicht mehr im Quelltext. Die gelaufene Datei war älter als die
  Korrektur.

  Das ist der teure Fehler dieser Art: Man prüft eine alte Fassung und
  hält den Befund für aktuell. Wer die nächste Prüfung ansetzt, baut
  vorher neu und schreibt sich den Commit auf, aus dem gebaut wurde.

  Dasselbe Bild brachte allerdings einen echten Fund: Die Meldung stand
  als »enth„lt« da statt »enthält«. Behoben, siehe Änderungsprotokoll.

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

- [x] **Die englische TODO nachgezogen.** Sie stammte aus der Zeit vor dem
  26.08. und führte Texterkennung und OAuth2 als offen, obwohl es beides
  längst gibt. Wer nur Englisch las, hielt MailBurg für weiter zurück, als
  es ist – die Umkehrung dessen, was `RECHTLICHES.md` verlangt, aber
  falsch ist beides. Bei der Gelegenheit stehen beide Listen wieder in
  derselben Ordnung.

### Am 2026-08-29

- [x] **OAuth2.** Anmeldung ohne App-Passwort nach RFC 7636 (PKCE), Marken
  im Schlüsselbund, Erneuerung mit Vorlauf beim Verbindungsaufbau, auf
  beiden Wegen bedienbar. [docs/oauth2.md](docs/oauth2.md). Was daran
  ungeprüft bleibt, steht oben unter den offenen Fragen.

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

  Sicherung: `…/MailBurg-vor-bildbereinigung-2026-08-29.bundle`, ausserhalb des Repos

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

- [x] **Was passiert, wenn jemand einen IMAP-Ordner umbenennt?**
  Nachgestellt und behoben. Die Vermutung stimmte: Der Ordner wurde
  zweimal geführt, jede Mail bekam einen zweiten Fundort, das Journal
  verdoppelte sich. Bei drei Mails waren es sechs Einträge statt drei;
  bei fünftausend entsprechend.

  Erkannt wird es über `UIDVALIDITY` – die bleibt beim Umbenennen
  gleich, so verlangt es RFC 3501. RFC 8474 (`OBJECTID`) wäre der
  sauberere Weg, kennen aber längst nicht alle Server.

  **Nur bei genau einem verschwundenen und genau einem neuen Ordner.**
  Zwei Ordner können dieselbe `UIDVALIDITY` tragen; der Standard
  verlangt Eindeutigkeit nur innerhalb eines Ordners über die Zeit. Im
  Zweifel geschieht nichts – dann wird eben doppelt gelesen, wie bisher.
  Ein falsch zusammengeführter Ordner wäre deutlich schlimmer.

### Am 2026-08-28

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

- [x] **Meldet MailBurg, wenn das Sicherungsziel fehlt?** Nachgestellt: Es
  meldete nichts. MailBurg legte den Ordner mit `mkdir -p` an, schrieb die
  Sicherung hinein und gab 0 zurück. Bei einem Einhängepunkt ohne
  eingehängten Datenträger wäre sie damit auf der Systemplatte gelandet –
  und aufgefallen wäre es erst, wenn man sie braucht.

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

- [x] **`konten zuordnung` zeigt Archivnamen, keine Kennungen.** Die
  Ausgabe ist zugleich nach Archiven gruppiert – die Frage lautet »was
  landet in meinem Geschäftsarchiv?«, und die beantwortete eine Liste, in
  der jedes Postfach seine Kennung wiederholt, nur mühsam. Namen, die
  MailBurg nicht auflösen kann, bleiben Kennungen: Ein Archiv auf einer
  abgezogenen Platte hat trotzdem Postfächer.

- [x] **Aufbewahrungskategorien: das Einstufen gibt es jetzt.**
  `mailburg einstufen ARCHIV SUCHE KATEGORIE`, mit Journalvorgang
  `classify` und Trockenlauf ohne `--wirklich`. Belegt ist auch die
  Wirkung: Eine Mail von 2019 ist als Buchungsbeleg bis Ende 2027
  gesperrt, als Handelsbrief schon frei.

  **Auch in der Oberfläche:** *Post → Aufbewahrung festlegen …*, mit
  einem Fenster, das vorher sagt, wie viele Mails betroffen sind und wie
  lange sie danach geschützt sind. Nur im Geschäftsarchiv sichtbar.

  Die Frage, ob sich Handelsbrief und Buchungsbeleg automatisch
  unterscheiden lassen, bleibt offen und ist bewusst nicht angefasst: Ein
  Vorschlag, den der Anwender bestätigt, setzt voraus, dass er ihn
  beurteilen kann – und bei einer falschen Automatik merkt es niemand.

- [x] **Fälligkeitsbericht.** `mailburg faellig` und eine Nachfrage in der
  Oberfläche, einmal im Jahr ab dem 1. Mai.

  Der Stichtag geht auf Stephan zurück: »Dann kommt diese Anfrage nur
  einmal im Jahr.« Nicht ab dem 1. Januar, wenn die Fristen ablaufen –
  eine Meldung bei jedem Öffnen wird weggeklickt, ohne gelesen zu
  werden.

  **Auch im Privatarchiv**, ebenfalls seine Anregung, aber mit anderem
  Ton: keine Fristen, nur ein Hinweis auf Post älter als zehn Jahre, und
  ausdrücklich der Satz, dass Alter kein Grund zum Löschen ist.

- [x] **Auskunftsexport nach Art. 15 DSGVO.** `mailburg auskunft` und
  *Archiv → Auskunft nach DSGVO …*. Als ZIP mit den unveränderten `.eml`
  und einem Begleitblatt, nicht als PDF: Eine Mail als PDF zu drucken
  heißt, sie zu verändern.

  Das Begleitblatt nennt ausdrücklich, was MailBurg *nicht* entscheiden
  kann – Daten Dritter in denselben Nachrichten (Art. 15 Abs. 4) und die
  Vollständigkeit bei mehreren Adressen. Der Vorgang steht im Journal,
  wegen der Rechenschaftspflicht aus Art. 5 Abs. 2.

- [x] **Verfahrensdokumentation erzeugen.** `mailburg verfahrensdoku` und
  *Archiv → Verfahrensdokumentation …*. Sieben Abschnitte als Markdown;
  was MailBurg nicht wissen kann, steht als `[BITTE ERGÄNZEN]` da und
  wird beim Speichern gezählt.

  Aufgeführt werden nur die Postfächer *dieses* Archivs. Die Kontenliste
  gilt für das ganze Programm – wer zwei Archive führt, hätte sonst in
  beiden Dokumentationen dieselben Postfächer stehen, und in keiner der
  beiden stünde die Wahrheit.

- [x] **Was passiert bei einem Archiv auf einer Platte, die zwischendurch
  weggeht?** Nachgestellt, indem der Archivordner mitten in einem Import
  von 3.000 Mails weggezogen wurde – für das Programm fast dasselbe wie
  eine abgezogene Platte.

  **Das Archiv bleibt heil.** 1.000 Mails abgelegt, Hash-Kette
  unversehrt, Journal und Ablage stimmen überein. Die Reihenfolge
  Ablage → Journal → Index hält, was sie verspricht. Am ursprünglichen
  Pfad entsteht auch kein Torso.

  **Die Meldung taugte nicht.** Es schlug ein nackter Python-Traceback
  durch – ein Wall aus Zeilen, der die einzige wichtige Frage nicht
  beantwortet: Ist mein Archiv jetzt kaputt? Jetzt steht dort, was
  passiert ist, dass nichts zu Schaden gekommen sein kann und was zu tun
  ist. Rückgabewert 4.

### Am 2026-08-27

- [x] **Windows im Betrieb erprobt.** Der erste echte Lauf überhaupt.
  MailBurg startet, die Oberfläche erscheint, der Assistent läuft durch,
  die Platzanzeige stimmt, und Passwörter landen in der
  Anmeldeinformationsverwaltung. Vier Fehler kamen dabei zutage – der
  Python-Platzhalter in `install.ps1`, eine falsche Fassungsnummer in
  `pyproject.toml`, ein grauer Weiter-Knopf ohne Begründung und ein
  Assistent, der die Postfächer keinem Archiv zuordnete. Alle behoben.

  Damit ist das Windows-Versprechen im README belegt statt behauptet.
  macOS bleibt unerprobt und ohne Aussicht auf ein Testgerät.

- [x] **Dunkles Thema: die Bereiche abgrenzen.** Nachgemessen ergab sich,
  dass es kein Farb-, sondern ein Kantenproblem war: Zwischen
  Fensterhintergrund und Inhaltsbereich liegt ein Kontrastverhältnis von
  1,15, in *jedem* Thema. Gezeichnet werden jetzt Rahmen in der
  Systemfarbe ``Mid`` – für alle Fenster, auch für die Gruppen der
  Ersteinrichtung, die Stephan als das Schlimmste benannt hatte.
  Platzhaltertexte bekommen im Dunkeln 70 Prozent Deckkraft statt Qts 50.

  **Am Gerät noch nicht geprüft**: Stephan sieht es sich später auf dem
  14-Zoll-Laptop an. Ein einheitlicher Grauton für beide Themen wurde
  durchgerechnet und verworfen – er käme auf 3,90 in beide Richtungen,
  während die abgeleitete Lösung im Dunkeln 7,05 erreicht.

- [x] **Scans mit riesigen Seitenmaßen.** Ein Scan aus der
  iPhone-Kamera-App misst 4507 × 6681 Punkte; bei 300 dpi wären das 523
  Megapixel, woran tesseract stumm erstickte. Die Auflösung richtet sich
  jetzt nach der Seitengröße. Passwortgeschützte PDF melden das, statt
  sich als »kein Text erkannt« auszugeben.

- [x] **Dokumente melden, aus denen kaum Text kam.** Erledigt heißt nicht
  gelesen – wer das nicht erfährt, hält sein Archiv später für
  unvollständig.

- [x] **Beim Öffnen steht die jüngste Nachricht oben**, für jedes Archiv
  gleich.

- [x] **Menüpunkt »Hilfe → Info«.** Urheber, Fassung und die beiden Wege
  für Fehlermeldungen.

### Am 2026-08-26

- [x] **Doppelte Anhänge nur einmal erkennen.** Ein Anhang, der an
  mehreren Mails hängt, ging mehrfach durch tesseract. Am
  Geschäftsarchiv gemessen: 222 gelesene Dokumente, aber nur 67
  verschiedene – 70 Prozent der Rechenzeit waren Abschriften. Verglichen
  werden jetzt die Bytes des Anhangs, über Läufe und Archive hinweg;
  `mailburg vorrat` holt das für schon erkannte Bestände nach.

- [x] **Grafische Oberfläche mit PySide6.** Dreispaltig, Suche beim
  Tippen, Vorschau mit Anhangsliste, Doppelklick öffnet die Nachricht in
  einem eigenen Fenster. Dazu Menüs für Archiv, Post, Suchen, Ansicht,
  Einstellungen und Hilfe, ein Handbuch in zehn Kapiteln und
  Schriftgrößen über Strg + / − / 0.

- [x] **Suchmaske nach dem Vorbild von MailStore.** Sie baut einen
  Suchausdruck zusammen und zeigt ihn an – die Maske kann nichts, was die
  Suchsprache nicht kann.

- [x] **Der Rückweg ins Postfach**, zwei von drei Wegen: „Zurücklegen…"
  per IMAP `APPEND` mit dem ursprünglichen Datum, auch in ein anderes
  Postfach als das der Herkunft, und „Als Datei speichern…" als `.eml`.
  Anhänge öffnen per Doppelklick.

- [x] **Bestehende Archive neu indizieren**, an beiden Archiven erprobt.
  Das Programm weist inzwischen von selbst darauf hin, wenn der Index
  leer ist, aber Dateien auf der Platte liegen.

- [x] **Texterkennung aus der Oberfläche.** Parallel über mehrere Kerne,
  Kernzahl wählbar, kleinste Dokumente zuerst, läuft beim Schließen des
  Fensters im Hintergrund weiter.

- [x] **Archivsicherung als eine komprimierte Datei**, mit Zeitplan über
  systemd-Timer, eine Einheit je Archiv.

### Am 2026-08-25

- [x] **Archivformat mit Hash-Kette.**
- [x] **Bytegenaue, inhaltsadressierte Ablage.**
- [x] **Grabsteine und Fristenschutz.**
- [x] **Suchindex mit zweitem Index über Dreizeichengruppen.**
- [x] **Mailparsing, robust gegen kaputte Kopfzeilen und Kodierungen.**
- [x] **Thunderbird-, Maildir- und MBOX-Quellen.**
- [x] **Kommandozeile und 121 Tests.**
- [x] **Rechtslage DE/AT/CH aufgearbeitet.**
- [x] **Suchsprache erweitert:** `datei:*.jpg` mit Platzhaltern über GLOB,
  `archiviert:` für den Zeitpunkt der Aufnahme ins Archiv (aus dem
  Journal, nicht von der Uhr), `groesse:>5MB`, `wichtigkeit:hoch` aus
  allen drei gebräuchlichen Kopfzeilen, sowie `cc:`, `bcc:` und `direkt:`
  über eine eigene Empfängertabelle.
- [x] **IMAP-Abruf mit Kontenverwaltung.** Passwörter im Schlüsselbund,
  inkrementell über `UIDVALIDITY` und den Höchststand aus dem Archiv,
  gescheiterte Mails werden vorgemerkt. `CONDSTORE` blieb außen vor: Es
  hilft nur beim Nachziehen geänderter Marken, und die archivieren wir
  ohnehin nur als Momentaufnahme.
