[Deutsch](CONTRIBUTING.md) | [Übersicht](README.md) | [Änderungsprotokoll](CHANGELOG.md) | [TODO](TODO.md) | [Anleitungen](docs/README.md)

# Mitmachen

Pull Requests sind willkommen, klassisch über Fork und Pull Request.

Diese Datei gibt es, seit ein Anwender am 21.09.2026 gefragt hat, ob das
überhaupt erwünscht ist. Ohne eine Antwort an einer festen Stelle müsste
sie jedes Mal neu geschrieben werden – und was hier erwartet wird, ist
nicht selbstverständlich.

## Womit anfangen

**Mit einem Issue, nicht mit Code.** Skizzieren Sie darin, was Sie
vorhaben. Das ist keine Hürde, sondern soll verhindern, dass Sie Arbeit
machen, die am Ende anders aussehen soll. Zwei Sätze genügen.

Offene Punkte stehen in [TODO.md](TODO.md), ganz oben die aktuellen.

## Was ein Beitrag mitbringen muss

**Tests.** MailBurg archiviert Geschäftspost, teils unter GoBD-Fristen.
Was schiefgeht, fällt oft erst Jahre später auf – und dann ist es nicht
mehr zu reparieren. Deshalb kann hier nichts übernommen werden, das nur
vorgeführt wurde.

Die Tests liegen in `tests/`, laufen mit `unittest`, und ihre
Methodennamen sind deutsch. So laufen sie vollständig:

```bash
PYTHONPATH="$PWD" QT_QPA_PLATFORM=offscreen \
  ~/.local/share/mailburg/venv/bin/python3 -m unittest discover -s tests
```

**Prüfen Sie, ob Ihr Test rot werden kann.** Nehmen Sie Ihre Änderung
versuchsweise zurück und sehen Sie nach, ob der Test es merkt. Ein Test,
der nicht rot werden kann, ist keiner – das ist hier mehrfach vorgekommen,
zuletzt am 21.09.2026.

**Keine echten Adressen, Domains, Server oder Pfade.** Auch nicht in
Testdaten, auch nicht in Screenshots, auch nicht in der Historie. Für
Beispiele gibt es `example.org`, `example.com` und `example.net` – nach
RFC 2606 genau dafür reserviert. Bilder bitte mit Texterkennung
nachsehen; ein Suchbegriff auf einem Screenshot verrät mehr, als man
denkt.

**Kommentare erklären das Warum, nicht das Was** – und nennen den Anlass
mit Datum, wenn es einen gab. Das ist im ganzen Repository so, und es ist
der Grund, warum der Code nach einem halben Jahr noch verständlich ist.
Ein Kommentar, der eine Zusage macht, schuldet einen Test dazu; sonst
wird er mit den Jahren falsch, ohne dass es auffällt.

Docstrings und Kommentare auf Deutsch, Bezeichner auf Englisch.

**Dokumentation in beiden Sprachen im selben Zug.** `README.md` und
`README.en.md`, `TODO.md` und `TODO.en.md` – in derselben Ordnung, damit
ein Abgleich möglich bleibt. Die Anleitungen in `docs/` sind deutsch.

**Ein neues Fenster gehört in die Lesbarkeitsprüfung.** Ein Test zählt
die Fenster der Oberfläche nach; wer eines baut und nicht einträgt,
bekommt einen roten Test. So prüfen Sie selbst:

```bash
QT_QPA_PLATFORM=offscreen python3 werkzeuge/lesbarkeit.py
```

Geprüft wird bei 9 bis 24 pt. Feste Pixelzahlen in einer Oberfläche,
deren Schrift sich einstellen lässt, sind ein Fehler, der auf sein
Auftreten wartet.

## Wo die Grenze liegt

**Oberfläche und Lesewege sehr gern.** Alles, was ins Archiv schreibt
oder an der Hash-Kette hängt, bleibt beim Betreuer – nicht aus
Misstrauen, sondern weil er dafür geradesteht, wenn ein Archiv nach acht
Jahren geprüft wird.

Konkret: `core/journal.py`, `core/store.py`, `core/krypto.py` und die
Aufnahmereihenfolge in `core/archive.py`. Vorschläge dazu bitte als
Issue.

## Lizenz

MailBurg steht unter der MIT-Lizenz. Wer beiträgt, stellt seinen Beitrag
unter dieselbe Lizenz. Eine gesonderte Vereinbarung gibt es nicht und
soll es nicht geben.

Ein Beitrag darf gern dabeistehen lassen, dass er mit Hilfe eines
Sprachmodells entstanden ist. Das ändert nichts an den Anforderungen
oben – aber es ist eine faire Angabe, und sie sollte normal werden.

## Warum das Ganze so ausführlich ist

Fast jede Regel hier stammt aus einem Fehler, der einmal passiert ist.
Die Begründungen stehen im [Änderungsprotokoll](CHANGELOG.md); wer wissen
will, warum eine Vorgabe so lautet, findet dort das Datum und den Anlass.
