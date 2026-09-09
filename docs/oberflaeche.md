[Übersicht](../README.md) | [Anleitungen](README.md) | [Erste Schritte](erste-schritte.md) | [Postfach entlasten](postfach-entlasten.md) | [Sichern](sicherung.md)

# Die Oberfläche

Jedes Fenster und jeder Menüpunkt, mit Bild und Erklärung. Alle Abbildungen
zeigen erfundene Postfächer.

Dieselben Erklärungen stehen auch im Programm selbst unter **Hilfe → Handbuch**
(F1) – dort mit Sprungmarken zwischen den Kapiteln.

## Das Hauptfenster

![Das Hauptfenster in drei Bereichen: links die Postfächer mit ihren Ordnern, rechts oben die Nachrichtenliste mit Anhangsymbol, Datum, Absender, Betreff und Größe, darunter der Lesebereich. Ganz oben das Suchfeld, unten die Zahl der Mails im Archiv.](bilder/uebersicht.png)

Vier Bereiche:

**Oben das Suchfeld.** Schreiben Sie hinein, wonach Sie suchen. Darunter
erscheint das Ergebnis: *MailBurg hat 191 Treffer* oder *MailBurg hat nichts
gefunden*. Diese Zeile steht dort, wo Sie beim Tippen ohnehin hinsehen – bei
zweitausend Mails ist die Suche in Millisekunden durch, und eine Zahl am
unteren Fensterrand bemerkt dabei niemand.

**Links die Postfächer** mit ihren Ordnern und der Zahl der Mails. Ein Klick
grenzt die Suche darauf ein. Die Postfächer lassen sich anordnen – mit der Maus
oder über Strg+Auf und Strg+Ab.

**Rechts die Treffer.** Ein Klick auf einen Spaltenkopf sortiert, ein zweiter
dreht die Richtung um; das Zeichen ⇅ zeigt, welche Spalten sich sortieren
lassen. Die Büroklammer ganz links steht für Anhänge.

**Darunter die Vorschau** mit Kopfzeilen, Text und Anhängen. Anhänge lassen
sich öffnen oder speichern.

**Unten rechts steht immer**, wie viele Mails im Archiv liegen und wann zuletzt
abgerufen wurde. Das beantwortet die Frage, die sich vor jedem Aufräumen im
Mailprogramm stellt: *Ist mein Archiv auf dem Stand?*

### Eine Nachricht lesen

![Eine geöffnete Nachricht: oben Betreff, Absender mit Adresse, Empfänger und Datum, darunter der Text der Mail in einem eigenen Bereich.](bilder/lesefenster.png)

Ein **Doppelklick** in der Trefferliste öffnet die Nachricht in einem eigenen
Fenster – die Vorschau unten ist zum Überfliegen da, nicht zum Lesen. Mehrere
Fenster gleichzeitig sind möglich, etwa um zwei Rechnungen zu vergleichen.
Strg+W oder Esc schließt sie.

### Der Gesprächsverlauf

Gehört eine Mail zu einem Austausch, der hin und her ging, sagt die Vorschau
es: *Gespräch: 7 Nachrichten – erste vom 12.03.2025, letzte vom 04.04.2025.*

**Zusammengehalten über die Kopfzeilen, nicht über den Betreff.** Jede Mail
trägt in `References` die Kennungen ihrer Vorgänger; so sieht es der Standard
für E-Mail vor. Der Betreff taugt dafür nicht: Er wechselt im Verlauf, und
zwei Mails mit »Rechnung« im Betreff haben meistens nichts miteinander zu tun.

**Vollständig ist ein Verlauf nie garantiert.** Was nie ins Archiv kam, fehlt
auch hier — und wer über den Server nur einen Teil der Postfächer sehen darf,
sieht auch nur die Teile des Gesprächs daraus.

> **Für bestehende Archive:** Diese Angaben stehen in den Mails, wurden aber
> bis Fassung 0.12 nicht in den Suchindex übernommen. Ein Archiv aus der Zeit
> davor **öffnet sich deshalb erst nach einem Neuaufbau des Suchindex.**
> MailBurg bietet ihn beim Öffnen an; auf der Kommandozeile ist es
> `mailburg neuaufbau ARCHIV`.
>
> Verloren ist dabei nichts. Die Mails liegen bytegenau im Archiv, samt aller
> Kopfzeilen; der Index ergibt sich daraus und sonst nirgendwoher. Rechnen Sie
> mit etwa vier Minuten je zehntausend Nachrichten.

### Eine Nachricht zurückholen

![Der Dialog zum Zurückholen einer Nachricht ins Postfach. Er erklärt, dass die Mail vollständig und mit ihrem ursprünglichen Datum in den Posteingang kommt und dass es nicht dasselbe Postfach sein muss. Darunter die Wahl des Zielpostfachs und ein Häkchen »Als ungelesen markieren«.](bilder/wiederherstellen.png)

Mit der **rechten Maustaste** auf eine Nachricht stehen drei Wege offen.

*In Mailprogramm öffnen* ist der kürzeste: Die Nachricht geht in dem Programm
auf, das Sie für E-Mail-Dateien eingerichtet haben. Verändert wird dabei
nichts.

MailBurg legt sie dafür kurz im Zwischenspeicher Ihres Benutzerkontos ab, in
einem Ordner, den nur Sie lesen dürfen — nicht im allgemeinen
Temp-Verzeichnis, in das auf einem gemeinsam genutzten Rechner jeder
hineinsieht. Was älter als vier Stunden ist, verschwindet beim nächsten
Öffnen; beim Beenden von MailBurg der ganze Ordner.

*Im Postfach wiederherstellen* legt sie in den Posteingang eines frei
gewählten Postfachs – vollständig, mit allen Anhängen und mit ihrem
ursprünglichen Datum.

**Es muss nicht das Postfach sein, aus dem sie stammt.** Post überlebt
Arbeitgeber, Anbieter und Adressen.

Markiert wird sie als ungelesen. Das klingt nach einer Falschmeldung, ist aber
der einzige Weg, sie wiederzufinden: Mit ihrem alten Datum steht sie mitten in
der Post von damals.

*Als Datei speichern* schreibt stattdessen eine `.eml`-Datei. Die öffnet jedes
Mailprogramm und braucht weder Zugangsdaten noch ein erreichbares Postfach.

## Menü Archiv

**Neues Archiv anlegen …** – ein weiteres Archiv, etwa ein privates neben dem
geschäftlichen.

**Archiv wechseln …** – zu einem vorhandenen Archiv. Der Dialog kennt Ihre
angeschlossenen Platten.

**Zuletzt benutzt** – die zuletzt geöffneten Archive unter ihrem Namen. Wer
zwei Archive führt, wechselt hierüber mit zwei Klicks.

**Auskunft nach DSGVO …** *(nur im Geschäftsarchiv)*

![Der Dialog für die Auskunft nach Artikel 15 DSGVO: ein Feld für die Mailadresse der betroffenen Person, ein Häkchen für Nachrichten, in denen die Adresse nur erwähnt wird, und das Ergebnis mit der Zahl der Nachrichten und dem Zeitraum. Darunter der Hinweis, dass vor der Herausgabe die Rechte Dritter zu prüfen sind.](bilder/auskunft.png)

Fragt jemand, was über ihn gespeichert ist, hat er nach Artikel 15 DSGVO
Anspruch auf eine Kopie. MailBurg sucht alle Nachrichten, in denen die Person
vorkommt, und packt sie auf Wunsch als ZIP – mit einem Begleitblatt, das
Herkunft, Zeitraum und Verarbeitungszweck nennt.

**Herausgegeben wird von Ihnen, nicht vom Programm.** In denselben Nachrichten
stehen oft Daten Dritter – Adressen im Verteiler, Namen im Text, Unterschriften
in Anhängen –, und nach Artikel 15 Absatz 4 darf die Kopie deren Rechte nicht
beeinträchtigen. Das steht im Fenster und noch einmal im Begleitblatt.

**Verfahrensdokumentation …** *(nur im Geschäftsarchiv)* – erzeugt einen
Entwurf nach GoBD. MailBurg füllt, was es selbst weiß; alles Organisatorische
bleibt als sichtbare Lücke stehen. Verantwortlich dafür sind Sie.

**Archiv sichern …**

![Der Sicherungsdialog. Er erklärt, dass das ganze Archiv in eine einzige Datei wandert, dass diese nicht viel kleiner wird, weil die Mails bereits komprimiert liegen, und dass der Suchindex nicht mitkommt, weil er sich jederzeit neu aufbauen lässt.](bilder/sichern.png)

Packt das ganze Archiv in eine einzige Datei. Viel kleiner wird sie nicht –
Ihre Mails liegen schon komprimiert –, aber aus zehntausend Dateien wird eine,
und damit kommen Cloud-Programme um ein Vielfaches schneller zurecht.

**Sicherung importieren …** – nimmt die Mails einer Sicherung in das *geöffnete*
Archiv auf, mit ihrem ursprünglichen Postfach und Ordner. Doppelte werden
erkannt; dieselbe Sicherung lässt sich gefahrlos zweimal einlesen.

**Sicherung in neues Archiv …** – macht daraus ein eigenes, neues Archiv. Das
Zielverzeichnis muss leer sein: Zwei Protokolle ineinander ergäben eines, das
sich nicht mehr prüfen lässt.

**Journal prüfen** – vergleicht das Protokoll mit dem, was tatsächlich auf der
Platte liegt, und prüft die Kette der Einträge. Nach jedem Zurückholen einer
Sicherung sinnvoll.

## Menü Post

**Jetzt abrufen (F5)** – holt sofort, was neu ist. Am Ende steht, ob alle
Postfächer erreichbar waren. **Räumen Sie nicht auf, solange dort eines fehlt.**

**Lokale Mailordner einlesen …**

Post, die schon auf der Platte liegt – aus Postfächern, die es online längst
nicht mehr gibt, oder aus einem Programm, das Sie nicht mehr benutzen. Vier
Quellen kennt MailBurg, und es erkennt selbst, welche vor ihm liegt:

- **Thunderbird-Profil** – mit allen Konten und der ganzen Ordnerstruktur.
- **Maildir-Verzeichnis** – so legt Evolution seine lokalen Ordner ab.
- **MBOX-Datei** – das Format von Thunderbirds lokalen Ordnern.
- **Ordner mit `.eml`-Dateien**, auch verschachtelt. Das ist der Weg für
  alles, was ein anderes Programm einmal einzeln exportiert hat – Apple Mails
  `.emlx` zählt mit.

Der Dialog schlägt vor, was er auf dem Rechner findet, und sagt **vor** dem
Start, was er dort erkannt hat. Passt nichts davon, nennt er den Grund statt
nur »geht nicht«.

**Der Kontoname entscheidet, wo die Post landet.** Zur Auswahl stehen die
Postfächer, die es in diesem Archiv schon gibt; eintippen lässt sich trotzdem,
was man will.

- **Alte Post zu einem laufenden Postfach** – etwa ein Export aus MailStore zu
  einem Postfach, das MailBurg weiterhin abruft: **dasselbe Konto auswählen.**
  Dann steht alles zusammen. Der Abruf gerät dabei nicht aus dem Tritt; er
  merkt sich seinen Stand an den Nachrichtennummern des Servers, und
  eingelesene Dateien haben keine.
- **Ein Bestand, der zu keinem Postfach mehr gehört:** einen eigenen Namen
  vergeben. »Alt-Thunderbird« ist eine bessere Wahl als »Import« – in zehn
  Jahren will jemand wissen, woher diese Mails stammen.

Bleibt das Feld leer, nimmt MailBurg den Namen des Ordners.

**Vorsicht bei fast gleichen Namen:** »firma« und »Firma« sind zwei Postfächer,
sehen im Baum aber gleich aus. MailBurg warnt, wenn der eingetippte Name einem
vorhandenen bis auf Groß- und Kleinschreibung gleicht.

Die Ordner des Exports erscheinen **neben** denen des Postfachs, nicht darin –
der Verzeichnisname wird zum Ordnernamen. Eine Mail, die es in beiden gibt,
liegt einmal auf der Platte; dass sie an zwei Stellen lag, steht trotzdem im
Journal.

### Papierkorb und Spam bleiben draußen

Wie beim Abruf aus einem Postfach werden diese Ordner übergangen:

```
Papierkorb, Trash, Deleted Items, Gelöschte Elemente, Gelöschte Objekte
Spam, Junk, Junk-E-Mail, Bulk Mail, Werbung, Unerwünschte E-Mail
Entwürfe, Drafts
```

Diese Post hat der Anwender schon einmal aussortiert. Groß- und
Kleinschreibung, Bindestriche und Leerzeichen sind dabei egal – »Junk-E-Mail«,
»Junk E-Mail« und »junk email« meinen denselben Ordner. Ein Ordner, der nur
so *ähnlich* heißt, bleibt drin: »Werbung 2024« ist ein eigener Name.

**Welche Ordner es trifft, steht vor dem Start unter dem Pfad** – eine stille
Auslassung wäre schlimmer als keine.

Das Häkchen *Papierkorb, Spamverdacht und Entwürfe mitnehmen* schaltet es ab,
auf der Kommandozeile `--alles`. Für ein Geschäftsarchiv kann das richtig
sein: Wer belegen muss, was ihn erreicht hat, will auch den Spamordner – dort
landet regelmäßig Post, die dorthin nicht gehört.

Wählen Sie dagegen mit *MBOX-Datei …* ausdrücklich eine einzelne Datei aus,
wird nicht gefiltert. Wer »Junk« von Hand anklickt, hat entschieden.

Auf der Kommandozeile ist das `mailburg importieren ARCHIV QUELLE --konto NAME`.

**Eingescannte PDF lesen …**

![Der Dialog für die Texterkennung. Er meldet, dass keine eingescannten PDF warten, und lässt einstellen, wie viele Prozessorkerne die Erkennung gleichzeitig verwenden darf.](bilder/texterkennung.png)

Die Zahl im Menü sagt, wie viele Dokumente noch ein weißes Blatt für die Suche
sind: eingescannte Seiten ohne Textebene. Die Texterkennung liest sie und legt
das Ergebnis in den Suchindex – **das Archiv selbst bleibt unangetastet**, die
PDF werden nicht verändert.

Etwa fünf bis acht Sekunden je Seite. Sie können das Fenster schließen und im
Hintergrund weiterlesen lassen; oben rechts steht dann der Stand, und Sie
können normal weitersuchen.

**Aufbewahrung festlegen …** *(nur im Geschäftsarchiv)*

![Der Dialog zum Einstufen gefundener Mails. Zur Wahl stehen Buchungsbeleg, Handelsbrief, Privat und »Noch nicht eingeordnet«, jeweils mit Erklärung. Darunter steht, wie viele Mails geändert werden und wie lange sie danach vor dem Löschen geschützt sind, sowie der Hinweis, dass jede Änderung im Journal vermerkt wird.](bilder/aufbewahrung.png)

Ordnet die **gerade gefundenen** Mails ein: Buchungsbeleg, Handelsbrief oder
privat. Davon hängt ab, wie lange MailBurg das Löschen bremst – sechs, acht
oder zehn Jahre.

Eingestuft wird über die Suche, nicht Mail für Mail. Wer ein Archiv einordnet,
hat hunderte Belege vor sich; »alles von der Steuerkanzlei ist Buchungsbeleg«
ist eine Regel, die sich als Suchausdruck schreiben lässt. Suchen Sie also
zuerst, und stufen Sie dann die Treffer ein.

Das Fenster sagt vorher, wie viele Mails betroffen sind und was die Wahl
bedeutet. Jede Änderung steht im [Journal](#journal) – wer später begründen
muss, warum eine Mail nach sechs statt acht Jahren gelöscht wurde, will darauf
zeigen können.

### Einmal im Jahr fragt MailBurg nach

![Die jährliche Nachfrage im Privatarchiv: Sie nennt die Zahl der Mails, die älter als zehn Jahre sind, und aus welchen Jahren sie stammen. Dazu der Hinweis, dass ein Privatarchiv keine Aufbewahrungsfristen kennt und Alter kein Grund zum Löschen ist. Knöpfe »Ansehen« und »Nicht jetzt«.](bilder/fristen.png)

Ab dem 1. Mai, und nur einmal je Kalenderjahr: MailBurg zeigt, was seine Frist
hinter sich hat. Nicht ab dem 1. Januar, wenn die Fristen ablaufen – eine
Meldung, die bei jedem Öffnen erscheint, wird nach der dritten Wiederholung
weggeklickt, ohne gelesen zu werden.

**Auch ein Privatarchiv fragt**, dort aber anders: Es gibt keine Fristen, also
zeigt es nur, was älter als zehn Jahre ist, und sagt ausdrücklich dazu, dass
Alter kein Grund zum Löschen ist. Gelöscht wird in beiden Fällen nichts von
selbst.

## Menü Suchen

**Ausführlich suchen … (Strg+F)**

![Die ausführliche Suchmaske mit Feldern für Suchwort, Absender, Empfänger, Betreff und Dateiname eines Anhangs. Darunter Eingrenzungen nach Postfach, Ordner, Jahr, Zeitraum, Anhangstyp, Größe und Wichtigkeit. Ganz unten steht der daraus gebaute Suchausdruck, der sich kopieren und auf der Kommandozeile weiterverwenden lässt.](bilder/suchmaske.png)

Eine Maske mit Feldern für Absender, Empfänger, Betreff, Anhänge, Zeitraum,
Größe und Wichtigkeit. Unten zeigt sie den Suchausdruck, den sie daraus
zusammensetzt – so lernt man die Suchsprache nebenbei und kann den Ausdruck
kopieren.

Der Zeitraum lässt sich im Kalender wählen. Achten Sie auf die Trennung:
*Verschickt oder empfangen* meint das Datum der Mail, *Ins Archiv aufgenommen*
den Tag, an dem MailBurg sie geholt hat. Eine Mail von 2016 kann heute ins
Archiv gekommen sein.

## Menü Ansicht

**Fenster auf Standard zurücksetzen** – Größe und Aufteilung wie beim ersten
Start. Ihre gespeicherte eigene Ansicht bleibt erhalten.

**Postfach nach oben / nach unten (Strg+Auf, Strg+Ab)** – ordnet die Postfächer
an. Geht auch mit der Maus.

**Eigene Ansicht speichern / laden** – legt Größe, Aufteilung, Spaltenbreiten
und Reihenfolge ab. Gespeichert wird nur auf Befehl: Sonst überschriebe ein
versehentliches Verziehen die Ansicht, die Sie sich eingerichtet haben.

## Menü Einstellungen

**Postfächer verwalten …**

![Die Postfachverwaltung als Tabelle mit Postfach, Mailadresse, Server, Ort des Passworts, Zustand und zugeordnetem Archiv. Ein stillgelegtes Postfach ist ausgegraut. Darunter Knöpfe zum Hinzufügen, zur Übernahme aus Thunderbird, zum Zuordnen eines Archivs und zum Stilllegen.](bilder/postfaecher.png)

Postfächer hinzufügen, Passwörter ändern, stilllegen oder entfernen. Ein
stillgelegtes Postfach bleibt eingerichtet, wird beim Abruf aber übergangen –
nützlich für ein Konto, das es nicht mehr gibt. **Entfernen** nimmt es samt
Passwort aus der Liste; die bereits archivierten Mails bleiben in jedem Fall
erhalten.

**Zugänge verwalten …** *(nur im Geschäftsarchiv)*

Wer sich an diesem Archiv anmelden darf – und welche Postfächer er dabei zu
sehen bekommt. Solange MailBurg nur auf diesem Rechner läuft, ändert das
nichts: Wer am Rechner sitzt, hat das Archiv ohnehin. Die Zugänge greifen,
sobald es über einen Server erreichbar ist.

Links stehen die Menschen, rechts die Rechte des Gewählten. Die wichtigste
Zeile ist die unterste: Sie sagt in einem Satz, was er sehen darf — auch den
Fall »Sieht nichts«, der beim Anlegen sonst niemandem auffällt.

**Zwei Rechte, und sie sind nicht dasselbe.** *Darf Zugänge verwalten* legt
Zugänge an und vergibt Rechte. *Darf alle Postfächer sehen* liest jede Post.
Wer die Technik betreut, muss keine Geschäftspost lesen dürfen — und wer alles
liest, nicht über fremde Zugänge bestimmen.

*Alle Postfächer* ist ein Schalter, keine angekreuzte Liste: Wer ihn gesetzt
hat, sieht auch das Postfach, das nächste Woche dazukommt.

**Stilllegen statt entfernen.** Ein stillgelegter Zugang meldet sich nicht mehr
an, bleibt aber eingetragen — sein Name muss in alten Journaleinträgen lesbar
bleiben, sonst stehen dort Vorgänge ohne Urheber.

**Der letzte Verwalter kann sich nicht selbst aussperren.** Ihm das Recht zu
nehmen, ihn stillzulegen oder zu entfernen, lässt MailBurg nicht zu. Sonst
gäbe es niemanden mehr, der Zugänge vergeben kann.

**Was von selbst laufen soll (Automatisierung) …**

![Die Einstellungen für das, was von selbst läuft: oben das Häkchen für den regelmäßigen Abruf im Hintergrund mit einstellbarem Abstand, darunter die regelmäßige Sicherung in eine Datei mit Häufigkeit, Zahl der aufbewahrten Stände und Zielordner. Dazu der Hinweis, nicht auf dieselbe Platte wie das Archiv zu sichern.](bilder/automatisierung.png)

Zwei Dinge, die ohne Zutun laufen sollten:

*Neue Post regelmäßig holen* – alle 15 Minuten bis einmal täglich. MailBurg
muss dafür weder geöffnet bleiben noch mitstarten; nötig ist nur, dass Sie
angemeldet sind, weil daran der Schlüsselbund hängt. War der Rechner aus, wird
der versäumte Abruf nachgeholt.

*Das Archiv regelmäßig sichern* – täglich, wöchentlich oder monatlich in einen
Ordner Ihrer Wahl. Am besten einen, den Ihre Cloud abgleicht. **Nicht auf
dieselbe Platte wie das Archiv:** Eine Sicherung, die neben dem Original liegt,
geht mit ihm zusammen verloren.

Dazu ein dritter Schalter, der zu keinem Zeitplan gehört, aber bei jedem Abruf
wirkt – auch bei dem, der von selbst läuft:

*Post mit Spam-Marke im Betreff gar nicht erst aufnehmen* – gilt für **alle**
Postfächer auf einmal. Zeigt das Kästchen einen Strich statt eines Hakens, ist
der Filter nur bei einem Teil an; wer ihn so stehen lässt, ändert daran nichts.
Für einzelne Postfächer gibt es `mailburg konten spamfilter NAME --ein`.

**Sehen Sie vorher nach, was das bei Ihnen träfe** – der Verweis daneben führt
ins Handbuch, wo steht, warum das wichtig ist. Kurz gefasst: Ein Spamfilter
irrt, und in einem echten Archiv standen unter den Treffern sieben Rechnungen.

## Menü Hilfe

![Das eingebaute Handbuch: links das Verzeichnis mit Kapiteln von »Überblick« bis »Tipps«, rechts der Text des gewählten Kapitels mit Verweisen auf verwandte Stellen.](bilder/handbuch.png)

**Handbuch … (F1)** – dieselben Erklärungen im Programm, nach Kapiteln
geordnet und untereinander verlinkt.

**Suchsprache …**, **Was das Journal ist …**, **Postfach aufräumen …**,
**Tipps …** – führen ins selbe Handbuch, nur gleich ans passende Kapitel.

## Die Bilder erneuern

Die Abbildungen entstehen aus einem Skript, nicht von Hand:

```bash
python werkzeuge/screenshots.py
```

Es legt ein kleines Archiv mit erfundener Post an, rendert die Fenster und
schreibt die Bilder nach `docs/bilder`. So veralten sie nicht still, wenn sich
die Oberfläche ändert – und es steht nie fremde Post darin.
