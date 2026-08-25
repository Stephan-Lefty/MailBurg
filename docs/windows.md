[Übersicht](../README.md) | [Anleitungen](README.md) | [Postfächer](postfaecher-einrichten.md) | [Zeitsteuerung](zeitsteuerung.md)

# MailBurg unter Windows

MailBurg läuft unter Windows genauso wie unter Linux – dieselbe Kommandozeile,
dasselbe Archivformat. Ein Archiv, das auf dem Windows-Rechner entstanden ist,
lässt sich auf einem Linux-Rechner öffnen und umgekehrt.

## Einrichten

Voraussetzung ist Python 3.11 oder neuer:

```powershell
winget install Python.Python.3.13
```

Wer von [python.org](https://www.python.org/downloads/) installiert, muss beim
Setup **„Add python.exe to PATH"** ankreuzen – ohne das findet die
Eingabeaufforderung Python später nicht.

Dann in PowerShell, im MailBurg-Ordner:

```powershell
.\install.ps1
```

Lässt Windows das Skript nicht zu, hilft für dieses eine Fenster:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Administratorrechte braucht es nicht. MailBurg landet unter
`%LOCALAPPDATA%\MailBurg`, der Befehl `mailburg` wird in den Suchpfad
aufgenommen – wirksam in **neu geöffneten** Fenstern.

## Loslegen

```powershell
mailburg anlegen $env:USERPROFILE\Archiv --modus privat
mailburg konten hinzufuegen Firma --server imap.example.org --benutzer post@example.org
mailburg abrufen $env:USERPROFILE\Archiv
mailburg suchen $env:USERPROFILE\Archiv betreff:rechnung
```

## Wo was liegt

| Was | Wo |
|-----|-----|
| Programm | `%LOCALAPPDATA%\MailBurg\venv` |
| Befehl | `%LOCALAPPDATA%\MailBurg\bin\mailburg.cmd` |
| Kontenliste | `%APPDATA%\MailBurg\konten.json` |
| Suchindex | `%LOCALAPPDATA%\MailBurg\index\` |
| Passwörter | Anmeldeinformationsverwaltung |
| Archiv | wo Sie es angelegt haben |

Die Trennung ist Absicht: Einstellungen liegen im wandernden Profil
(`APPDATA`) und wandern in einer Domäne mit, der Suchindex liegt lokal
(`LOCALAPPDATA`). Der kann zweistellige Gigabyte erreichen – den über das
Netz zu synchronisieren, wäre eine Zumutung.

## Passwörter

Die Anmeldeinformationsverwaltung von Windows wird ohne Zusatzpaket benutzt.
Nachsehen lässt sich das unter *Systemsteuerung → Anmeldeinformationsverwaltung
→ Windows-Anmeldeinformationen*, Einträge beginnen mit `de.stephanlefty.MailBurg`.

## Anhänge im Volltext

PDF-Anhänge werden durchsuchbar gemacht, aber unter Windows auf dem langsameren
Weg: `pdftotext` aus poppler ist dort selten installiert, MailBurg weicht
deshalb auf `pypdf` aus. Das Ergebnis ist dasselbe, der Import dauert länger.

Wer poppler haben will:

```powershell
winget install oschwartz10612.Poppler
```

Danach muss der `bin`-Ordner von poppler im Suchpfad stehen.

Eingescannte PDF ohne Textebene bleiben in beiden Fällen unauffindbar – dafür
bräuchte es Texterkennung, die noch nicht gebaut ist. Wie viele davon im
Bestand liegen, meldet der Import am Ende.

## Regelmäßig abrufen

```powershell
.\install.ps1 -Zeitsteuerung C:\Archiv
```

Einzelheiten und der Haken mit dem Schlüsselbund stehen in
[zeitsteuerung.md](zeitsteuerung.md).

## Thunderbird und Outlook

Ein vorhandenes **Thunderbird**-Profil wird gefunden und mitsamt aller Konten
und Ordner eingelesen:

```powershell
mailburg importieren $env:USERPROFILE\Archiv `
    "$env:APPDATA\Thunderbird\Profiles\xxxxxxxx.default" --konto alt
```

**Outlook**-Archive (`.pst`, `.ost`) kann MailBurg noch nicht lesen. Der Weg
dahin führt über `libpff` und steht auf der Liste. Bis dahin hilft der Umweg:
In Outlook den Ordner als `.eml` exportieren oder das Konto zusätzlich in
Thunderbird einrichten – oder gleich per IMAP abrufen, das geht bei Outlook.com
und Exchange ohnehin.

## Abbauen

```powershell
.\install.ps1 -Entfernen
```

Nimmt das Programm weg. Archiv, Kontenliste, Suchindex und die Passwörter
bleiben stehen – die müssen Sie bewusst selbst entfernen.
