[Übersicht](../README.md) | [Anleitungen](README.md) | [Postfächer](postfaecher-einrichten.md) | [Windows](windows.md)

# Regelmäßig abrufen

Ein Archiv, das man von Hand füttern muss, wird irgendwann nicht mehr gefüttert.
Der Abruf ist deshalb darauf ausgelegt, in einer Zeitsteuerung zu laufen: Er
holt nur, was neu ist, und braucht keine Eingabe.

```bash
mailburg abrufen ~/Archiv
```

## Der eine Haken: der Schlüsselbund

Die Passwörter liegen im Schlüsselbund des Betriebssystems, und der ist an die
angemeldete Sitzung gebunden. **Läuft der Abruf, während niemand angemeldet ist,
kommt er nicht an die Passwörter.**

Daraus folgt: Der nächtliche Abruf funktioniert auf einem Rechner, der
durchläuft und an dem der Benutzer angemeldet bleibt. Er funktioniert nicht auf
einem Server, an dem sich niemand anmeldet.

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
./install.sh --zeitsteuerung ~/Archiv
```

Das legt einen Benutzer-Timer an, der täglich um drei Uhr läuft, mit
`Persistent=true` – war der Rechner um drei aus, wird der Abruf beim nächsten
Start nachgeholt. Ohne das fiele er an jedem Wochenende aus.

Nachsehen:

```bash
systemctl --user list-timers mailburg-abruf.timer
journalctl --user -u mailburg-abruf.service
systemctl --user start mailburg-abruf.service   # gleich einmal laufen lassen
```

Die Uhrzeit steht in `~/.config/systemd/user/mailburg-abruf.timer` unter
`OnCalendar`. Nach einer Änderung:

```bash
systemctl --user daemon-reload
systemctl --user restart mailburg-abruf.timer
```

### Ohne systemd: cron

```cron
0 3 * * * /home/IHRNAME/.local/bin/mailburg abrufen /home/IHRNAME/Archiv >> /home/IHRNAME/.mailburg-abruf.log 2>&1
```

Der volle Pfad ist nötig: cron kennt den Suchpfad der Anmeldesitzung nicht.

## Windows: Aufgabenplanung

```powershell
.\install.ps1 -Zeitsteuerung C:\Archiv
```

Das legt die Aufgabe „MailBurg Abruf" an, täglich um drei Uhr, mit
„Aufgabe so schnell wie möglich nachholen" – dieselbe Überlegung wie oben.

Nachsehen in der Aufgabenplanung (`taskschd.msc`) unter diesem Namen. Von Hand
anstoßen:

```powershell
Start-ScheduledTask -TaskName "MailBurg Abruf"
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
        <string>/Users/IHRNAME/Archiv</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key><integer>3</integer>
        <key>Minute</key><integer>0</integer>
    </dict>
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

In einem Geschäftsarchiv gehört nach jedem Abruf ein Siegel über den Stand:

```bash
mailburg abrufen ~/Archiv && mailburg siegel ~/Archiv
```

Das Siegel hält fest, wie weit die Hash-Kette zu diesem Zeitpunkt reichte. Ein
späterer Eingriff lässt sich damit auf den Abschnitt zwischen zwei Siegeln
eingrenzen. Was es *nicht* leistet, ist ein Beweis über den Zeitpunkt – dafür
braucht es einen Zeitstempel von dritter Seite nach RFC 3161, und der ist noch
nicht gebaut.
