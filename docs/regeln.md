[Übersicht](../README.md) | [Anleitungen](README.md) | [Erste Schritte](erste-schritte.md) | [Die Oberfläche](oberflaeche.md) | [Postfach entlasten](postfach-entlasten.md) | [Sichern](sicherung.md)

# Private Post im Geschäftsarchiv

Wer geschäftlich archiviert, archiviert Privates mit. Der Verein, die
Familie, der Handwerker für die eigene Wohnung, die Bestellung beim
Elektronikhändler — all das kommt über dasselbe Postfach und landet im
selben Archiv.

**Und liegt dort falsch.** Ein Geschäftsarchiv bremst das Löschen: sechs,
acht oder zehn Jahre, je nach Einstufung. Für eine Einladung zum Grillfest
gilt keine dieser Fristen. Umgekehrt verlangt die DSGVO, personenbezogene
Daten zu löschen, sobald ihr Zweck entfällt — und bei privater Post
entfällt er sofort.

Von Hand nachzustufen wäre die Alternative. Das tut niemand über Jahre
hinweg bei jeder eingehenden Mail.

## Was eine Regel tut

Sie schaut auf **Ordner**, **Absender** oder **Empfänger** und bestimmt
daraus die Einstufung:

```bash
mailburg regeln ~/Geschaeftsarchiv hinzufuegen von '*@verein.example' privat
```

Ab jetzt wird jede Mail von einer Adresse bei `verein.example` beim
Aufnehmen als privat eingestuft — und unterliegt damit keiner
Aufbewahrungsfrist.

Als Muster dienen `*` und `?`, nicht reguläre Ausdrücke. `*@verein.example`
versteht jeder; ein verunglückter regulärer Ausdruck kann alles treffen,
ohne dass man es ihm ansieht.

## Was eine Regel nicht tut

**Sie verhindert nicht das Holen.** Geholt wird alles, immer. Die Regel
entscheidet nur, wie die Mail eingestuft wird.

Das ist eine bewusste Entscheidung: Eine Regel, die schon den Abruf
verhindert, wirft weg, was sie trifft. Wer später merkt, dass sie zu weit
griff, hat die Post verloren — falls sie im Postfach inzwischen gelöscht
wurde. Eine falsche Einstufung lässt sich zurücknehmen, eine nicht geholte
Mail nicht.

**Sie rührt bestehende Post nicht an.** Was schon im Archiv liegt, bleibt
eingestuft, wie es ist — besonders dann, wenn jemand es von Hand
eingestuft hat. Eine bewusste Entscheidung soll nicht weniger wiegen als
ein Suchmuster. Wer bestehende Post nachstufen will, sagt es ausdrücklich:

```bash
mailburg regeln ~/Geschaeftsarchiv anwenden            # zeigt nur
mailburg regeln ~/Geschaeftsarchiv anwenden --wirklich # tut es
```

## Die erste passende Regel gilt

Nicht die schärfste, nicht die zuletzt angelegte — die erste. Das ist die
einzige Regelung, die sich ohne Nachdenken vorhersagen lässt.

Daraus folgt: **Ausnahmen gehören nach oben.** Der Kassenwart des Vereins
schickt Beitragsquittungen, und die sind Buchungsbelege:

```bash
mailburg regeln ~/Archiv hinzufuegen von 'kasse@verein.example' \
    buchungsbeleg --zuerst --bemerkung "Beitragsquittungen"
```

Ohne `--zuerst` stünde die Regel hinter der allgemeinen Vereinsregel und
käme nie zum Zug. Die Reihenfolge sehen Sie jederzeit:

```bash
mailburg regeln ~/Archiv zeigen
```

```
2 Regeln, in dieser Reihenfolge geprüft:
  1. Absender passt auf »kasse@verein.example« → buchungsbeleg
     Beitragsquittungen
  2. Absender passt auf »*@verein.example« → privat
```

## Was im Journal steht

**Jede Anwendung.** Mit der Regel als Urheber, nicht mit Ihrem Namen — wer
später liest, wer diese Mail für privat erklärt hat, soll nicht fälschlich
einen Menschen dort finden.

**Jede Änderung an den Regeln.** Welche Regel wann galt, gehört zur
Verfahrensdokumentation. Wer einer Prüfung erklären muss, warum eine Mail
nicht der zehnjährigen Aufbewahrung unterlag, zeigt auf diesen Eintrag —
und er hängt in der Hash-Kette, lässt sich also nicht nachträglich
glattziehen.

## Ein Vorschlag für den Anfang

Legen Sie zuerst die Ordner fest, dann die Absender. Ordner sind
verlässlicher: Wer seine Post einsortiert, hat die Entscheidung schon
getroffen.

```bash
mailburg regeln ~/Archiv hinzufuegen ordner 'INBOX/Privat*' privat
mailburg regeln ~/Archiv hinzufuegen ordner '*/Familie' privat
mailburg regeln ~/Archiv hinzufuegen von '*@verein.example' privat
```

Danach einmal ansehen, was das für den Bestand hieße:

```bash
mailburg regeln ~/Archiv anwenden
```

Es zeigt die ersten zehn Mails, die umgestuft würden, und die Gesamtzahl.
Sieht das falsch aus, ändern Sie die Regeln, bevor Sie `--wirklich`
hinzufügen.

## Grenzen

**Ein Muster ist kein Verständnis.** `*@verein.example` trifft auch den
Anwalt, der zufällig dort seine Adresse hat. Sehen Sie sich nach ein paar
Wochen an, was die Regeln eingestuft haben — in der Oberfläche über
*Suchen*, oder auf der Kommandozeile:

```bash
mailburg suchen ~/Archiv von:verein.example
```

Stimmt eine Einstufung nicht, stellen Sie sie um: *Post → Aufbewahrung
festlegen …*, oder `mailburg einstufen`. Was von Hand eingestuft wurde,
rührt keine Regel mehr an.

**Der Betreff steht nicht zur Auswahl.** Absichtlich: Er lässt sich
fälschen, er wechselt im Verlauf eines Austauschs, und eine Regel auf
»Rechnung« im Betreff träfe auch die Werbemail, die so tut. Ordner und
Absender sind belastbarer.

**Regeln ersetzen keine Prüfung.** Was aufbewahrungspflichtig ist,
entscheidet das Recht, nicht ein Suchmuster. Im Zweifel gilt die längere
Frist — und deshalb bleibt alles ohne passende Regel »unbestimmt«, was
MailBurg wie die längste Pflicht behandelt.
