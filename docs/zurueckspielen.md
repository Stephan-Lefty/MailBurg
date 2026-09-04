[Anleitungen](README.md) | [Übersicht](../README.md) | [Änderungsprotokoll](../CHANGELOG.md)

# Post aus dem Archiv zurückholen

Ein Archiv, aus dem nichts wieder herauskommt, wäre ein Grab. Diese Anleitung
beschreibt den Weg hinaus – für eine einzelne Nachricht und für ein ganzes
Postfach.

## Für eine einzelne Nachricht

Rechte Maustaste auf einen Treffer in der Liste:

- **In Mailprogramm öffnen** – die Mail geht in Thunderbird, Outlook oder
  Apple Mail auf. Der kürzeste Weg, wenn Sie nur antworten wollen.
- **Im Postfach wiederherstellen …** – MailBurg legt sie in den Posteingang
  eines Postfachs Ihrer Wahl, mit ihrem ursprünglichen Datum. Es muss nicht
  das Postfach sein, aus dem sie stammt.
- **Als Datei speichern …** – als `.eml`. Braucht weder Zugangsdaten noch ein
  erreichbares Postfach.

## Für viele Nachrichten auf einmal

*Post → Ins Dateisystem zurückspielen …*, oder auf der Kommandozeile:

```bash
mailburg zurueckspielen ~/Archiv ~/Wiederhergestellt
```

**Ohne `--wirklich` wird nur gezählt.** Der Befehl sagt, um wie viele
Nachrichten es geht und wohin sie kämen – dann erst noch einmal mit
`--wirklich`. Im Fenster steht dieselbe Zahl unter dem Zielfeld.

Geschrieben wird, was Sie ausgewählt haben. Ohne Angabe alles; mit `--suche`
beziehungsweise dem Feld *Auswahl* nur die Treffer eines Suchausdrucks:

```bash
mailburg zurueckspielen ~/Archiv ~/Raus --suche "von:firma.example seit:01.01.2024" --wirklich
```

Stand im Suchfeld des Hauptfensters schon etwas, ist es im Dialog
vorausgefüllt. Die Suchsprache ist dieselbe wie überall sonst – `mailburg
suchhilfe` erklärt sie.

## Welches Format?

Die Wahl ist keine Geschmacksfrage.

| | Maildir | MBOX | .eml |
|---|---|---|---|
| Aufbau | eine Datei je Mail | eine Datei je Ordner | eine Datei je Mail |
| Bytegenau | **ja** | nein (siehe unten) | **ja** |
| Lesezustand | kommt mit | – | – |
| Ordner | `.Konto.Unterordner` | Verzeichnisse | Verzeichnisse |

**Maildir ist die Vorgabe**, und für alles, was noch einmal ein Postfach
werden soll, ist es die richtige Wahl: Die Nachricht bleibt Byte für Byte
dieselbe, eine vorhandene DKIM-Signatur also gültig, und ob eine Mail gelesen
oder beantwortet war, steht wieder im Dateinamen. Evolution und moderne
Thunderbird-Profile lesen das Format unmittelbar.

**MBOX ist das Format von Thunderbirds lokalen Ordnern** – und der einzige
Weg, bei dem MailBurg Ihre Nachrichten verändert:

> Eine Zeile, die im Text mit `From ` beginnt, trennt in einer MBOX zwei
> Nachrichten. Damit aus einer Mail nicht zwei werden, bekommt sie ein `>`
> davor. Wer die Datei wieder einliest, sieht den ursprünglichen Text – eine
> Signatur über die veränderte Fassung stimmt aber nicht mehr.

**.eml** ist der einfachste Fall: eine Datei je Nachricht, die sich in jedes
Mailprogramm ziehen lässt.

## Zweimal zurückspielen ändert nichts

MailBurg erkennt im Zielordner wieder, was von ihm stammt, und überspringt
es. Das ist der Grund, warum dieser Weg zuerst gebaut wurde und nicht der
über IMAP: Dort legt der Server bei jedem `APPEND` eine neue Kopie an, und
wer zweimal zurückspielt, hat alles doppelt.

Praktisch heißt das:

- Ein abgebrochener Lauf lässt sich einfach wiederholen. Er setzt dort an, wo
  der erste aufgehört hat.
- Ein zweiter Lauf holt nach, was seit dem ersten dazugekommen ist.
- Sie können denselben Zielordner immer wieder benutzen.

Bei MBOX liegt neben jeder Datei eine unscheinbare Beiakte
(`…mbox.mailburg-bestand`). Ohne sie wäre nicht zu sagen, was schon
drinsteht: Im Format selbst ist kein Platz für eine Kennung, und eine
hineinzuschreiben hieße, die Mails zu verändern. Löschen Sie sie nicht – ohne
sie beginnt der nächste Lauf von vorn.

## Was dabei nicht geschieht

**Gelöscht wird nichts.** Es entsteht eine Kopie; das Archiv bleibt, wie es
war. Dass Post herausgegangen ist, steht im Journal – mit Ziel, Format und
Anzahl. Wer in einem Jahr gefragt wird, wohin Daten gegangen sind, kann das
nachlesen.

**Lag eine Mail an mehreren Stellen, wird sie trotzdem nur einmal
geschrieben.** Bei Gmail und Proton ist Mehrfachablage der Normalfall – dort
ist jedes Etikett ein weiterer Fundort. Wer alle schreibt, hat dieselbe
Rundmail hinterher fünfmal. Wie oft das vorkam, steht im Bericht am Ende.

**Der Ordnerbaum wird nachgebaut**, je Postfach und Ordner ein Zielordner.
Wer alles in einem Topf haben will, nimmt `--flach` oder das Häkchen im
Dialog.

## In Thunderbird zurückbekommen

MailBurg schreibt die Dateien; das Einhängen macht Thunderbird. Der Weg hängt
davon ab, wie Ihr Profil aufgebaut ist – deshalb steht hier bewusst keine
Klickfolge, die morgen falsch ist. Zwei Wege, die es gibt:

- **`.eml`-Dateien** lassen sich mit der Maus in einen lokalen Ordner ziehen.
  Das ist der Weg, der ohne Zusatzprogramm auskommt.
- **MBOX-Dateien** gehören in den `Mail/Local Folders`-Ordner des Profils.
  Thunderbird muss dafür geschlossen sein, und es legt beim nächsten Start
  seine eigene Indexdatei (`.msf`) daneben.

## Zurück in ein Postfach

Statt auf die Platte geht es auch unmittelbar in ein Postfach – im Dialog
über *Format: In ein Postfach (IMAP)*, auf der Kommandozeile so:

```bash
mailburg zurueckspielen ~/Archiv "Mein Konto" --format postfach --wirklich
```

Das Ziel ist dann kein Ordner, sondern der Name eines eingerichteten
Postfachs (`mailburg konten liste` zeigt sie). Es muss **nicht** das
Postfach sein, aus dem die Post stammt: Der Sinn der Sache ist gerade, dass
Sicherung und Rückgabe nichts miteinander zu tun haben.

Die Ordner werden dort angelegt, mit dem Postfachnamen aus dem Archiv als
oberster Ebene. Ob der Server dabei mit `/` oder `.` trennt, liest MailBurg
aus seiner Ordnerliste – geraten wird nichts.

> **Auch hier schreibt zweimal Laufen nichts doppelt** – aber auf einem
> anderen Weg als auf der Platte. Der Server hilft dabei nämlich nicht:
> `APPEND` legt jedes Mal eine neue Kopie an und vergibt eine neue Nummer.
> MailBurg holt deshalb vor dem Schreiben die `Message-ID` aller
> Nachrichten, die im Zielordner schon liegen, und überspringt, was es
> davon kennt. Das gilt auch für Post, die jemand anders dort abgelegt hat.
>
> **Eine Mail ohne `Message-ID` lässt sich so nicht wiedererkennen.** Die
> wird geschrieben und im Bericht gezählt: Ein Duplikat ist besser als eine
> fehlende Nachricht. Solche Mails sind selten – aber es gibt sie.

**Der Lesezustand kommt mit**, soweit im Archiv vermerkt: Was gelesen oder
beantwortet war, ist es auch im neuen Postfach. Nur `\Deleted` bleibt
draußen – eine Nachricht, die im alten Postfach zum Löschen vorgemerkt war,
soll im neuen nicht als halb gelöscht ankommen.

**Und eines sollten Sie wissen, bevor Sie anfangen:** Was Sie
zurückspielen, holt MailBurg beim nächsten Abruf wieder ins Archiv. Auf der
Platte entsteht dadurch keine zweite Datei – die Ablage erkennt gleiche
Inhalte –, wohl aber ein weiterer Fundort im Journal. Wer das nicht will,
nimmt für den Abruf ein anderes Postfach als für die Rückgabe.

## Wenn etwas schiefgeht

Eine Nachricht, die sich nicht schreiben lässt, beendet den Lauf nicht.
Notiert wird jede einzelne, und am Ende steht, wie viele es waren. Bei
zehntausend Mails ist das der Unterschied zwischen »neun Fehler« und
»nichts«.

Der Rückgabewert der Kommandozeile ist `0`, wenn alles durchlief, `1` bei
einzelnen Fehlern und `2`, wenn schon das Ziel nicht taugte.
