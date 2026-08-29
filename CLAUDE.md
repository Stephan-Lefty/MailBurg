# CLAUDE.md

Landkarte des Repositorys. Ergänzt [README.md](README.md) und
[TODO.md](TODO.md), wiederholt sie nicht.

## Hier war Schluss (Stand 2026-08-29, Samstag)

**OAuth2 ist gebaut** – Ablauf, Bedienung auf beiden Wegen,
[docs/oauth2.md](docs/oauth2.md). PKCE nach RFC 7636, Marken im
Schlüsselbund, Erneuerung mit Vorlauf beim Verbindungsaufbau.

**Was offen bleibt, und das ist der wichtigste Satz hier:** Niemand hat
sich damit bisher bei einem echten Anbieter angemeldet. Geprüft ist der
Ablauf gegen einen nachgebauten Anbieter auf dem eigenen Rechner.
Stephans Konten liegen auf eigenen Servern und bei Proton – ein
Microsoft-Konto zum Testen gibt es nicht. In der Anleitung steht das
ausdrücklich; wer den Text ändert, soll diesen Satz stehen lassen,
solange er stimmt.

Zweite offene Frage: ob Googles Testmodus die Erneuerungs-Token
wirklich nach sieben Tagen verfallen lässt. Falls ja, taugt OAuth2 bei
Gmail nicht für den Zeitplan – die Anleitung rät dort deshalb weiterhin
zum App-Passwort.

**Noch offen aus der Verabredung:** Bilder. Stephan will sie zum
Schluss, wenn alles andere sauber ist – die Linux-Screenshots in
`docs/bilder/` sind vom 26.08. und zeigen den Assistenten vor den
Änderungen, für Windows fehlen SmartScreen, Hauptfenster und
Zeitplan-Dialog.

### Was der 28.08. gebracht hat

Der Tag zerfiel in zwei Hälften. Vormittags Windows: die `.exe` fertig
gebaut, in einer VM mit einem echten Postfach durchgespielt und dabei
sechs Fehler gefunden, die unter Linux nie aufgefallen wären – darunter
zwei, die den Zeitplan unbrauchbar gemacht hätten. Nachmittags die
GoBD- und DSGVO-Ecke: Einstufen, Fälligkeitsbericht, Auskunftsexport,
Verfahrensdokumentation.

**Die Lehre des Tages steht in den Prüfschritten des Bau-Workflows.**
Der Fehler, dass die `.exe` ihre eigene Kommandozeile nicht kannte, kam
nur ans Licht, weil ein Prüfschritt hängenblieb: Er wartete auf einen
Klick, den auf einem Bauserver niemand macht. Von Hand hätte ich das
Fenster gesehen und für einen Fehlstart gehalten.

**Und eine zweite:** Ein Test prüft, dass jeder Menüpunkt im Handbuch
erklärt ist. Er hat an diesem Tag dreimal zugeschlagen, jedes Mal zu
Recht. Solche Tests sind mehr wert als zehn, die Rechenwege prüfen.

## Hier war Schluss (Stand 2026-08-26, vormittags)

Der dritte Tag war der erste im echten Betrieb – und dabei ist ein
Dutzend Fehler aufgefallen, die keine Testsuite gefunden hätte. Das ist
die Lehre des Tages: **Diese Oberfläche musste einmal von jemandem
benutzt werden, der sie nicht gebaut hat.**

478 Tests, alles auf GitHub. Zwei Archive laufen produktiv auf der
externen Platte `Linux-Mobil`: ein Geschäftsarchiv (AT) mit sieben
Postfächern samt Proton über die Bridge, und ein Privatarchiv mit 1.557
Mails aus Thunderbirds lokalen Ordnern.

**Die drei lehrreichsten Fehler:**

1. **Ein Lambda an einem Signal aus dem Arbeitsfaden.** Qt kann einem
   Lambda keinen Faden zuordnen und ruft es deshalb sofort auf – im
   Arbeitsfaden. Die Zeilen darunter fassten Widgets an und öffneten
   einen modalen Dialog, der nie gezeichnet wurde, aber jede Eingabe
   schluckte. Für Stephan sah das so aus: Fenster verschiebbar, innen
   tot. Die Regel steht jetzt in `ui/arbeit.py`, ein Test verbietet
   Lambdas an diesen Signalen.
2. **`validatePage` warf sich selbst wieder an.** Sie prüft nebenläufig,
   sagt erst Nein und schickt die Seite weiter, sobald die Antworten da
   sind – was `validatePage` erneut aufrief. Sichtbar als flackernde
   Zustandsspalte; unsichtbar bekam der Mailserver bei jedem Umlauf drei
   frische Anmeldungen.
3. **`saveGeometry()` unter Wayland.** Dort darf ein Fenster seine
   Position nicht kennen; Qt schreibt Platzhalter, und
   `restoreGeometry()` stellt sie treu wieder her. Bei jedem Start
   dasselbe 720×720. Größe wird jetzt als Zahl gespeichert.

**Was als Prüfmuster bleibt:** Zustand, der zu früh gesichert wird, ist
falsch – `saveState()` beim Aufbau hält die Breite eines Fensters fest,
das seine Größe noch nicht hat. Und was der Anwender sieht, muss aus
derselben Quelle stammen wie das, was gilt: Der Postfachbaum addierte
Fundorte, die Statuszeile zählte Mails, und beide behaupteten eine
Gesamtzahl.

**Neu an diesem Tag:** Handbuch mit Kapiteln (`ui/hilfe.py`, ein Test
liest die Menüpunkte aus dem echten Menü), Hintergrundabruf aus der
Oberfläche (`core/zeitplan.py`), der Weg zurück ins Postfach
(`core/rueckgabe.py`, `ui/zurueck.py`), sortierbare Trefferliste,
taggenaue Suche mit `seit:`/`bis:`/`am:`.

**Am Nachmittag kam dazu:** Sicherung als eine Datei samt Zeitplan,
Anleitungen mit erzeugten Bildern (`werkzeuge/screenshots.py`),
Menü »Einstellungen«, Schriftgröße einstellbar, parallele Texterkennung.
Version 0.9.0 ist getaggt.

**GuideOS läuft.** Debian mit Cinnamon, apt-Zweig, gnome-keyring – die
zweite Umgebung, die für 1.0 fehlte. Zwei Befunde von dort: Der
Installer schwieg zehn Minuten, während pip PySide6 holte (`-q`), und
im dunklen Thema sind die Kontraste zu schwach. Ersteres behoben,
Zweites teilweise – die Linkfarbe stimmt jetzt, die Schriftgröße lässt
sich einstellen, der Rest kommt vom System-Thema.

**Offen und als Nächstes dran:**

1. **Dunkles Thema auf kleinen Bildschirmen.** Stephans Urteil: „alles
   relativ dunkel, auf 14 Zoll schlecht lesbar, die Unterschiede
   zwischen Hintergrund, Text, Menüs und Links kaum zu erkennen."
   Schriftgröße und Linkfarbe sind gemacht; die Abgrenzung der Bereiche
   noch nicht.
2. **Messung der parallelen Texterkennung** an 431 echten Dokumenten.
   Erwartet: aus einer Stunde werden fünfzehn Minuten.
3. **700.000 Mails** aus dem MailStore-Archiv der Firma. Gerechnet: 2,5
   bis 4 Stunden Import, ~170 GB. Der unbekannte Teil ist, wie MailStore
   die Daten herausgibt – dort würde es scheitern, nicht bei MailBurg.

## Vom zweiten Tag (Stand 2026-08-25, spätabends)

Der zweite Tag ging fast vollständig in die Oberfläche. Sie steht jetzt:
Einrichtungsassistent, Hauptfenster mit Suche und Vorschau, Startbefehl
`mailburg-gui`, Menüeintrag. 322 Tests, alles auf GitHub.

**Offen und als Nächstes dran:**

1. **Der Absturz bei falschen Passwörtern ist nicht gefunden.** Stephan
   hat absichtlich falsche eingegeben, die Oberfläche verschwand
   kommentarlos. Nachgestellt ließ er sich nicht – der reine Fehlerweg
   läuft sauber durch. Eingebaut ist jetzt ein Ausnahmehaken, der
   Programmfehler anzeigt statt sie zu verschlucken; beim nächsten Mal
   sollte also eine Meldung kommen. **Verdacht:** ein QThread, der
   weggeräumt wird, während er noch läuft – klassischer Qt-Absturz, der
   sich nicht als Python-Ausnahme zeigt. Zu prüfen wäre die
   Läuferverwaltung in `ui/assistent.py`, besonders wenn dieselbe Zeile
   zweimal geprüft wird (Zertifikatsvorschlag).
2. Die Oberfläche ist noch nie im Alltag gelaufen, nur in Durchgängen.
3. `mailburg abgleich` fehlt weiterhin – siehe unten.

**Was Stephan an der Oberfläche wichtig war** (gilt für alles Weitere):
Die Ersteinrichtung ist der Moment, in dem Vertrauen entsteht. Lieber
ausführlich als knapp, Fachjargon vermeiden (»meldet nichts nach Hause«
sagt niemandem etwas), keine Formulierung, die Misstrauen voraussetzt,
und nichts behaupten, was die Oberfläche nicht auch zeigt – ein Text,
der Nextcloud verspricht, während nur ein Pfadfeld dasteht, ist eine
halbe Zusage.

## Vom ersten Tag (Stand 2026-08-25 abends)

Alles Committete läuft, 232 Tests grün, alles auf GitHub. Unterbrochen
mitten in einem Arbeitsgang – **angefangen und nicht zu Ende gebracht:**

- **Doku zu Proton und zur Übernahme fehlt noch.** Der Code steht
  (`konten uebernehmen`, `--proton`, `--bruecke`), aber in
  `docs/postfaecher-einrichten.md` steht nichts davon. Dort gehört hin: die
  Bridge muss laufen, sie erzeugt ein eigenes Passwort (das Proton-Kennwort
  taugt nicht), sie braucht ein bezahltes Abo, und ohne laufende Bridge
  scheitert jeder Abruf. Ebenso ein Absatz zu `konten uebernehmen` samt der
  Begründung, warum Passwörter nicht mit übernommen werden.
- **CHANGELOG.md ist für beides noch nicht nachgezogen** – der Abschnitt
  „Unveröffentlicht" endet beim laufenden Abruf.
- **`docs/postfach-entlasten.md` ist verlinkt, aber existiert nicht.**
  `docs/zeitsteuerung.md` verweist darauf.

**Als Nächstes besprochen, noch nicht angefangen:**

1. **`mailburg abgleich`** – der wichtigste offene Punkt. Er soll belegen,
   dass alle Mails vor einem Stichtag im Archiv sind, *bevor* der Mailclient
   sie auf dem Server wegräumt. Ohne ihn ist das Aufräumen in Thunderbird
   eine Hoffnung. Gedachter Weg: je Ordner `UID SEARCH BEFORE <datum>`, jede
   gefundene UID gegen die Fundorte im Index halten, Bericht ausgeben.
   Danach `docs/postfach-entlasten.md` mit dem ganzen Ablauf.
2. **Erprobung an einem echten Postfach.** Der Abruf ist bisher nur gegen
   `tests/fake_imap.py` gelaufen. Stephan hat Konten bei Proton (Bridge auf
   1143), eines auf 993 und sechs auf 143 – gute Gelegenheit.

**Entschieden und nicht mehr zu diskutieren:** kein Passwort beim
Programmstart. Ohne Archivverschlüsselung wäre es Sicherheitstheater (die
Mails liegen als Dateien im Ordner) und machte den Abruf im Hintergrund
unmöglich. Ein Passwort gehört an die Verschlüsselung, und dann pro Archiv.

**Veröffentlichung: noch nicht.** Das Repo bleibt privat, bis der Abruf an
echten Postfächern gelaufen ist. Der Grund ist nicht die Codequalität,
sondern dass Fehler in einem Archivprogramm unbemerkt und unumkehrbar sind:
Was nicht geholt wurde, fällt erst Jahre später auf. Bisher ist alles nur
gegen `tests/fake_imap.py` gelaufen – also gegen meine eigenen Annahmen.

**Zwei Testumgebungen, die Stephan hat.** Sie sollen Verschiedenes abdecken:

- *Manjaro / KDE Plasma / Wayland* – der Echtbetrieb. Acht Konten in
  Thunderbird (eines über die Proton Bridge auf 1143, eines auf 993, sechs
  auf 143), der große Altbestand, der laufende Abruf. Schlüsselbund ist hier
  **ksecretd**, nicht gnome-keyring.
- *GuideOS (Debian 13) / Cinnamon* – die andere Hälfte: der apt-Zweig von
  `install.sh`, gnome-keyring, und der **manuelle** Weg über
  `konten hinzufuegen` ohne Thunderbird-Übernahme. Den ist noch nie jemand
  gegangen. Mit Evolution als Client käme die Maildir-Quelle an echte Daten.
- *Beide zusammen* – endlich prüfbar, was unter „Noch nicht getestet" steht:
  Sperrdatei bei zwei Rechnern an einem Archiv, Index-Neuaufbau auf dem
  zweiten, Nextcloud mit laufendem Synchronisationsclient.

**Kein macOS-Testgerät vorhanden, Windows ebenfalls nicht bestätigt.** Das
README behauptet „Läuft unter Linux, Windows und macOS". Geprüft ist davon
nur, dass Tests und Einrichtung in der CI durchlaufen – der Betrieb auf keiner
der beiden. Und selbst das stimmte bis zum 26.08.2026 nicht: Unter Windows
scheiterte in Wahrheit *jeder* Test, weil das Journal `fsync` auf einem nur
lesend geöffneten Deskriptor aufrief. Die Läufe waren rot, nur sah es niemand. Vorschlag lag Stephan vor, ist **noch nicht entschieden**: den Satz
auf das herunterziehen, was tatsächlich erprobt ist. Passt zur Haltung des
Projekts, nichts zu behaupten, was nicht belegt ist (siehe RECHTLICHES.md).

## Aufbau

```
mailburg/
├── core/
│   ├── archive.py     hält alles zusammen; Anlegen, Öffnen, Aufnehmen, Löschen, Prüfen
│   ├── journal.py     das Protokoll mit der Hash-Kette – das Herzstück
│   ├── store.py       inhaltsadressierte Ablage der Mails
│   ├── index.py       SQLite mit FTS5, zwei Volltextindizes
│   ├── importer.py    der Archivierungslauf, mit Prozesspool für Anhänge
│   ├── accounts.py    Postfächer und Passwörter (Schlüsselbund)
│   ├── sync.py        UIDVALIDITY und vorgemerkte Nachzügler je Ordner
│   ├── retention.py   Aufbewahrungsfristen DE/AT/CH, rein rechnend
│   ├── compress.py    Zstandard mit Rückfall auf LZMA
│   └── paths.py       Verzeichnisse je Betriebssystem
├── extract/message.py Mails zerlegen; pdf.py, office.py, text.py für Anhänge
├── search/query.py    Suchausdruck -> SQL
├── sources/           base.py (Schnittstelle), local.py (Thunderbird/Maildir/MBOX),
│                      imap.py (Postfächer)
├── ui/                die Oberfläche: hauptfenster, assistent, konten,
│                      suchmaske, vorschau, hilfe, zeitplan, sichern,
│                      einstufen, fristen, auskunft, anmelden
└── __main__.py        Kommandozeile

install.sh / install.ps1   Einrichtung; laufen in der CI wirklich durch
pyproject.toml             Paket und der Befehl "mailburg"
docs/                      Anleitungen für Anwender
```

## Regeln, die aus Fehlern stammen

**Das Journal ist die Wahrheit, der Index ist Beiwerk.** Jede Information, die
zum Wiederaufbau nötig ist, muss im Journal stehen. Beim ersten Entwurf bekam
ein zweiter *Fundort* derselben Mail keinen Journaleintrag, weil die Datei ja
schon da war – damit ging beim Neuaufbau der zweite Ordner verloren.
Protokolliert wird der Fundort, nicht die Datei.

**Mails werden bytegenau abgelegt.** Keine geglätteten Zeilenenden, keine
reparierten Kopfzeilen. Sonst ist die DKIM-Signatur hinüber und die
Unveränderbarkeit dahin. Das heißt auch: Dieselbe Rundmail an drei Adressen
liegt dreimal auf der Platte, weil sich die `Received:`-Zeilen unterscheiden.
Das ist Absicht.

**Der Index gehört nicht ins Archiv.** SQLite auf einem synchronisierten
Laufwerk geht kaputt. Er liegt unter `paths.index_path()`, benannt nach der
Archivkennung – nicht nach dem Pfad, damit er eine umgehängte externe Platte
überlebt.

**Reihenfolge beim Aufnehmen:** erst `store.put()`, dann Journal, dann Index.
Andersherum entstünde bei einem Absturz ein Eintrag ohne Inhalt – und der sieht
aus wie eine Manipulation.

**Die CI läuft je Push nur auf Linux.** Seit dem 26.08.2026 ist das
Repository öffentlich, Actions-Minuten kosten dort nichts mehr. Die Regel
bleibt trotzdem – sie stammt aus der Zeit davor und hat einen Grund, der
noch gilt: GitHub rundet *jeden einzelnen Job* auf volle Minuten auf, rechnet macOS zehnfach und
Windows zweifach. Die erste Fassung startete dreizehn Jobs je Push und
verbrauchte an einem einzigen Arbeitstag das Monatskontingent des Kontos
(1.800 von 2.000 Minuten). Deshalb: ein Job je Push, alle Schritte darin
gebündelt, die teuren Systeme montags. Wer hier einen Job hinzufügt, sollte
vorher rechnen – ein zusätzlicher macOS-Job kostet zehn Minuten, auch wenn er
nach neun Sekunden fertig ist.

**Keine AGPL- oder GPL-Abhängigkeiten.** Das Projekt ist MIT und soll als
Binärpaket verteilt werden. Also PySide6 statt PyQt6, pypdf statt PyMuPDF.

**`fsync` nicht pro Eintrag.** Bei hunderttausend Mails am Stück ist das der
Flaschenhals. `journal.flush()` am Ende eines Durchlaufs und vor jedem Siegel.

**Das Postfach wird nur gelesen.** `EXAMINE` statt `SELECT`, `BODY.PEEK[]`
statt `BODY[]`. Beides zusammen sorgt dafür, dass ungelesene Post ungelesen
bleibt. Wer eines davon vergisst, macht aus einem Archivprogramm ein Programm,
das fremde Postfächer verändert.

**Der Höchststand für den nächsten Abruf wird nicht mitgeschrieben.** Er kommt
aus `index.max_uid()`, also aus dem, was *tatsächlich* im Archiv liegt. Eine
mitgeschriebene Zahl wäre nach einem Abbruch mitten im Ordner falsch – sie
stünde auf der zuletzt geholten Mail, nicht auf der zuletzt abgelegten, und
alles dazwischen fehlte dauerhaft. Deshalb steht in `core/sync.py` nur, was
der Index nicht wissen kann: `UIDVALIDITY` und die Nachzügler.

**Eine gescheiterte Mail muss vorgemerkt werden.** Sonst zieht der Höchststand
an ihr vorbei und sie fehlt für immer, ohne Spur. Das ist der Grund, warum
`importieren()` dem Fehler-Rückruf die ganze `RawMessage` gibt und nicht nur
den Ordner – ohne die UID lässt sie sich nicht wieder anfordern.

**`UID n:*` liefert immer mindestens eine UID.** Auch wenn die höchste
vorhandene kleiner als `n` ist; so steht es in RFC 3501. Ohne Nachfiltern holt
jeder Abruf die zuletzt archivierte Mail erneut.

**Gmails »Alle Nachrichten« gehört nicht ins Archiv.** Der Ordner (`\All` nach
RFC 6154) enthält sämtliche Mails ein zweites Mal. Auf der Platte gäbe das
keine doppelte Datei, wohl aber einen zweiten Fundort je Mail im Journal.

## Lizenzen und Recht

Im README und überall sonst gilt: MailBurg **unterstützt** revisionssicheren
Betrieb, es **stellt ihn nicht her**. Keine Software kann GoBD-konform sein –
wer das behauptet, macht sich angreifbar. Die Belege dafür stehen in
[RECHTLICHES.md](RECHTLICHES.md).

## Gepflogenheiten

- Docstrings und Kommentare auf Deutsch, Bezeichner auf Englisch.
- Kommentare erklären das *Warum*, nicht das *Was*.
- Tests mit `unittest` in `tests/`, Methodennamen auf Deutsch.
- Version steht in `mailburg/__init__.py`, sonst nirgends.
- Fristen und Jahreszahlen stehen ausschließlich in `core/retention.py`.

## Noch nicht getestet

- ~~Verhalten bei einem Archiv auf einem Laufwerk, das während des Betriebs
  verschwindet.~~ Am 28.08.2026 nachgestellt: Das Archiv bleibt heil
  (1.000 Mails, Hash-Kette unversehrt), die Meldung war ein nackter
  Traceback und ist behoben.
- Zusammenspiel mit einem laufenden Nextcloud-Client.
- Große Bestände: gemessen wurde an 5.187 Mails, nicht an einer halben Million.
- **Gmail und Exchange.** Der Abruf gegen echte Server läuft seit dem
  26.08.2026 im Alltag – acht Postfächer, darunter Proton über die Bridge,
  und am 28.08. auch unter Windows. Alle liegen aber bei denselben zwei
  Anbietern. Ungeprüft bleiben die Eigenheiten von Gmail (Etiketten statt
  Ordner), Exchange (eigenwillige LIST-Antworten) und Servern, die bei zu
  vielen UIDs in einer Zeile aussteigen.
- **OAuth2 an einem echten Konto.** Siehe ganz oben: Der Ablauf ist nur
  gegen einen nachgebauten Anbieter geprüft.
