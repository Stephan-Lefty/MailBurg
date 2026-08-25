# CLAUDE.md

Landkarte des Repositorys. Ergänzt [README.md](README.md) und
[TODO.md](TODO.md), wiederholt sie nicht.

## Hier war Schluss (Stand 2026-08-25 abends)

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
├── ui/                noch leer – kommt mit PySide6
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

- Verhalten bei einem Archiv auf einem Laufwerk, das während des Betriebs
  verschwindet.
- Zusammenspiel mit einem laufenden Nextcloud-Client.
- Große Bestände: gemessen wurde an 5.187 Mails, nicht an einer halben Million.
- **Der Abruf gegen einen echten IMAP-Server.** Geprüft ist er gegen den
  nachgebildeten Server in `tests/fake_imap.py`. Der hält sich an RFC 3501 –
  echte Server tun das mit Eigenheiten. Besonders zu beobachten: Gmail
  (Etiketten statt Ordner), Exchange (eigenwillige LIST-Antworten) und Server,
  die bei zu vielen UIDs in einer Zeile aussteigen.
