[Deutsch](mailstore-umzug.md) | [Übersicht](../README.md) | [Anleitungen](README.md) | [MailBurg Server](mailburg-server.md)

# Aus MailStore nach MailBurg umziehen

MailStore Home gibt es nicht mehr, und wer ein Archiv damit aufgebaut
hat, steht vor der Frage, wie die Post herauskommt. Diese Anleitung
beschreibt den Weg, der im Oktober 2026 an einem Bestand von **827.198
Mails** gegangen wurde – zweiunddreißig Archive, achtzehn Konten, ein
Firmenserver im Alltagsbetrieb.

**Der Weg führt über EML-Dateien**, und das ist die gute Nachricht:
Eine `.eml` ist die Mail in genau der Form, in der sie über das Netz
ging. Nichts wird umgeschrieben, nichts geht verloren – auch die
DKIM-Signatur nicht.

## 1. Was Sie vorher wissen sollten

**Jede Mail wird eine Datei.** Bei 800.000 Mails sind das 800.000
Dateien. Für das Einlesen ist das kein Problem; wer die Exporte aber
über ein Netzlaufwerk oder auf eine externe Platte kopiert, sollte
wissen, dass eine Million kleiner Dateien ein Vielfaches derselben
Datenmenge in einer großen Datei braucht.

**Platz:** Rechnen Sie mit etwa demselben Umfang wie im alten Archiv,
und zwar zusätzlich – während des Umzugs liegen beide nebeneinander.
Dazu kommt der Suchindex mit rund 15 MB je 1.000 Mails.

**Der Kontoname lässt sich später nicht ändern.** Er steht im Journal,
und das Journal wird nicht umgeschrieben – es ist der Nachweis.
Überlegen Sie die Namen, bevor Sie den ersten Lauf starten.

## 2. Den Virenscanner aussperren – vor dem ersten Export

**Ein Mailarchiv enthält zwangsläufig alte Schadsoftware.** Zwanzig
Jahre Geschäftspost bringen Phishing-Mails, Makroviren und Trojaner
mit; sie gehören ins Archiv, weil die Korrespondenz vollständig sein
muss. Ein Virenscanner sieht das anders und greift zu.

**Was dabei passiert, ist der schlimmste Fall:** Die Mail verschwindet,
und das Archiv sieht weiterhin vollständig aus.

Setzen Sie die Ausnahmen für **beide** Orte, bevor Sie anfangen:

```
Add-MpPreference -ExclusionPath "D:\Archiv"
Add-MpPreference -ExclusionPath "C:\Users\…\Downloads\admin"
```

**Der Exportordner gehört dazu, nicht nur das Archiv.** Am 06.10.2026
hat der Defender dem MailStore-Client eine Mail aus der Hand genommen,
während er sie exportierte – Echtzeitschutz, `PWS:HTML/Phish`,
Quarantäne. Sie kam nie als Datei im Ordner an und wurde folglich nie
eingelesen. Im Protokoll des Einlesens steht davon nichts: MailBurg hat
diese Datei nie gesehen.

Nachsehen lässt sich das hinterher so:

```
Get-WinEvent -FilterHashtable @{LogName="Microsoft-Windows-Windows Defender/Operational"; Id=1116,1117} | Select-Object TimeCreated, Id | Format-Table
```

**Und die Ausnahme wieder herausnehmen, wenn der Umzug durch ist** –
jedenfalls für den Exportordner. Für das Archiv bleibt sie: Dort liegt
die Post dauerhaft, und sie soll dauerhaft liegen bleiben.

## 3. Aus MailStore exportieren

Nachgeschlagen in der
[Hersteller-Dokumentation](https://help.mailstore.com/de/server/E-Mails_exportieren),
nicht aus dem Gedächtnis:

1. Rechtsklick auf einen Eintrag im Ordnerbaum
2. **Exportieren nach …**
3. Ziel: **Verzeichnis (Dateisystem)**
4. Dateiformat: **EML**
5. Option **Ordnerstruktur beibehalten** einschalten

Es gibt außerdem **Vorhandenen Export aktualisieren** – das gleicht
über die Dateinamen ab und schreibt nur Neues. Für einen Export in
Etappen ist das der richtige Schalter.

**Exportieren Sie Postfach für Postfach**, nicht alles auf einmal. Nur
dann entscheiden Sie je Postfach, unter welchem Namen es in MailBurg
erscheint.

## 4. Die Verzeichnisse benennen

**Der Ordnername wird der Kontoname.** Das ist der ganze Trick an
dieser Anleitung: Wenn Sie die Exporte gleich richtig benennen, ist das
Einlesen danach stumpfe Arbeit.

Benennen Sie je Person oder Bereich **einen** Ordner und legen Sie alle
Quellen dieser Person hinein:

```
Downloads\admin\
├── mueller (MailStore)\
│   ├── mueller@firma.example\      <- altes Postfach
│   ├── mueller@alt.example\        <- noch älteres
│   └── Archiv von mueller\         <- Benutzerarchiv
├── buchhaltung (MailStore)\
└── sonstige (MailStore)\           <- was sich niemandem zuordnen lässt
```

**Der Zusatz `(MailStore)` ist kein Schmuck.** Läuft das Postfach in
MailBurg weiter, gibt es dort schon ein Konto – meist unter der
Mailadresse. Mit dem Zusatz sehen Sie an jedem Treffer, aus welcher
Quelle er stammt. Das ist während der Wochen, in denen beide Archive
parallel laufen, genau die Auskunft, die man für Stichproben braucht.

**Nennen Sie den Ordner nicht genauso wie den Adressteil des laufenden
Postfachs.** »Buchhaltung« neben `buchhaltung@firma.example` sähe in
der Postfachspalte des Browsers fast gleich aus. »Buchhaltung
(MailStore)« nicht.

**Was sich niemandem zuordnen lässt, kommt nach »sonstige«.** Das ist
keine Einbahnstraße: Der Name des Unterverzeichnisses bleibt als
Oberordner erhalten, Sie sehen also weiterhin, woher jede Mail kam.

## 5. Den Dienst anhalten

**Nur bei der Server-Variante, und dort ist es Pflicht.** Zwei
Vorgänge, die gleichzeitig ins selbe Archiv schreiben, reißen die
Hash-Kette.

```
sc.exe stop MailBurgServer
sc.exe query MailBurgServer
```

`sc.exe stop` kehrt zurück, bevor der Dienst unten ist – warten Sie,
bis bei `query` der Zustand **STOPPED** steht.

**Nach einem Neustart läuft er von selbst wieder**, denn er ist auf
»verzögert automatisch« eingerichtet. Wer über mehrere Tage am Archiv
arbeitet, muss ihn nach jedem Neustart erneut anhalten.

**Und er hält den Suchindex, solange er läuft.** Das betrifft nicht nur
das Einlesen: Auch `neuaufbau` und `texterkennung` schreiben in den
Index und warten dann – ohne Meldung – darauf, dass er frei wird. Von
außen sieht das aus wie ein hängender Befehl. Am 07.10.2026 hat uns das
eine halbe Stunde Fehlersuche gekostet.

## 6. Erst einen, zum Messen

Nehmen Sie das kleinste Postfach, am besten eines, das **auch weiterhin
abgerufen wird**:

```
mailburg importieren D:\Archiv "C:\…\admin\mueller (MailStore)" --konto "mueller (MailStore)"
```

Zwei Zahlen in der Ausgabe sind wichtig:

**Die Dauer.** Rechnen Sie hoch, wie lange der ganze Bestand braucht.
Bei 70.000 Mails über `pypdf` waren es gut hundert Minuten; mit
`pdftotext` aus poppler ein Bruchteil davon. Bei 800.000 Mails ist das
der Unterschied zwischen einer Nacht und einem Wochenende.

**»Bereits vorhanden«.** Läuft das Postfach in MailBurg schon, sollten
die Mails dort als Dubletten erkannt werden. Passiert das nicht, gibt
MailStore sie nicht bytegenau heraus – dann lägen am Ende viele Mails
zweimal im Archiv, einmal über jeden Weg. Das wissen Sie nach diesem
einen Lauf statt nach zwanzig Stunden.

> **Dubletten sortieren Sie nicht vorher aus.** Der Name einer Mail im
> Archiv *ist* der Hash ihres Inhalts; eine zweite Kopie kann es
> technisch nicht geben. Gemessen an drei Exporten mit absichtlichen
> Dreifach-Dubletten: neun Dateien gelesen, fünf aufgenommen, vier
> bereits vorhanden.

## 7. Den Rest abarbeiten

Wenn die Zahlen stimmen, läuft der Rest von selbst:

```
Get-ChildItem -Directory $quelle | ForEach-Object {
  Write-Host "=== $($_.Name)"
  mailburg importieren $archiv $_.FullName --konto $_.Name
}
```

Mit Protokoll, damit Sie hinterher nachsehen können:

```
… | Tee-Object -Append "$quelle\einlesen.log"
```

**Setzen Sie vorher einmal die Ausgabekodierung**, sonst ist das
Protokoll hinterher nicht durchsuchbar:

```
$env:PYTHONIOENCODING = "utf-8"
```

Die Windows-Konsole schreibt in einer alten Codepage, und `Tee-Object`
schreibt das durch. In der Datei steht dann »▄bergangen« statt
»Übergangen« und »Gel÷schte Elemente« statt »Gelöschte Elemente« – eine
Suche nach dem richtigen Wort findet nichts. Am 07.10.2026 hat das eine
Stunde gekostet und zu der falschen Annahme geführt, es seien 295.072
Mails verloren gegangen.

**Oder einzeln und nacheinander.** Nach jedem Lauf steht die Bilanz da,
und wenn etwas klemmt, betrifft es ein Postfach statt achtzehn.

## 8. Nachsehen und den Dienst starten

```
mailburg info D:\Archiv
mailburg pruefen D:\Archiv
```

`pruefen` rechnet die Hash-Kette nach und hält jeden Journaleintrag
gegen die Ablage. Die Mails selbst werden dabei nicht gelesen, nur ihre
Dateinamen – deshalb ist es schneller als `info`, das für die Zeile
»Auf Platte« jede einzelne Datei anfasst.

**Fehlt eine Mail, nennt MailBurg sie mit Postfach, Datum, Absender und
Betreff** – und mit dem Zeitpunkt, an dem sie ins Archiv aufgenommen
wurde:

```
  FEHLEND:     2 Mails ohne Datei
    - 5286d60406624ea9…  mueller@firma.example / INBOX
      02.10.2026, 15:45, von partner@beispiel.example
      WG: Einkaufspreis für die OVL XL
      aufgenommen 02.10.2026, 15:59 als Eintrag 70763
```

**Lesen Sie die beiden Datumsangaben getrennt.** Das erste steht im
Kopf der Mail und kann Jahre zurückliegen; »aufgenommen« sagt, wann die
Mail ins Archiv kam. Nur das Zweite beantwortet die Frage, wann der
Verlust entstanden sein kann – und genau diese Verwechslung hat am
07.10.2026 eine Ursachensuche in die falsche Richtung geschickt.

Danach:

```
sc.exe start MailBurgServer
```

## 9. Die Vollständigkeit ausrechnen

**Das ist der Nachweis, auf den es ankommt** – und er ist keine
Stichprobe, sondern eine Rechnung, die ohne Rest aufgehen muss. Gefragt
ist: Was ist aus jeder einzelnen ausgegebenen Datei geworden?

Zuerst die Zahl, die alles verankert – wie viele Dateien tatsächlich
dalagen:

```
Get-ChildItem "C:\…\admin" -Recurse -Filter *.eml | Measure-Object | Select-Object Count
```

Dann aus dem Protokoll die gelesenen Dateien und die Dubletten:

```
Select-String -Path "C:\…\einlesen.log" -Pattern "^Fertig:" | ForEach-Object { $_.Line }
```

Und die Ordner, die ausgelassen wurden:

```
Select-String -Path "C:\…\einlesen.log" -Pattern "bergangen" | ForEach-Object { $_.Line }
```

Die Rechnung sieht dann so aus – die Zahlen stammen vom Umzug am
07.10.2026:

```
827.199  Dateien ausgegeben
-295.072  Papierkorb, Spamverdacht, Entwürfe (nicht gelesen)
 532.127  gelesen
- 13.373  bereits vorhanden
 518.754  neu aufgenommen
+ 70.283  Bestand vor der Übernahme
 589.037  erwartet  ·  589.058 im Archiv (21 aus dem laufenden Abruf)
```

**Geht die Rechnung nicht auf, suchen Sie nicht nach einer Erklärung,
sondern nach der Ursache.** Bei uns schien zunächst ein Drittel des
Bestands zu fehlen – tatsächlich hatten wir die Meldung über die
übergangenen Ordner nicht gefunden, weil wir mit einem Umlaut gesucht
haben (siehe Abschnitt 7).

**Die Zahl der ausgelassenen Dateien lässt sich gegenprüfen**, ohne dem
Protokoll zu glauben:

```
Get-ChildItem "C:\…\admin" -Recurse -Filter *.eml | Where-Object { $_.FullName -match "Gel.schte Elemente|Junk|Entw|Trash|Spam" } | Measure-Object | Select-Object Count
```

Stimmt diese Zahl mit der Differenz überein, ist die Rechnung von zwei
Seiten belegt. Bei uns stimmte sie auf die Datei.

**Und bewahren Sie `einlesen.log` auf.** Es ist der Beleg dafür, welche
Ordner ausgelassen wurden – ohne die Datei steht in Ihrem Protokoll eine
Behauptung.

## 10. Beide Archive eine Weile parallel

**Löschen Sie das alte Archiv nicht sofort.** Vier bis sechs Wochen
beide laufen lassen und Stichproben machen – suchen Sie dieselben
Begriffe in beiden und vergleichen Sie, was herauskommt.

Ein Archiv, aus dem etwas fehlt, sieht genauso aus wie ein
vollständiges. Das ist der Grund für diese Wartezeit, und sie ist der
einzige Weg, die Vollständigkeit zu belegen.

## 11. Den Vorgang protokollieren

**Bei geschäftlicher Post gehört der Umzug belegt.** Nachvollziehbar
sein muss, wie die Daten in das System gekommen sind und dass dabei
nichts verändert wurde – das verlangen die GoBD, und es ist ohnehin
die Frage, die in fünf Jahren jemand stellt.

Dafür gibt es eine Vorlage zum Ausfüllen:
**[Übernahmeprotokoll](uebernahmeprotokoll-vorlage.md)**.

**Schreiben Sie die Zahlen mit, während der Umzug läuft.** Am Ende
jedes Laufs steht die Bilanz; hinterher ist sie nur noch mühsam zu
rekonstruieren, und was man rekonstruiert, ist keine Messung mehr.

## Was dabei nicht mitkommt

**Einstufungen, Markierungen und Aufbewahrungsvermerke aus MailStore.**
Eine `.eml` enthält die Mail, nicht die Verwaltungsdaten des Programms,
das sie archiviert hat.

**Der Lesezustand** bleibt bei EML ebenfalls draußen – das Format kennt
ihn nicht.

Beides lässt sich in MailBurg neu vergeben; aus einem anderen Programm
übernehmen lässt es sich nicht.
