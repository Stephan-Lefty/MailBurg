[Übersicht](../README.md) | [Anleitungen](README.md) | [Die Oberfläche](oberflaeche.md) | [Postfach entlasten](postfach-entlasten.md) | [Sichern](sicherung.md)

# Erste Schritte

Von der Installation bis zum ersten durchsuchbaren Archiv. Rechnen Sie mit
zehn Minuten – der erste Abruf läuft danach im Hintergrund weiter.

Alle Bilder in dieser Anleitung zeigen erfundene Postfächer.

## 1. Installieren

### Ubuntu, Mint, Fedora, Arch und alle übrigen: das AppImage

Eine Datei, ausführbar machen, starten. Kein Python, keine Paketverwaltung,
keine Rücksicht auf die Distribution. Das AppImage hängt an der
[jüngsten Veröffentlichung](https://github.com/Stephan-Lefty/MailBurg/releases/latest).

```bash
chmod +x MailBurg-x86_64.AppImage
./MailBurg-x86_64.AppImage
```

Wer lieber klickt: In den Dateieigenschaften gibt es ein Häkchen „Datei als
Programm ausführen" (die Beschriftung unterscheidet sich je nach
Arbeitsumgebung). Danach genügt ein Doppelklick.

> **Legen Sie die Datei an einen festen Platz, bevor Sie den regelmäßigen
> Abruf einrichten** – etwa nach `~/Programme/`. In den Zeitplan schreibt
> MailBurg den vollen Pfad der Datei; wird sie später verschoben, holt der
> Abruf keine Post mehr. MailBurg merkt das beim nächsten Öffnen und bietet
> an, es geradezuziehen, aber bis dahin fehlt Ihnen die Post dieser Zeit.

Zum Aktualisieren die neue Datei über die alte legen – der Name bleibt
gleich, damit der Zeitplan weiter stimmt.

**Was das AppImage kostet:** Es bringt Qt mit, rund 200 MB, und bekommt
dessen Sicherheitsupdates deshalb nicht über Ihre Distribution, sondern erst
mit der nächsten Fassung von MailBurg. Wer Debian 13 oder GuideOS betreibt,
nimmt darum besser das `.deb` – gleich hier darunter.

### Debian 13 und GuideOS: das fertige Paket

Eine Datei herunterladen, ein Befehl, fertig. Das `.deb` hängt an der
[jüngsten Veröffentlichung](https://github.com/Stephan-Lefty/MailBurg/releases/latest).

```bash
sudo apt install ./mailburg_*_all.deb
```

Der Stern steht dort statt einer Versionsnummer: So stimmt der Befehl
auch nach der nächsten Veröffentlichung noch.

`apt` holt sich dabei die Oberfläche, den Schlüsselbund und die PDF-Werkzeuge
aus Ihrer Distribution. **MailBurg bringt kein eigenes Qt mit** – sonst bekäme
es dessen Sicherheitsupdates nie. Deshalb wiegt das Paket zwei Megabyte statt
zweihundert.

Danach steht `mailburg` in der Eingabeaufforderung bereit und **MailBurg** im
Anwendungsmenü. Zum Aktualisieren dasselbe mit der neuen Datei; Ihr Archiv
bleibt unangetastet.

> **Unter Ubuntu funktioniert dieser Weg nicht.** Ubuntu führt PySide6 nicht
> in seinen Paketquellen. `apt` installiert MailBurg dort zwar, aber ohne
> Oberfläche – und sagt es nur beiläufig, als nicht erfüllte *Empfehlung*.
> Dasselbe gilt für alles, was auf Ubuntu aufbaut: Linux Mint, Pop!\_OS,
> Zorin. **Nehmen Sie dort das AppImage weiter oben.**
>
> Woran Sie es merken, falls Sie es doch versucht haben: `apt` sagt es Ihnen
> schon beim Installieren, und beim Start geht ein Fenster auf, das nennt,
> was fehlt und wie es zu beheben ist.
>
> **Bis zum 14.09.2026 tat es das nicht.** Der Hinweis ging nur auf die
> Fehlerausgabe – und ein Menüeintrag startet ohne Terminal. Wer MailBurg so
> installiert hatte, klickte und sah gar nichts. Gemeldet hat es ein Anwender
> auf Linux Mint; behoben ist es seit Fassung 1.4.6. Dass es dieses AppImage
> gibt, geht ebenfalls auf seine Rückmeldung zurück.

### Aus dem Quelltext: die Einrichtung im Benutzerordner

Der Weg für alle, die den Quelltext ohnehin haben wollen – und bis zum
AppImage der einzige für Ubuntu und Mint.

```bash
git clone https://github.com/Stephan-Lefty/MailBurg.git
cd MailBurg
./install.sh
```

Das Skript legt eine eigene Python-Umgebung an, installiert MailBurg samt
Oberfläche und trägt einen Menüeintrag unter *Büroprogramme* ein. Es fragt
vorher, was es tut, und braucht keine Verwaltungsrechte.

**Rechnen Sie mit fünf bis fünfzehn Minuten.** Der längste Teil ist die
grafische Oberfläche: PySide6 ist rund 150 MB, und je nach Python-Fassung
werden einzelne Pakete erst für Ihr System übersetzt. Der Fortschritt läuft
dabei mit – solange sich etwas bewegt, ist alles in Ordnung.

Danach steht `mailburg` in der Eingabeaufforderung bereit und **MailBurg** im
Anwendungsmenü.

### Windows

Eine Datei herunterladen, doppelklicken, fertig. Python wird nicht gebraucht,
installiert wird nichts, Administratorrechte braucht es nicht.

Die aktuelle `MailBurg.exe` hängt an der
[jüngsten Veröffentlichung](https://github.com/Stephan-Lefty/MailBurg/releases/latest).
Die Texterkennung für eingescannte PDF ist darin bereits enthalten.

Beim ersten Start warnt Windows: „Der Computer wurde durch Windows geschützt."
Das ist zu erwarten — die Datei ist nicht signiert. **Weitere Informationen** →
**Trotzdem ausführen**. Einzelheiten und die Prüfsumme zum Nachrechnen in
[MailBurg unter Windows](windows.md).

### Zwei Werkzeuge, die MailBurg mitbringt

`install.sh` bietet an, zwei Systempakete mitzuinstallieren, und antwortet man
nicht ausdrücklich mit Nein, tut es das auch:

| Paket | wofür |
|---|---|
| **poppler** | holt Text aus PDF – schnell und zuverlässig |
| **tesseract** samt deutschen Sprachdaten | liest *eingescannte* PDF, also Rechnungen, die als Foto einer Seite ankommen |

**Sagen Sie hier möglichst Ja.** Ohne tesseract ist der Inhalt eingescannter
Dokumente für die Suche unsichtbar – nicht langsamer auffindbar, sondern gar
nicht. Und das merkt man erst, wenn man Jahre später vergeblich nach einer
Rechnung sucht, die im Archiv liegt.

Zum Nachrüsten, falls Sie beim ersten Mal abgelehnt haben:

```bash
# Debian, Ubuntu, GuideOS, Mint
sudo apt install poppler-utils tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng

# Arch, Manjaro
sudo pacman -S poppler tesseract tesseract-data-deu tesseract-data-eng

# Fedora
sudo dnf install poppler-utils tesseract tesseract-langpack-deu

# openSUSE
sudo zypper install poppler-tools tesseract-ocr tesseract-ocr-traineddata-german

# macOS
brew install poppler tesseract tesseract-lang
```

Ob es geklappt hat, sagt Ihnen:

```bash
tesseract --list-langs
```

Steht dort `deu`, ist alles bereit. In der Windows-Fassung sind beide Werkzeuge
samt deutschen Sprachdaten bereits eingepackt — dort genügt
`MailBurg.exe werkzeuge`, um es nachzusehen. Einzelheiten in
[MailBurg unter Windows](windows.md).

**Ohne diese Pakete läuft MailBurg vollständig** – Abrufen, Suchen,
Aufbewahrungsfristen, Sicherung. Nur Bilder von Seiten bleiben stumm.

### Und die Python-Zusätze

Das gilt für die beiden Systemprogramme oben. MailBurg selbst kennt daneben
vier Zusätze, die `install.sh` alle mitinstalliert – wer stattdessen `pip`
benutzt, wählt sie selbst:

| Zusatz | wofür |
|---|---|
| `oberflaeche` | das Fenster (PySide6) |
| `imap` | Postfächer abrufen, Passwörter im Schlüsselbund |
| `anhaenge` | Text aus PDF und Büroformaten |
| `packen` | kleinere Sicherungen (Zstandard) |

```bash
pip install "mailburg[alles]"        # alles auf einmal
pip install "mailburg[oberflaeche,imap]"   # nur Fenster und Abruf
```

**`oberflaeche` allein genügt nicht zum Abrufen.** Heraus käme ein Programm,
das Postfächer einrichten kann, aber keine Passwörter behält – dafür sorgt
`imap`.

## 2. Der erste Start

Beim ersten Aufruf von **MailBurg** führt ein Assistent durch die Einrichtung.

![Die erste Seite des Einrichtungsassistenten mit dem MailBurg-Logo. Darunter steht, dass Postfächer nur gelesen werden, wohin die Post geht, dass keine Verbindung nach außen aufgebaut wird und keine Suche nach Aktualisierungen stattfindet.](bilder/einrichtung-1.png)

Hier steht, was MailBurg tut und was nicht. Lesen Sie es einmal – es ist die
Grundlage dafür, ob Sie dem Programm Ihre Post anvertrauen wollen.

## 3. Wo das Archiv liegen soll

![Der Schritt »Das Archiv«: eine Auswahl für den Ort mit dem freien Platz dahinter, darunter der vollständige Pfad zum Ändern. Weiter unten die Wahl zwischen Privatarchiv und Geschäftsarchiv, jeweils mit Erklärung, und ein Feld für das Recht, nach dem die Fristen gelten. Ganz unten ein Bereich »Schutz« mit dem nicht angekreuzten Häkchen »Das Archiv verschlüsseln (neu)«.](bilder/einrichtung-2.png)

MailBurg schlägt Orte vor und zeigt, wie viel Platz dort frei ist. **Wählen
Sie möglichst nicht die Platte, auf der Ihr Betriebssystem liegt** – geht die
kaputt, wäre sonst beides weg. Eine externe Platte ist eine gute Wahl.

Darunter entscheiden Sie zwischen zwei Betriebsarten:

**Privatarchiv** – keine Aufbewahrungsfristen, löschen jederzeit möglich. Das
entspricht der Rechtslage: Wer ausschließlich eigene Post archiviert,
unterliegt der DSGVO gar nicht.

**Geschäftsarchiv** – jeder Vorgang wird protokolliert, die Kette der Einträge
gegen nachträgliche Änderungen gesichert, gelöscht wird nur mit Vermerk.
Außerdem gelten die Aufbewahrungsfristen des gewählten Rechtsraums
(Deutschland, Österreich, Schweiz).

> **Führen Sie im Zweifel zwei Archive.** Geschäftliche Post gehört ins
> Geschäftsarchiv, private ins Privatarchiv. Das ist keine Ordnungsliebe: Ein
> Geschäftsarchiv bremst das Löschen jahrelang, während die DSGVO für
> Gesundheitsdaten und Ähnliches das Gegenteil verlangt.

Ganz unten steht **Schutz** mit dem Häkchen *Das Archiv verschlüsseln*. Lassen
Sie es beim ersten Mal aus. Es lohnt sich, wenn das Archiv auf einer externen
Platte liegt, in eine Cloud gesichert wird oder auf einem Server steht — dann
lesen Sie vorher [Das Archiv verschlüsseln](verschluesselung.md). Zwei Dinge
sollten Sie wissen, bevor Sie es setzen: Ohne Passwort oder Notschlüssel kommt
niemand mehr an die Mails, und nachträglich verschlüsseln lässt sich ein Archiv
nicht.

## 4. Postfächer

![Der Schritt »Ihre Postfächer«: drei aus Thunderbird übernommene Postfächer, angekreuzt, mit Serveradresse darunter und je einem Passwortfeld. Darüber die Erklärung, warum MailBurg die Passwörter nicht aus Thunderbird ausliest.](bilder/einrichtung-3.png)

Ist Thunderbird installiert, liest MailBurg dessen Einstellungen aus – Server,
Benutzername und Verschlüsselung stehen dann schon da.

**Die Passwörter müssen Sie einmal von Hand eingeben.** Technisch ließen sie
sich mitlesen, aber ein Programm, das die Passwörter anderer Programme
abgreift, verhält sich wie Schadsoftware. Einem Archiv vertrauen Sie
jahrzehntealte Post an; dieses Vertrauen ist mehr wert als die gesparte
Tipparbeit.

Abgelegt werden sie im Schlüsselbund Ihres Systems – KDE-Brieftasche,
GNOME-Schlüsselbund, Windows-Anmeldeinformationsverwaltung –, nie in einer
Datei des Programms.

Jedes Postfach wird sofort ausprobiert. Sie sehen also gleich, ob es klappt.

**Wenn ein Zertifikat abgelehnt wird:** Läuft Ihr Mailserver bei einem größeren
Anbieter, weist er sich oft unter dessen Namen aus. MailBurg sieht dann nach,
für welchen Namen das Zertifikat gilt, und schlägt ihn vor. Nehmen Sie den
Vorschlag an – danach ist die Verbindung vollständig geprüft. Eine Möglichkeit,
die Prüfung einfach abzuschalten, gibt es bewusst nicht.

Postfächer ohne Thunderbird tragen Sie über **Weiteres Postfach von Hand
eintragen …** ein. Einzelheiten zu App-Passwörtern bei Gmail, GMX und Web.de
stehen in [Postfächer einrichten](postfaecher-einrichten.md) — dort steht auch,
warum Microsoft-Konten derzeit nicht gehen — und warum es bei **Proton** ohne
die Bridge gar nicht geht:
[Proton geht nur über die Bridge](postfaecher-einrichten.md#proton-geht-nur-über-die-bridge).

## 5. Fertig

![Die Abschlussseite: der Ort des Archivs, die Zahl der eingerichteten Postfächer und der Schlüsselbund, in dem die Passwörter liegen. Darunter die Häkchen für den regelmäßigen Abruf im Hintergrund samt Abstand und für den ersten Abruf gleich jetzt.](bilder/einrichtung-4.png)

Hier lässt sich gleich einstellen, dass MailBurg regelmäßig im Hintergrund
abruft. Dafür muss das Programm weder geöffnet bleiben noch mitstarten – nötig
ist nur, dass Sie angemeldet sind, weil daran der Schlüsselbund hängt.

Der erste Abruf holt alles. Bei einem gewachsenen Bestand dauert das; Sie
können weiterarbeiten, und wenn Sie abbrechen, macht der nächste Lauf dort
weiter.

## 6. Suchen

![Das Hauptfenster nach einer Suche nach »rechnung«: links der Baum der Postfächer und Ordner, oben die drei Treffer mit Datum, Absender und Betreff, darunter die gewählte Nachricht mit Kopfzeilen, Text und einem Anhang, der sich öffnen oder speichern lässt.](bilder/hauptfenster.png)

Schreiben Sie einfach hinein, wonach Sie suchen. Gesucht wird in Betreff,
Text, Absender, Empfänger und in den Anhängen.

Unter dem Suchfeld steht das Ergebnis, links stehen Ihre Postfächer mit ihren
Ordnern, rechts die Treffer und darunter die gewählte Nachricht.

Ein **Doppelklick** öffnet eine Nachricht in einem eigenen Fenster. Mit der
**rechten Maustaste** öffnen Sie sie in Ihrem Mailprogramm, legen sie in ein
Postfach zurück oder speichern sie als Datei.

**Eine Suche, die Sie öfter brauchen, können Sie behalten.** *Suchen → Diese
Suche als Suchordner sichern …* gibt ihr einen Namen und stellt sie links in
den Baum, unter die Postfächer. Ein Klick darauf sucht wieder danach – und
zwar immer nach dem heutigen Stand: Was morgen ankommt und dazugehört, steht
darin, ohne dass Sie etwas einsortieren. An Ihrer Post ändert ein Suchordner
nichts; er ist nur ein Name für eine Frage.

Mehr zur Oberfläche: [Die Oberfläche](oberflaeche.md).
Mehr zur Suchsprache: **Hilfe → Suchsprache** oder `mailburg suchhilfe`.

## 7. Und dann?

Drei Dinge lohnen sich gleich am Anfang:

**Eingescannte PDF lesbar machen.** Unter *Post → Eingescannte PDF lesen …*
steht, wie viele Dokumente noch ein weißes Blatt für die Suche sind.

**Eine Sicherung einrichten.** MailBurg ist ein Archiv, kein Backup – siehe
[Das Archiv sichern](sicherung.md).

**Das Postfach entlasten.** Der eigentliche Zweck: erst nachweisen, dass alles
im Archiv ist, dann beim Anbieter aufräumen –
[Postfach entlasten](postfach-entlasten.md).

## 8. Auf den neuesten Stand bringen

MailBurg sieht **nicht** von selbst nach, ob es etwas Neues gibt. Ein
Archivprogramm, das beim Start nach Hause telefoniert, wäre das Gegenteil
dessen, was hier sonst gilt: Es verbindet sich ausschließlich mit den
Mailservern, die Sie eingetragen haben.

Welche Fassung bei Ihnen läuft, sagt `mailburg --version` oder im Fenster
*Hilfe → Info*. Was es Neues gibt, steht bei den
[Veröffentlichungen](https://github.com/Stephan-Lefty/MailBurg/releases).

### Linux

Neuen Stand holen, Einrichtung wiederholen:

```bash
cd ~/MailBurg
git pull
./install.sh --ohne-pakete
```

`--ohne-pakete` überspringt die Frage nach poppler und tesseract – die liegen
ja schon auf Ihrem Rechner. Ohne die Angabe fragt das Skript noch einmal
nach; schaden tut das nicht.

**Rechnen Sie wieder mit fünf bis fünfzehn Minuten.** Die Python-Umgebung
wird dabei neu aufgebaut, und der längste Teil daran ist erneut die
grafische Oberfläche.

> **Ihr Archiv bleibt unberührt.** `install.sh` fasst es nie an – auch
> `--entfernen` nimmt nur das Programm weg. Dasselbe gilt für die
> Kontenliste, den Suchindex und die Passwörter im Schlüsselbund.

**Wenn Sie den regelmäßigen Abruf eingerichtet haben**, läuft er unverändert
weiter: Er zeigt auf `~/.local/bin/mailburg`, und dieser Verweis bleibt
derselbe.

**Bei einem Sprung auf eine neue Hauptfassung** kann es vorkommen, dass der
Suchindex neu gebaut werden muss. Dann sagt MailBurg das beim Öffnen und
nennt den Befehl dazu (`mailburg neuaufbau IHR-ARCHIV`). Verloren geht dabei
nichts – der Index entsteht vollständig aus dem Archiv.

### Wenn Ihre Distribution Python anhebt

Arch, Manjaro und Verwandte tauschen Python mitunter gegen eine neue
Hauptfassung aus und entfernen die alte. MailBurgs eigene Python-Umgebung
liegt dann daneben: Sie sucht ihre Bestandteile unter der alten Fassung, die
es nicht mehr gibt.

**MailBurg sagt das seit Fassung 1.5.2 in einem Satz**, statt mit einem
Traceback abzubrechen – und zwar mit dem wichtigsten Satz zuerst: *Ihr
Archiv ist davon nicht betroffen.* Es liegt außerhalb dieser Umgebung,
ebenso Ihre Postfächer, der Suchindex und die Passwörter. Verloren geht
nichts.

Die Abhilfe ist dieselbe wie beim Aktualisieren:

```bash
cd ~/MailBurg
./install.sh --ohne-pakete
```

Wer über die Paketverwaltung installiert hat – das `.deb` oder das
AppImage –, ist davon gar nicht erst betroffen.

### Windows

Die neue `MailBurg.exe` von der
[jüngsten Veröffentlichung](https://github.com/Stephan-Lefty/MailBurg/releases/latest)
herunterladen und die alte damit ersetzen. Mehr ist es nicht: Die Datei
bringt alles mit, und Ihre Einstellungen liegen ohnehin woanders.

### Warum es kein Paket gibt

Ein `.deb`, ein AppImage oder ein Eintrag in den Paketquellen wären der
bequemere Weg, und beides steht auf der Liste ([TODO.md](../TODO.md)). Bis
dahin ist `git pull` und `./install.sh` der Weg – umständlicher, aber
durchschaubar: Sie sehen, was Sie bekommen.
