<#
.SYNOPSIS
    MailBurg unter Windows einrichten.

.DESCRIPTION
    Legt eine eigene Python-Umgebung unter %LOCALAPPDATA%\MailBurg an,
    richtet den Befehl "mailburg" ein und auf Wunsch einen nächtlichen
    Abruf über die Aufgabenplanung.

    Das Archiv selbst rührt dieses Skript nie an. Auch -Entfernen nimmt nur
    das Programm weg; die Mails bleiben, wo sie sind.

.PARAMETER OhneKuer
    Nur den Kern einrichten, ohne IMAP-Schlüsselbund, Anhangstext und
    Zstandard.

.PARAMETER Zeitsteuerung
    Pfad zu einem Archiv. Richtet den laufenden Abruf dafür ein.

.PARAMETER Alle
    Abstand zwischen zwei Abrufen in Minuten: 10, 30, 60 oder 90.
    Vorgabe ist 30.

.PARAMETER Entfernen
    Baut das Programm wieder ab.

.EXAMPLE
    .\install.ps1
    .\install.ps1 -Zeitsteuerung C:\Archiv
    .\install.ps1 -Zeitsteuerung C:\Archiv -Alle 10
    .\install.ps1 -Entfernen

.NOTES
    Ohne Administratorrechte. Lässt Windows das Skript nicht zu, hilft:
        Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#>

[CmdletBinding()]
param(
    [switch]$OhneKuer,
    [string]$Zeitsteuerung = "",
    # Dreißig Minuten sind der Kompromiss: kurz genug, dass eine
    # Aufräumregel im Mailclient nichts wegräumt, was noch nicht archiviert
    # ist, und lang genug, dass kein Anbieter die häufigen Anmeldungen für
    # einen Angriff hält.
    [ValidateSet(10, 30, 60, 90)]
    [int]$Alle = 30,
    [switch]$Entfernen
)

$ErrorActionPreference = "Stop"

$Quelle   = Split-Path -Parent $MyInvocation.MyCommand.Path
$Ziel     = Join-Path $env:LOCALAPPDATA "MailBurg"
$Venv     = Join-Path $Ziel "venv"
$Bin      = Join-Path $Ziel "bin"
$Aufgabe  = "MailBurg Abruf"

function Melde($text)   { Write-Host "`n$text" -ForegroundColor White }
function Hinweis($text) { Write-Host "  $text" }
function Fehler($text)  { Write-Host "Fehler: $text" -ForegroundColor Red; exit 1 }

# ------------------------------------------------------------------ Abbauen

if ($Entfernen) {
    Melde "MailBurg abbauen"

    if (Get-ScheduledTask -TaskName $Aufgabe -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $Aufgabe -Confirm:$false
        Hinweis "Nächtlicher Abruf abgestellt."
    }
    if (Test-Path $Venv) { Remove-Item -Recurse -Force $Venv }
    if (Test-Path $Bin)  { Remove-Item -Recurse -Force $Bin }

    Hinweis "Programm entfernt."
    Hinweis "Geblieben sind: Ihr Archiv, die Kontenliste und der Suchindex."
    Hinweis "  Kontenliste: $env:APPDATA\MailBurg\konten.json"
    Hinweis "  Suchindex:   $env:LOCALAPPDATA\MailBurg\index\"
    Hinweis "Die Passwoerter in der Anmeldeinformationsverwaltung bleiben stehen."
    exit 0
}

# ------------------------------------------------------------------- Python

Melde "MailBurg einrichten"

$PythonExe = $null
$PythonArgs = @()

foreach ($kandidat in @("py", "python", "python3")) {
    if (-not (Get-Command $kandidat -ErrorAction SilentlyContinue)) { continue }

    # "py -3" wählt die neueste Fassung, wenn mehrere installiert sind.
    # Die Zusatzargumente werden per Splatting übergeben; ein Zugriff wie
    # $a[1..($a.Length-1)] kehrt bei einelementigen Feldern die Reihenfolge
    # um, weil 1..0 in PowerShell rückwärts zählt.
    $zusatz = if ($kandidat -eq "py") { @("-3") } else { @() }
    $fassung = & $kandidat @zusatz -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
    if (-not $fassung) { continue }

    $teile = $fassung.Trim().Split(".")
    if ([int]$teile[0] -ge 3 -and [int]$teile[1] -ge 11) {
        $PythonExe = $kandidat
        $PythonArgs = $zusatz
        Hinweis "Python $($fassung.Trim()) gefunden."
        break
    }
}

if (-not $PythonExe) {
    Fehler @"
MailBurg braucht Python 3.11 oder neuer.

Zu holen ueber den Microsoft Store, ueber winget:
    winget install Python.Python.3.13
oder von https://www.python.org/downloads/

Beim Installieren von python.org bitte "Add python.exe to PATH" ankreuzen.
"@
}

# ----------------------------------------------------------------- Programm

# Eine eigene Umgebung statt einer Installation ins System: So bleibt die
# Python-Installation unberuehrt, und zum Abbauen genuegt es, einen Ordner
# zu loeschen.
New-Item -ItemType Directory -Force -Path $Ziel | Out-Null
& $PythonExe @PythonArgs -m venv --upgrade-deps $Venv | Out-Null
Hinweis "Eigene Python-Umgebung unter $Venv"

$pip = Join-Path $Venv "Scripts\pip.exe"
$paket = if ($OhneKuer) { $Quelle } else { "$Quelle[alles]" }
& $pip install -q $paket
if ($LASTEXITCODE -ne 0) { Fehler "Die Installation ist gescheitert." }

if ($OhneKuer) {
    Hinweis "MailBurg im Kern eingerichtet."
} else {
    Hinweis "MailBurg mit allem eingerichtet: IMAP, Anhaenge im Volltext, Zstandard."
}

# Ein Startskript statt einer Verknuepfung: So laesst sich "mailburg" in
# jeder Eingabeaufforderung und in der Aufgabenplanung gleich aufrufen.
New-Item -ItemType Directory -Force -Path $Bin | Out-Null
$starter = Join-Path $Bin "mailburg.cmd"
"@echo off`r`n`"$Venv\Scripts\mailburg.exe`" %*" |
    Set-Content -Path $starter -Encoding ASCII
Hinweis "Befehl 'mailburg' liegt in $Bin"

$pfad = [Environment]::GetEnvironmentVariable("Path", "User")
if ($pfad -notlike "*$Bin*") {
    [Environment]::SetEnvironmentVariable("Path", "$pfad;$Bin", "User")
    Hinweis "In den Suchpfad aufgenommen – wirksam in neuen Fenstern."
}

Hinweis ""
Hinweis "Hinweis zu PDF-Anhaengen: Unter Windows fehlt meist pdftotext aus"
Hinweis "poppler. MailBurg weicht dann auf pypdf aus – dasselbe Ergebnis,"
Hinweis "nur langsamer. Eingescannte PDF bleiben so oder so unauffindbar,"
Hinweis "dafuer braucht es Texterkennung."

# ------------------------------------------------------------ Zeitsteuerung

if ($Zeitsteuerung) {
    Melde "Laufender Abruf"

    $archiv = (Resolve-Path $Zeitsteuerung -ErrorAction SilentlyContinue)
    if (-not $archiv) { Fehler "Das Verzeichnis $Zeitsteuerung gibt es nicht." }
    if (-not (Test-Path (Join-Path $archiv "archive.json"))) {
        Fehler "In $archiv liegt kein Archiv. Erst anlegen: mailburg anlegen `"$archiv`""
    }

    $aktion = New-ScheduledTaskAction -Execute $starter `
        -Argument "abrufen --leise `"$archiv`""

    # Bei der Anmeldung anlaufen und sich dann in kurzem Takt wiederholen.
    # An die Anmeldung gebunden, weil die Anmeldeinformationsverwaltung an
    # der Sitzung haengt - ohne angemeldeten Benutzer kaeme der Abruf gar
    # nicht erst an die Passwoerter.
    $ausloeser = New-ScheduledTaskTrigger -AtLogOn
    $ausloeser.Delay = "PT5M"
    $ausloeser.Repetition = (New-ScheduledTaskTrigger -Once -At (Get-Date) `
        -RepetitionInterval (New-TimeSpan -Minutes $Alle) `
        -RepetitionDuration ([System.TimeSpan]::MaxValue)).Repetition

    $regeln = New-ScheduledTaskSettingsSet `
        -StartWhenAvailable `
        -DontStopIfGoingOnBatteries `
        -AllowStartIfOnBatteries `
        -RunOnlyIfNetworkAvailable `
        -MultipleInstances IgnoreNew `
        -ExecutionTimeLimit (New-TimeSpan -Hours 2)

    Register-ScheduledTask -TaskName $Aufgabe -Action $aktion `
        -Trigger $ausloeser -Settings $regeln -Force | Out-Null

    Hinweis "Eingerichtet fuer $archiv, alle $Alle Minuten."
    Hinweis "Nachsehen in der Aufgabenplanung (taskschd.msc) unter '$Aufgabe'."
    Hinweis "Jetzt gleich: Start-ScheduledTask -TaskName '$Aufgabe'"
    Hinweis ""
    Hinweis "Der Abruf laeuft ab der Anmeldung und dann im gewaehlten Takt."
    Hinweis "Ohne angemeldeten Benutzer kommt er nicht an die Passwoerter -"
    Hinweis "die Anmeldeinformationsverwaltung haengt an Ihrer Sitzung."
}

# ------------------------------------------------------------------- Fertig

Melde "Fertig"
Hinweis "Erste Schritte in einem neuen Fenster:"
Hinweis "    mailburg anlegen %USERPROFILE%\Archiv --modus privat"
Hinweis "    mailburg konten hinzufuegen Firma --server imap.example.org --benutzer post@example.org"
Hinweis "    mailburg abrufen %USERPROFILE%\Archiv"
Hinweis ""
Hinweis "Anleitungen liegen in docs\, die Suchsprache erklaert 'mailburg suchhilfe'."
