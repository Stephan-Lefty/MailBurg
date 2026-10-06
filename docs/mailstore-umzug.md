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

## 2. Aus MailStore exportieren

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

## 3. Die Verzeichnisse benennen

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

## 4. Den Dienst anhalten

**Nur bei der Server-Variante, und dort ist es Pflicht.** Zwei
Vorgänge, die gleichzeitig ins selbe Archiv schreiben, reißen die
Hash-Kette.

```
sc.exe stop MailBurgServer
sc.exe query MailBurgServer
```

`sc.exe stop` kehrt zurück, bevor der Dienst unten ist – warten Sie,
bis bei `query` der Zustand **STOPPED** steht.

## 5. Erst einen, zum Messen

Nehmen Sie das kleinste Postfach, am besten eines, das **auch weiterhin
abgerufen wird**:

```
mailburg importieren D:\Archiv "C:\…\admin\sitebah (MailStore)" --konto "sitebah (MailStore)"
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

## 6. Den Rest abarbeiten

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

**Oder einzeln und nacheinander.** Nach jedem Lauf steht die Bilanz da,
und wenn etwas klemmt, betrifft es ein Postfach statt achtzehn.

## 7. Nachsehen und den Dienst starten

```
mailburg info D:\Archiv
mailburg pruefen D:\Archiv
```

`pruefen` geht die Hash-Kette durch. Danach:

```
sc.exe start MailBurgServer
```

## 8. Beide Archive eine Weile parallel

**Löschen Sie das alte Archiv nicht sofort.** Vier bis sechs Wochen
beide laufen lassen und Stichproben machen – suchen Sie dieselben
Begriffe in beiden und vergleichen Sie, was herauskommt.

Ein Archiv, aus dem etwas fehlt, sieht genauso aus wie ein
vollständiges. Das ist der Grund für diese Wartezeit, und sie ist der
einzige Weg, die Vollständigkeit zu belegen.

## Was dabei nicht mitkommt

**Einstufungen, Markierungen und Aufbewahrungsvermerke aus MailStore.**
Eine `.eml` enthält die Mail, nicht die Verwaltungsdaten des Programms,
das sie archiviert hat.

**Der Lesezustand** bleibt bei EML ebenfalls draußen – das Format kennt
ihn nicht.

Beides lässt sich in MailBurg neu vergeben; aus einem anderen Programm
übernehmen lässt es sich nicht.
