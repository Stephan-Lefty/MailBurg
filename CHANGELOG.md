[Deutsch](CHANGELOG.md) | [Übersicht](README.md) | [TODO](TODO.md)

# Änderungsprotokoll

Alle nennenswerten Änderungen an MailBurg stehen hier.

Das Format folgt [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
die Versionsnummern folgen [Semantic Versioning](https://semver.org/lang/de/).

## [Unveröffentlicht]

### Neu

- **IMAP-Abruf.** Mails werden direkt aus dem Postfach geholt, für beliebig
  viele Konten. Das Postfach bleibt dabei unangetastet: Ordner werden nur
  lesend geöffnet (`EXAMINE`) und Mails mit `BODY.PEEK[]` geholt, damit
  ungelesene Post ungelesen bleibt.
- **Inkrementeller Abruf.** Nach dem ersten Lauf wird nur noch geholt, was
  dazugekommen ist. Der Höchststand wird nicht mitgeschrieben, sondern aus dem
  Archiv abgelesen – so ist ein Abbruch mitten im Ordner folgenlos. Ändert der
  Server seinen `UIDVALIDITY`-Wert, wird der Ordner vollständig neu gelesen.
- **Vormerkung gescheiterter Mails.** Eine Nachricht, an der sich MailBurg
  verschluckt, wird notiert und beim nächsten Lauf erneut angefordert. Ohne das
  zöge der Höchststand an ihr vorbei und sie fehlte für immer im Archiv, ohne
  dass es jemand bemerkte.
- **Kontenverwaltung** mit `konten liste`, `konten hinzufuegen`,
  `konten entfernen` und `konten pruefen`. Passwörter liegen im Schlüsselbund
  des Betriebssystems, nie in einer Konfigurationsdatei; in der Kontenliste
  steht nur, wo ein Postfach liegt und wie es heißt.
- **Ordnernamen im abgewandelten UTF-7** nach RFC 3501 werden aufgelöst, sodass
  aus `Entw&APw-rfe` wieder „Entwürfe" wird. Fremde Trennzeichen werden auf `/`
  vereinheitlicht.
- **Sonderordner bleiben draußen.** Papierkorb, Spamverdacht und Entwürfe nach
  Namen und nach den Merkmalen aus RFC 6154. Bei Gmail auch »Alle Nachrichten«,
  das sonst jede Mail ein zweites Mal ins Journal brächte.
- **Befehl `abrufen`**, geeignet für die Zeitsteuerung, mit `--konto`,
  `--ordner` und `--voll`.
- **64 weitere Tests**, darunter ein nachgebildeter IMAP-Server. Geprüft wird
  auch die Eigenheit aus RFC 3501, dass `UID n:*` immer mindestens die höchste
  UID liefert – wer das übersieht, holt bei jedem Lauf dieselbe Mail erneut.

### Geändert

- `importieren()` übergibt dem Fehler-Rückruf jetzt die ganze Nachricht statt
  nur ihren Ordner. Der IMAP-Abruf braucht die UID, um die gescheiterte Mail
  vormerken zu können.

## [0.1.0] – 2026-08-25

Erste Fassung. Der Unterbau steht; Oberfläche und IMAP fehlen noch.

### Neu

- **Archivformat.** Ein Archiv ist ein Verzeichnis mit `archive.json`, `mail/`
  und `meta/`. Jede Mail liegt als einzelne, gepackte Datei, benannt nach dem
  SHA-256 ihres Inhalts, sortiert nach Monat.
- **Bytegenaue Ablage.** Mails werden unverändert gespeichert – keine
  geglätteten Zeilenenden, keine reparierten Kopfzeilen. Damit bleibt eine
  DKIM-Signatur prüfbar.
- **Journal mit Hash-Kette.** Jeder Eintrag trägt den Hash seines Vorgängers.
  Nachträgliche Änderungen, entfernte Einträge und untergeschobene Mails fallen
  bei der Prüfung auf.
- **Grabsteine statt Löschen.** Der Inhalt verschwindet, der Vorgang bleibt
  protokolliert – mit Zeitpunkt, Verursacher und Grund.
- **Siegel** über den Stand des Journals, mit vorgesehenem Feld für einen
  Zeitstempel nach RFC 3161.
- **Zwei Betriebsarten.** Privatarchiv ohne Fristen, Geschäftsarchiv mit
  Hash-Kette, Fristenschutz und Protokoll.
- **Aufbewahrungsfristen** für Deutschland (6/8 Jahre), Österreich (7) und die
  Schweiz (10), gerechnet ab Ende des Kalenderjahres. Sonderfall BaFin
  berücksichtigt.
- **Suchindex** mit SQLite und FTS5, außerhalb des Archivs abgelegt und
  jederzeit vollständig daraus neu erzeugbar.
- **Zweiter Index über Dreizeichengruppen**, damit `betreff:rechnung` auch
  „Schlussrechnung" findet, und mit Umlautnormalisierung, damit `von:muller`
  auch „Müller" findet.
- **Deutsche Suchsprache**: `von:`, `an:`, `betreff:`, `text:`, `inhalt:`,
  `hat:anhang`, `typ:`, `jahr:`, `konto:`, `ordner:` sowie Ausschluss per `-`.
- **Mailquellen**: Thunderbird-Profile mit allen Konten und Ordnern, Maildir und
  MBOX-Dateien. Thunderbird-Profile werden auf allen drei Systemen selbst
  gefunden, auch bei Flatpak- und Snap-Installationen.
- **Sperrdatei**, damit nicht zwei Rechner gleichzeitig in ein Archiv in der
  Cloud schreiben.
- **Kommandozeile** mit `anlegen`, `importieren`, `suchen`, `pruefen`,
  `neuaufbau`, `siegel`, `info` und `suchhilfe`.
- **121 Tests**, darunter der Nachweis, dass eine Fälschung auch dann auffällt,
  wenn der Fälscher den Eigenhash mitrechnet.
- [RECHTLICHES.md](RECHTLICHES.md) zur Rechtslage in Deutschland, Österreich und
  der Schweiz.

[Unveröffentlicht]: https://github.com/Stephan-Lefty/MailBurg/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Stephan-Lefty/MailBurg/releases/tag/v0.1.0
