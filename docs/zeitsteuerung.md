[Übersicht](../README.md) | [Anleitungen](README.md) | [Erste Schritte](erste-schritte.md) | [Postfächer](postfaecher-einrichten.md) | [Windows](windows.md) | [Postfach entlasten](postfach-entlasten.md) | [Sichern](sicherung.md)

# Regelmäßig abrufen

Ein Archiv, das man von Hand füttern muss, wird irgendwann nicht mehr gefüttert.
Der Abruf ist deshalb darauf ausgelegt, in einer Zeitsteuerung zu laufen: Er
holt nur, was neu ist, und braucht keine Eingabe.

```bash
mailburg abrufen ~/Archiv --leise
```

## Wie oft?

**Alle 30 Minuten ist die Vorgabe.** Wählbar sind 10, 30, 60 oder 90 Minuten.

Der Grund für den kurzen Takt ist nicht Bequemlichkeit, sondern eine echte
Gefahr: Wer seinem Mailclient aufträgt, alte Post wegzuräumen, löscht sie bei
einem IMAP-Konto **auf dem Server**. Was MailBurg bis dahin nicht geholt hat,
ist unwiederbringlich weg. Zwischen „Mail kommt an" und „Mail könnte gelöscht
werden" darf deshalb kein großes Fenster liegen.

Die Wahl hängt davon ab, wie viele Konten Sie haben:

| Takt | Wofür |
|------|-------|
| 10 Minuten | Wenige Konten, eigener Mailserver, oder ein Mailclient, der zügig aufräumt |
| 30 Minuten | Der Regelfall |
| 60–90 Minuten | Viele Konten bei großen Anbietern |

**Warum nicht immer zehn Minuten?** Bei dreißig Konten wären das über
viertausend Anmeldungen am Tag. GMX, Web.de und andere drosseln oder sperren
Konten, bei denen sich jemand derart häufig anmeldet – aus ihrer Sicht sieht
das aus wie ein Angriff. Wer viele Postfächer bei großen Anbietern hat, fährt
mit 60 Minuten besser.

Kein Takt schließt das Fenster ganz. Wirklich sicher wird das Aufräumen erst,
wenn Sie vorher nachweisen, dass alles Ältere im Archiv liegt – siehe
[Postfach entlasten](postfach-entlasten.md).

## Der eine Haken: der Schlüsselbund

Die Passwörter liegen im Schlüsselbund des Betriebssystems, und der ist an die
angemeldete Sitzung gebunden. **Läuft der Abruf, während niemand angemeldet ist,
kommt er nicht an die Passwörter.**

Daraus folgt: Der laufende Abruf funktioniert auf einem Rechner, an dem Sie
angemeldet sind. Er funktioniert nicht auf einem Server, an dem sich niemand
anmeldet – und er ruht, solange der Rechner aus ist.

Für den Serverfall gibt es zwei Wege, beide mit Nachteilen:

- **Schlüsselbund ohne Passwort entsperren** (`gnome-keyring-daemon --unlock`
  aus einer Datei). Damit liegt der Hauptschlüssel im Klartext auf der Platte –
  wer an den Rechner kommt, kommt an alle Postfächer.
- **Nur ein Konto, Passwort im Dienst.** Wenn es ohnehin nur um ein
  Sammelpostfach geht, ist ein eigens dafür angelegtes Konto mit eingeschränkten
  Rechten die ehrlichere Lösung.

Ein dritter Weg ist in Arbeit: MailBurg als Dienst mit eigenem Schlüssel, siehe
[TODO.md](../TODO.md).

## Linux: systemd

Der bequeme Weg:

```bash
./install.sh --zeitsteuerung ~/Archiv           # alle 30 Minuten
./install.sh --zeitsteuerung ~/Archiv --alle 10 # alle 10 Minuten
```

Das legt einen Benutzer-Timer an, der fünf Minuten nach dem Hochfahren anläuft
und sich dann im gewählten Takt wiederholt. Gerechnet wird ab dem *Ende* des
letzten Laufs (`OnUnitActiveSec`) – so überholt sich der Abruf nie selbst, auch
wenn ein Durchgang einmal länger dauert als das Intervall.

Nachsehen:

```bash
systemctl --user list-timers mailburg-abruf.timer
journalctl --user -u mailburg-abruf.service
systemctl --user start mailburg-abruf.service   # gleich einmal laufen lassen
```

Der Takt steht in `~/.config/systemd/user/mailburg-abruf.timer` unter
`OnUnitActiveSec`. Nach einer Änderung:

```bash
systemctl --user daemon-reload
systemctl --user restart mailburg-abruf.timer
```

### Ohne systemd: cron

```cron
*/30 * * * * /home/IHRNAME/.local/bin/mailburg abrufen --leise /home/IHRNAME/Archiv >> /home/IHRNAME/.mailburg-abruf.log 2>&1
```

Der volle Pfad ist nötig: cron kennt den Suchpfad der Anmeldesitzung nicht.

## Windows: Aufgabenplanung

**Am einfachsten aus dem Programm heraus:** *Einstellungen → Was von selbst
laufen soll*, Häkchen bei „Neue Post regelmäßig im Hintergrund holen", Abstand
wählen, Übernehmen. Dasselbe steht am Ende der Einrichtung. MailBurg legt die
Aufgabe selbst an; Verwaltungsrechte braucht es dafür nicht.

Angelegt wird sie im Ordner **MailBurg** der Aufgabenplanung (`taskschd.msc`),
je Archiv eine eigene — wer geschäftlich und privat trennt, bekommt zwei. Sie
lässt sich dort ansehen, anhalten und löschen wie jede andere Aufgabe.

Drei Einstellungen darin sind bewusst so gewählt:

| Einstellung | Warum |
|---|---|
| `InteractiveToken` | Läuft nur, während Sie angemeldet sind. Anders kommt der Abruf nicht an die Anmeldeinformationsverwaltung — und damit an kein Passwort. |
| `StartWhenAvailable` | Holt nach, was ausfiel, während der Rechner aus war. Ohne das fällt eine tägliche Sicherung stillschweigend aus. |
| `IgnoreNew` | Ein Durchgang darf länger dauern als der Abstand, ohne dass sich zwei Läufe überschneiden. |

Von Hand anstoßen:

```powershell
Start-ScheduledTask -TaskName "MailBurg\Abruf - MailBurg-Archiv"
```

Der zweite Teil des Namens ist der Ordnername Ihres Archivs.

### Aus dem Quellverzeichnis

Wer MailBurg aus den Quellen betreibt, kann die Aufgabe auch dort anlegen:

```powershell
.\install.ps1 -Zeitsteuerung C:\Archiv            # alle 30 Minuten
.\install.ps1 -Zeitsteuerung C:\Archiv -Alle 10   # alle 10 Minuten
```

## macOS: launchd

Für macOS gibt es kein fertiges Skript. Diese Datei als
`~/Library/LaunchAgents/de.stephanlefty.mailburg.abruf.plist` anlegen und den
Pfad zum Archiv anpassen:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>de.stephanlefty.mailburg.abruf</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/IHRNAME/.local/bin/mailburg</string>
        <string>abrufen</string>
        <string>--leise</string>
        <string>/Users/IHRNAME/Archiv</string>
    </array>
    <key>StartInterval</key>
    <integer>1800</integer>
    <key>StandardErrorPath</key>
    <string>/Users/IHRNAME/Library/Logs/mailburg-abruf.log</string>
</dict>
</plist>
```

Scharf schalten:

```bash
launchctl load ~/Library/LaunchAgents/de.stephanlefty.mailburg.abruf.plist
launchctl start de.stephanlefty.mailburg.abruf
```

## Was der Abruf ausgibt

Je Konto eine Zeile mit dem, was geholt wurde. Der Rückgabewert ist 0, wenn
alles geklappt hat, und 1, wenn sich mindestens ein Konto nicht anmelden konnte
– darauf lässt sich eine Benachrichtigung aufbauen.

Mails, an denen sich MailBurg verschluckt hat, werden vorgemerkt und beim
nächsten Lauf erneut angefordert. Der Lauf meldet, wie viele es waren.

## Und das Siegel?

In einem Geschäftsarchiv gehört regelmäßig ein Siegel über den Stand – aber
**nicht nach jedem Abruf**. Bei einem Takt von dreißig Minuten wären das fast
fünfzig Siegel am Tag; das bläht das Journal auf, ohne die Aussage zu
verbessern. Einmal täglich genügt, als eigener Eintrag in der Zeitsteuerung:

```cron
0 23 * * * /home/IHRNAME/.local/bin/mailburg siegel /home/IHRNAME/Archiv
```

Das Siegel hält fest, wie weit die Hash-Kette zu diesem Zeitpunkt reichte. Ein
späterer Eingriff lässt sich damit auf den Abschnitt zwischen zwei Siegeln
eingrenzen. Was es *nicht* leistet, ist ein Beweis über den Zeitpunkt – dafür
braucht es einen Zeitstempel von dritter Seite nach RFC 3161, und der ist noch
nicht gebaut.
