[Übersicht](../README.md) | [Anleitungen](README.md) | [Erste Schritte](erste-schritte.md) | [Postfach entlasten](postfach-entlasten.md) | [Regelmäßig abrufen](zeitsteuerung.md) | [Windows](windows.md)

# Das Archiv sichern

## Warum überhaupt

**MailBurg ist ein Archiv, kein Backup.** Der Unterschied ist nicht
akademisch: Ihr Archiv liegt auf *einer* Platte. Geht die kaputt, ist alles
weg – Mails, Protokoll, Nachweisbarkeit. Eine Sicherung ist eine Kopie an
einem *zweiten* Ort.

Wer sein Postfach beim Anbieter leert, weil ja alles im Archiv liegt, und
dieses Archiv nur einmal vorhält, hat seine Sicherheit nicht erhöht, sondern
verlagert. Vorher lagen die Mails beim Anbieter *und* im Mailprogramm.

## Eine Datei statt zehntausend

```bash
mailburg sichern ~/Archiv ~/Sicherungen
```

Das packt das gesamte Archiv in eine einzelne Datei. In der Oberfläche geht
dasselbe über **Archiv → Archiv sichern …**

**Kleiner wird dabei kaum etwas.** Ihre Mails liegen bereits komprimiert;
gemessen an einem Archiv mit 9.300 Mails: ein Prozent. Nur das Protokoll
schrumpft deutlich, macht aber ein Promille des Ganzen aus.

Der Gewinn ist ein anderer: **aus zehntausend Dateien wird eine.**
Cloud-Programme laden jede Datei einzeln hoch, mit eigenem Vorgang und eigener
Prüfung – bei tausenden kleinen dauert das ein Vielfaches von einer großen
gleicher Größe. Und jeder Stand ist eine Datei, kein Ordner, den man mit dem
vorigen vergleichen müsste.

**Der Suchindex kommt nicht mit.** Er liegt außerhalb des Archivs, ändert sich
bei jedem Abruf vollständig und lässt sich aus dem Protokoll neu aufbauen.

### Sammeln oder ersetzen

```bash
# Jeder Lauf legt eine Datei mit Datum an, die letzten sieben bleiben
mailburg sichern ~/Archiv ~/Sicherungen --behalten 7

# Immer dieselbe Datei überschreiben
mailburg sichern ~/Archiv ~/Sicherungen --ersetzen --name Geschaeftsarchiv
```

`--ersetzen` ist für Cloud-Ordner gedacht, deren Anbieter selbst Versionen
führt – Nextcloud etwa. Dort wäre eine wachsende Sammlung doppelt gemoppelt
und kostete Platz.

`--name` bestimmt den Dateinamen unabhängig vom Archivnamen. Umlaute werden
dabei umgeschrieben: `MailBurg-Geschaeftsarchiv.tar.zst`. Ein Dateiname wandert
bei einer Sicherung durch fremde Hände – Cloud-Server, Weboberflächen, fremde
Rechner –, und macOS speichert Umlaute anders als Linux.

## In die Cloud

Hier hört MailBurg auf. Es legt eine Datei in einen Ordner; wie die zu Ihrem
Anbieter kommt, entscheidet dessen Programm. Drei übliche Wege:

### Ein synchronisierter Ordner

Der einfachste Weg, wenn Sie Nextcloud, Dropbox, Drive oder ähnliches als
Desktop-Programm nutzen: Sichern Sie direkt in den synchronisierten Ordner.

```bash
mailburg sichern ~/Archiv ~/Nextcloud/Mailsicherung --ersetzen
```

Das Programm des Anbieters lädt die Datei anschließend von selbst hoch.

**Bei externen Speichern aufpassen.** Eine Storage Box oder ein anderer
serverseitig eingebundener Speicher wird vom Desktop-Programm nicht
zwangsläufig gespiegelt. In den Einstellungen des Nextcloud-Clients lässt er
sich unter *Zu synchronisierende Ordner auswählen* anhaken – taucht er dort
nicht auf, hilft nur einer der folgenden Wege.

### Von Hand hochladen

Über die Weboberfläche des Anbieters. Umständlich, aber es geht immer, und für
eine wöchentliche Sicherung ist es zumutbar.

Liegt die Datei bereits beim Anbieter und soll nur in einen anderen Ordner:
**Verschieben Sie sie in der Weboberfläche, nicht lokal.** Das geschieht
serverseitig, es muss also nichts erneut hochgeladen werden.

### Mit einem eigenen Werkzeug

Für alles, was WebDAV, S3 oder SFTP spricht, gibt es fertige Programme.
`rclone` deckt praktisch alles ab:

```bash
mailburg sichern ~/Archiv /tmp/mailburg-sicherung --ersetzen
rclone copy /tmp/mailburg-sicherung meinecloud:Sicherungen
```

Bei Nextcloud genügt auch `curl` mit einem App-Passwort – dasselbe, das Sie
auch MailBurg für ein Postfach geben würden:

```bash
curl -T MailBurg-Archiv.tar.zst \
  -u benutzer:app-passwort \
  https://cloud.example.org/remote.php/dav/files/benutzer/Sicherungen/
```

## Von selbst

Ein Backup, an das jemand denken muss, ist irgendwann keines mehr.

In der Oberfläche: **Einstellungen → Was von selbst laufen soll (Automatisierung) …**, dort das Häkchen
bei *Das Archiv regelmäßig in eine Datei sichern*, Takt und Zielordner
wählen. MailBurg legt dafür einen systemd-Timer im Benutzerverzeichnis an –
kein Verwaltungsrecht nötig.

Führen Sie mehrere Archive, richten Sie jedes einzeln ein; jedes bekommt
seinen eigenen Zeitplan.

Auf der Kommandozeile geht dasselbe manuell, etwa über cron:

```cron
0 3 * * 0  /home/ich/.local/bin/mailburg sichern --leise --ersetzen ~/Archiv ~/Nextcloud/Sicherung
```

## Zurückholen – und prüfen

Eine Sicherung, die niemand je zurückgeholt hat, ist eine Vermutung.

**Archiv → Sicherung in neues Archiv …** macht aus der Datei wieder ein
Archiv. Das Zielverzeichnis muss leer sein: Zwei Protokolle ineinander ergäben
eines, das sich nicht mehr prüfen lässt.

**Archiv → Sicherung importieren …** nimmt stattdessen die Mails in Ihr
geöffnetes Archiv auf – mit ihrem ursprünglichen Postfach und Ordner. Doppelte
werden erkannt; dieselbe Sicherung lässt sich gefahrlos zweimal einlesen.

**Danach immer `Archiv → Journal prüfen`.** Das vergleicht das Protokoll mit
dem, was tatsächlich angekommen ist. Eine Cloud-Übertragung lässt schon einmal
etwas aus, und bei einem Archiv merkt man das sonst erst Jahre später beim
Suchen.

Probieren Sie das einmal aus, solange Sie es nicht brauchen. Der Tag, an dem
Sie es brauchen, ist der falsche für die erste Übung.

## Was dabei schiefgehen kann

**Die Sicherung liegt neben dem Original.** Dann geht sie mit ihm zusammen
verloren. MailBurg weist ein Ziel innerhalb des Archivs ab, aber dieselbe
Platte kann es nicht erkennen.

**Sichern während eines Abrufs.** Läuft gerade ein Import, erwischt die Kopie
einen Zwischenstand, bei dem eine Mail schon abgelegt, ihr Protokolleintrag
aber noch nicht geschrieben ist. Die Prüfung bemängelt das anschließend in der
Kopie. Die nächste Sicherung räumt es von selbst auf.

**Die Platte läuft voll.** Ohne `--behalten` oder `--ersetzen` sammeln sich
die Stände, und irgendwann scheitert ausgerechnet die Sicherung, auf die es
ankäme.

**Zwei Rechner an einem Archiv.** Ein Archiv in einem synchronisierten Ordner
zu *betreiben* – nicht nur zu sichern – geht nur, solange genau ein Rechner
hineinschreibt. Das Protokoll ist eine Kette; schreiben zwei gleichzeitig,
entstehen zwei Zweige mit demselben Vorgänger, und der Cloud-Dienst macht
daraus eine Konfliktdatei. Auflösen lässt sich das nicht, weil beide Zweige
echte Mails enthalten.
