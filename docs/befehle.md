[Deutsch](befehle.md) | [Übersicht](../README.md) | [Anleitungen](README.md) | [MailBurg Server](mailburg-server.md)

# Alle Befehle

Jeder Befehl der Kommandozeile, nach Aufgaben geordnet statt nach dem
Alphabet – wer eine Übersicht aufschlägt, hat eine Absicht im Kopf und
keinen Buchstaben.

**Es ist dasselbe Programm in beiden Gestalten.** Die
<img src="../assets/icon-64.png" width="16" align="top"> blaue Fassung
am Arbeitsplatz und die
<img src="../assets/server/icon-64.png" width="16" align="top"> rote im
Browser teilen sich die Befehle; nur drei gibt es allein für den
Serverbetrieb, und sie stehen unten in einem eigenen Abschnitt.

**Im Zweifel gilt `--help`.** Es zeigt den Stand des Programms, das
gerade läuft – verlässlicher als jede Aufstellung, auch als diese.

```bash
mailburg --help
mailburg importieren --help
```

In den Beispielen steht `~/Archiv` für das Archivverzeichnis. Unter
Windows entsprechend `D:\Archiv`; Pfade mit Leerzeichen gehören in
Anführungszeichen.

## Drei Regeln, die aus Schaden stammen

> **Vor dem Sichern den Abruf anhalten.** Eine Sicherung, die neben
> einem laufenden Abruf entsteht, wird in sich widersprüchlich: Ihr
> Protokoll kennt Nachrichten, deren Dateien nicht mitgepackt wurden.
> Und sie sieht dabei vollständig aus.
>
> **Der Dienst hält den Suchindex.** `neuaufbau`, `texterkennung` und
> `importieren` warten dann – ohne Meldung. Von außen sieht das aus wie
> ein hängender Befehl.
>
> **Kontonamen lassen sich nicht ändern.** Sie stehen im Journal, und
> das Journal wird nicht umgeschrieben. Vor dem ersten Einlesen
> überlegen.

## 1. Nachsehen und prüfen

### Was im Archiv steckt

```bash
mailburg info ~/Archiv
```

Anzahl, Anhänge, Fundorte, Größe, Journaleinträge – dazu die
Postfächer mit ihren Ordnern.

Bei großen Beständen dauert das Minuten: Die Zeile »Auf Platte« wird
aus jeder einzelnen Datei erhoben. Die Postfachliste bricht nach 40
Zeilen ab.

### Ob das Archiv unversehrt ist

```bash
mailburg pruefen ~/Archiv
```

Rechnet die Hash-Kette nach und hält jeden Journaleintrag gegen die
Ablage. Erwartet wird »Hash-Kette: unversehrt« und »Ergebnis: alles in
Ordnung«.

**Fehlt etwas, nennt MailBurg Postfach, Ordner, Datum, Absender und
Betreff** – und davon getrennt den Zeitpunkt der Aufnahme. Beides nicht
zu verwechseln: Das Datum der Mail kann Jahre zurückliegen, der
Aufnahmezeitpunkt sagt, wann der Verlust entstanden sein kann.

### Ob die Texterkennung bereitsteht

```bash
mailburg werkzeuge
```

Zeigt, ob poppler und tesseract gefunden werden. **Auf die Zeile
»Benutzt wird« achten:** Steht dort nur `eng`, fehlen die deutschen
Sprachdaten – dann liest die Erkennung deutsche Texte mit dem
englischen Modell, und der Unsinn landet im Suchindex. Eine Suche, die
Treffer liefert, die keine sind, ist schlimmer als eine, die nichts
findet.

### Ob im Postfach noch Post liegt, die fehlt

```bash
mailburg abgleich ~/Archiv
mailburg abgleich ~/Archiv --aelter-als 180
```

Fragt jedes Postfach, was dort vor einem Stichtag liegt, und hält jede
Nummer gegen das Archiv.

**Das beantwortet eine andere Frage als `pruefen`:** nicht »ist das
Archiv heil«, sondern »ist alles darin«. Ein Archiv kann aus sich
heraus nicht wissen, was es nie gesehen hat.

| Option | |
|---|---|
| `--aelter-als 180` | Stichtag als Abstand in Tagen |
| `--stichtag` | fester Stichtag statt einer Tageszahl |
| `--konto` | nur dieses Postfach |

## 2. Post hereinholen

### Abrufen

```bash
mailburg abrufen ~/Archiv
mailburg abrufen --alle
```

Holt, was seit dem letzten Lauf dazugekommen ist. **Die Postfächer
werden dabei nur gelesen** – ungelesene Post bleibt ungelesen, nichts
wird verschoben oder markiert.

| Option | |
|---|---|
| `--voll` | alles holen statt nur das Neue; doppelt wird nichts abgelegt |
| `--konto` | nur dieses Postfach |
| `--ordner NAME …` | nur diese Ordner |
| `--alle` | nacheinander durch jedes bekannte Archiv |
| `--leise` | nur melden, wenn etwas ankam oder schiefging |
| `--ohne-anhangstext` | Anhänge nicht im Volltext erfassen |
| `--ohne-texterkennung` | danach keine eingescannten PDF lesen |
| `--erkennungsbudget` | Sekunden für die Texterkennung im Anschluss |

Papierkorb, Spamverdacht und Entwürfe bleiben draußen. `--ordner` hebt
das derzeit **nicht** auf.

### Postfächer einrichten

```bash
mailburg konten liste
mailburg konten hinzufuegen Firma --server imap.example.org --benutzer post@example.org
mailburg konten pruefen
```

| Unterbefehl | |
|---|---|
| `liste` | eingerichtete Postfächer zeigen |
| `hinzufuegen` | ein Postfach einrichten |
| `uebernehmen` | aus Thunderbird oder Evolution übernehmen |
| `pruefen` | Anmeldung und Ordner prüfen |
| `passwort` | Passwort setzen oder ändern |
| `zuordnen`, `zuordnung` | Postfach einem Archiv zuordnen |
| `ausschluss` | welche Ordner draußen bleiben |
| `spamfilter` | Betreffmarken wie `[SPAM]` |
| `anmelden`, `abmelden` | OAuth2-Anmeldung |
| `entfernen` | aus der Liste nehmen |

### Von der Platte einlesen

```bash
mailburg importieren ~/Archiv ~/Thunderbird-Profil
mailburg importieren ~/Archiv ~/Export/mueller --konto "mueller (alt)"
```

Liest Thunderbird-Profile, Maildir-Ordner, MBOX-Dateien und
Verzeichnisse mit `.eml`-Dateien. Die Unterordner werden zu den Ordnern
im Archiv.

| Option | |
|---|---|
| `--konto` | unter welchem Namen die Post erscheint |
| `--zusammenlegen` | gleichnamige Ordner mehrerer Quellen vereinen |
| `--alles` | Papierkorb, Spamverdacht und Entwürfe mitnehmen |
| `--ohne-verdichten` | den Suchindex nicht nach jedem Lauf verschmelzen |
| `--ohne-anhangstext` | Anhänge nicht im Volltext erfassen |

Mehrere Quellen auf einmal sind möglich; dann ist `--konto` Pflicht.

**`--ohne-verdichten` lohnt bei vielen Läufen hintereinander.** Das
Verdichten geht über den *gesamten* Volltextindex, nicht nur über das
Neue – bei achtzehn Läufen ist das siebzehnmal verworfene Arbeit.
Einmal am Schluss ohne den Schalter, und der Index ist fertig.

## 3. Suchen und herausholen

### Suchen

```bash
mailburg suchen ~/Archiv "rechnung von:müller jahr:2025"
mailburg suchhilfe
```

`suchhilfe` erklärt die vollständige Suchsprache – dieselbe wie im
Fenster und im Browser.

### Viele Mails herausschreiben

```bash
mailburg zurueckspielen ~/Archiv ~/Rueckgabe --suche "konto:firma jahr:2024" --format eml --wirklich
```

| Option | |
|---|---|
| `--format` | `maildir`, `mbox`, `eml` oder `postfach` |
| `--suche` | welche Mails – dieselbe Suchsprache |
| `--flach` | ohne Ordnerstruktur |
| `--wirklich` | ohne diese Angabe wird nur gezählt |

**Zweimal zurückspielen schreibt nichts doppelt.** Einzig MBOX ist
nicht bytegenau: Dort muss eine Zeile, die mit `From ` beginnt, ein `>`
bekommen – sonst gälte sie als Anfang der nächsten Nachricht.

### Auskunft nach DSGVO

```bash
mailburg auskunft ~/Archiv person@example.org ~/Auskunft.zip
```

Stellt alles zu einer Person zusammen (Art. 15 DSGVO). Ohne Zieldatei
wird nur gezählt. `--im-text` nimmt auch Mails mit, in denen die
Adresse bloß erwähnt wird – das trifft oft Verteiler, in denen die
Person nicht Beteiligte ist.

## 4. Sichern und zurückholen

> **Nur mit angehaltenem Abruf.** Beim Sichern wird zuerst die
> Dateiliste erstellt und das Protokoll zuletzt gepackt. Kommt
> dazwischen eine Mail an, steht ihr Eintrag in der Sicherung und ihre
> Datei nicht – und die Sicherung sieht trotzdem vollständig aus.

```bash
mailburg sichern ~/Archiv ~/Sicherungen
mailburg sichern ~/Archiv ~/Sicherungen --name Firmenarchiv --ersetzen --behalten 3
```

| Option | |
|---|---|
| `--ersetzen` | immer dieselbe Datei statt einer mit Datum |
| `--behalten N` | nur die letzten N Sicherungen aufheben |
| `--name` | Name der Datei statt des Archivnamens |
| `--leise` | nur bei Fehlern melden |

Aus hunderttausenden Dateien wird eine. Kleiner wird dabei kaum etwas –
die Mails liegen schon gepackt –, aber eine Datensicherung auf ein
Wechselmedium hat danach nur noch diese eine Datei zu übertragen.

### Zurückholen

```bash
mailburg wiederherstellen ~/Sicherungen/Archiv.tar.zst ~/Archiv-neu
mailburg wiederherstellen ~/Sicherungen/Archiv.tar.zst --hinein ~/Archiv
```

**Zwei Wege, und der Unterschied ist wesentlich.** In einen leeren
Ordner entsteht das Archiv neu, mit seiner eigenen Hash-Kette – der
Fall nach einem Plattenschaden. Mit `--hinein` wandern nur die
Nachrichten in ein vorhandenes Archiv, mit ihrem ursprünglichen
Postfach und Ordner; beide Ketten bleiben heil, und Doppeltes erkennt
das Archiv selbst.

## 5. Pflege und Nachweis

### Eingescannte PDF durchsuchbar machen

```bash
mailburg texterkennung ~/Archiv
mailburg texterkennung ~/Archiv --alles
```

| Option | |
|---|---|
| `--alles` | ohne Zeitgrenze durchlaufen – Abbruch mit Strg+C |
| `--budget N` | Sekunden für diesen Lauf |
| `--nochmal` | zuvor aufgegebene Dokumente erneut versuchen |

**Die kleinsten zuerst.** Jeder Abbruch hinterlässt deshalb einen
brauchbaren Stand, und der nächste Lauf macht dort weiter. Gemessen an
einem Bestand mit 77.000 wartenden Dokumenten: rund eine Sekunde je
Seite, 55.000 Dokumente in einer Nacht.

```bash
mailburg vorrat ~/Archiv
```

Nimmt schon erkannten Text in den Nebenspeicher, damit er einen
Neuaufbau übersteht.

### Suchindex neu bauen

```bash
mailburg neuaufbau ~/Archiv
```

Erzeugt den Index vollständig aus Ablage und Journal – deshalb muss er
nicht gesichert werden.

**Nebenbei ist das die einzige vollständige Inhaltsprüfung:** Jede Mail
wird gelesen und ihr Hash nachgerechnet. `pruefen` sieht nur, *ob* eine
Datei da ist, nicht *was* darin steht. Die Schlusszahl gegen die
erwartete Anzahl halten.

### Siegel und Vermerke

```bash
mailburg siegel ~/Archiv
mailburg siegel ~/Archiv --zeitstempel
mailburg siegel ~/Archiv --liste
mailburg kettenvermerk ~/Archiv --nummer 488 --grund "zwei Prozesse" --wer "Name"
```

Ein Siegel hält den Stand fest; mit `--zeitstempel` von einem
RFC-3161-Dienst bestätigt. Ein `kettenvermerk` erklärt eine bekannte
Bruchstelle – **er heilt sie nicht, und das ist Absicht:** Die Kette
umzuschreiben wäre genau das, was sie verhindern soll.

### Fristen, Einstufung, Dokumentation

```bash
mailburg faellig ~/Archiv
mailburg einstufen ~/Archiv "konto:verein" privat --wirklich
mailburg regeln ~/Archiv zeigen
mailburg verfahrensdoku ~/Archiv ~/Verfahrensdokumentation.md
```

`faellig` zeigt, was seine Aufbewahrungsfrist hinter sich hat –
gelöscht wird nichts von selbst. `einstufen` ordnet Mails
aufbewahrungsrechtlich ein, `regeln` tut das schon beim Aufnehmen.
`verfahrensdoku` erzeugt den technischen Teil der GoBD-Dokumentation;
die offenen Stellen bleiben sichtbar stehen.

### Löschen

```bash
mailburg loeschen ~/Archiv --konto postfach@example.org --grund "..." --wirklich
```

Im Geschäftsarchiv über Grabsteine – der Vorgang bleibt im Journal
nachvollziehbar. Ohne `--wirklich` wird nur gezählt.

### Ein neues Archiv

```bash
mailburg anlegen ~/Archiv --modus geschaeftlich --recht DE --name Firmenarchiv
mailburg anlegen ~/Archiv --verschluesseln
```

Beim verschlüsselten Archiv kommt dazu:

```bash
mailburg passwort aendern ~/Archiv
mailburg passwort hinterlegen ~/Archiv
mailburg passwort vergessen ~/Archiv
```

**Der Suchindex bleibt dabei Klartext** – er liegt außerhalb des
Archivs. Für den Anlass der Verschlüsselung (Sicherung in der Cloud,
verlorene Platte) genügt das, weil er nicht mitwandert; auf einem
Server hilft nur eine verschlüsselte Platte.

### Suchordner

```bash
mailburg suchordner ~/Archiv zeigen
mailburg suchordner ~/Archiv hinzufuegen "Offene Rechnungen" "rechnung -bezahlt"
```

## 6. Nur für die rote Fassung

<img src="../assets/server/icon-64.png" width="18" align="top"> Diese
drei Befehle gibt es allein für den Serverbetrieb.

### Zugänge

```bash
mailburg zugaenge ~/Archiv liste
mailburg zugaenge ~/Archiv hinzufuegen name
mailburg zugaenge ~/Archiv rechte name --nur postfach@example.org
mailburg zugaenge ~/Archiv passwort name
```

| Unterbefehl | |
|---|---|
| `rechte --alle` | alle Postfächer sehen |
| `rechte --nur X` | nur diese; mehrfach angebbar, ersetzt die bisherigen |
| `rechte --verwalter` | darf Zugänge anlegen und Rechte vergeben |
| `anzeigename` | den Klarnamen ändern |
| `stilllegen`, `zulassen` | Zugang sperren und wieder öffnen |

**Die Rechte gehen bis zum Postfach, nicht bis zum Ordner.** Die
Einschränkung wirkt bereits in der Suche, nicht erst bei der Anzeige –
schon die Trefferzahl verrät damit nicht, dass es Nachrichten gibt, die
man nicht einsehen darf.

Ausgeschiedene Mitarbeiter werden stillgelegt, nicht gelöscht: Ihr Name
muss in den Protokollen nachvollziehbar bleiben.

### Tresor – Passwörter ohne Schlüsselbund

```bash
mailburg tresor uebernehmen
mailburg tresor liste
mailburg tresor pruefen
mailburg tresor schluessel
mailburg tresor entfernen name
```

Auf einem Server gibt es keinen Schlüsselbund. `uebernehmen` holt
Passwörter **und OAuth2-Marken** vom Arbeitsplatz; `schluessel` nennt
den Ort des Hauptschlüssels.

**Tresordatei und Hauptschlüssel nie auf demselben Weg übertragen.**

### Den Dienst betreiben

```bash
mailburg server --help
```

Gestartet und angehalten wird er über das Betriebssystem:

```bash
# Linux
sudo systemctl start mailburg-server
sudo systemctl stop mailburg-server
systemctl status mailburg-server
```

```powershell
# Windows
sc.exe start MailBurgServer
sc.exe stop MailBurgServer
sc.exe query MailBurgServer
```

**`sc.exe stop` kehrt zurück, bevor der Dienst unten ist** – bei
`query` auf **STOPPED** warten. Unter Windows startet der Dienst nach
einem Neustart von selbst (verzögert automatisch); wer über mehrere
Tage am Archiv arbeitet, muss ihn jedes Mal erneut anhalten.

### Die Betriebsart

```bash
mailburg betriebsart ~/Archiv --modus geschaeftlich --land DE
```

Gilt für beide Fassungen, steht aber hier, weil ein Serverarchiv in
aller Regel ein geschäftliches ist. Im Geschäftsarchiv wandert jeder
Vorgang in die Hash-Kette, gelöscht wird nur über Grabsteine, und
Aufbewahrungsfristen schützen vor zu frühem Entfernen.
