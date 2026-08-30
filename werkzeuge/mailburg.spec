# -*- mode: python ; coding: utf-8 -*-
"""Bauplan für die Windows-Fassung von MailBurg.

**Warum es das gibt.** Am 2026-08-27 wurde MailBurg zum ersten Mal auf
einem frischen Windows eingerichtet. Das dauerte zwei Stunden: Python
über winget nachinstallieren, PowerShell als Administrator öffnen, Pfade
abtippen, Zusätze in eckigen Klammern kennen (``[oberflaeche,imap]``).
Unter Linux genügt ein Befehl.

Stephans Urteil danach: »Der Windows-User braucht eine fertige
Exe-Datei, und dann läuft alles automatisch.« Er hat recht – wer ein
Archivprogramm sucht, will kein Python einrichten.

**Was hier hineingepackt wird:** Python, PySide6, keyring und MailBurg
selbst. Nicht enthalten sind poppler und tesseract für die
Texterkennung; das wären noch einmal 150 MB für etwas, das die Ausnahme
ist – in Stephans Privatarchiv 323 eingescannte PDF bei 16.360 Mails.
Fehlen sie, sagt MailBurg das und arbeitet ohne sie weiter.

Gebaut wird mit::

    pyinstaller werkzeuge/mailburg.spec

Das läuft nur unter Windows sinnvoll: PyInstaller packt immer für das
System, auf dem es läuft.
"""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

WURZEL = Path(SPECPATH).parent

#: Der Einstieg. Nicht ``mailburg/__main__.py``: Das ist die
#: Kommandozeile. Wer doppelklickt, will das Fenster.
EINSTIEG = str(WURZEL / "werkzeuge" / "start_gui.py")

#: Was mitmuss, obwohl es niemand ausdrücklich importiert.
#:
#: ``keyring`` sucht seinen Speicher zur Laufzeit über Einstiegspunkte –
#: PyInstaller sieht davon nichts und ließe die Windows-Anbindung weg.
#: Genau die braucht MailBurg aber: Ohne sie würde bei jedem Abruf nach
#: dem Passwort gefragt, und der Hintergrundabruf wäre unmöglich.
VERSTECKT = [
    "keyring.backends.Windows",
    # Ohne QtSvg kann Qt die Banner nicht zeichnen: Sie liegen als SVG
    # vor, damit sie auf jedem Bildschirm scharf bleiben. PyInstaller
    # sieht den Bedarf nicht, weil MailBurg das Modul nirgends
    # ausdrücklich importiert - QPixmap lädt es zur Laufzeit nach.
    "PySide6.QtSvg",
    "win32ctypes.core",
    *collect_submodules("win32ctypes"),
]

#: Was Platz kostet und niemand braucht. PySide6-Essentials bringt
#: einiges mit, das ein Archivprogramm nie anfasst.
DRAUSSEN = [
    "PySide6.Qt3DAnimation", "PySide6.Qt3DCore", "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput", "PySide6.Qt3DLogic", "PySide6.Qt3DRender",
    "PySide6.QtBluetooth", "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
    "PySide6.QtNfc", "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets",
    "PySide6.QtPositioning", "PySide6.QtQuick", "PySide6.QtQuick3D",
    "PySide6.QtQuickWidgets", "PySide6.QtQml", "PySide6.QtSensors",
    "PySide6.QtSerialPort", "PySide6.QtSpatialAudio", "PySide6.QtWebChannel",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets", "tkinter", "unittest", "pydoc_data",
]

#: poppler und tesseract, sofern der Workflow sie hergelegt hat.
#:
#: **Warum sie mit hinein müssen.** Ohne sie findet MailBurg unter
#: Windows keine eingescannte Rechnung – und mehr als die Hälfte der PDF
#: in einem gewachsenen Postfach sind Scans. Der Weg dorthin wäre sonst:
#: poppler von einer GitHub-Release-Seite laden, ZIP entpacken, PATH
#: eintragen, dasselbe für tesseract, Sprachdaten für Deutsch nicht
#: vergessen. Das erledigt niemand nebenbei. Stephans Urteil am
#: 2026-08-28: »Ohne das ist es doch nicht dieselbe Lösung wie unter
#: Linux.«
#:
#: Sie liegen als ``datas``, nicht als ``binaries``: PyInstaller soll sie
#: nicht auf Abhängigkeiten durchsuchen und ihre DLLs umsortieren. Sie
#: werden als eigenständige Programme aufgerufen und müssen beisammen
#: bleiben.
MITGEBRACHT = WURZEL / "werkzeuge" / "windows"
BEIGABEN = (
    [(str(MITGEBRACHT), "werkzeuge")] if MITGEBRACHT.is_dir() else []
)

analyse = Analysis(
    [EINSTIEG],
    pathex=[str(WURZEL)],
    binaries=[],
    # Das Handbuch steckt im Programm, die Anleitungen kommen mit: Wer
    # eine einzelne Datei herunterlädt, hat sonst keine Dokumentation.
    datas=[
        # **Das ganze Bilderverzeichnis, nicht nur das Symbol.** Beim
        # ersten Wurf lag hier allein die .ico – und der
        # Willkommensbildschirm zeigte kein Logo mehr, weil die Burg mit
        # dem Schriftzug aus einer SVG kommt. Das Erste, was ein neuer
        # Anwender sieht, war damit kahl (2026-08-28).
        (str(WURZEL / "assets" / "banner.svg"), "assets"),
        (str(WURZEL / "assets" / "banner-dark.svg"), "assets"),
        (str(WURZEL / "assets" / "icon.svg"), "assets"),
        (str(WURZEL / "assets" / "mailburg.ico"), "assets"),
        (str(WURZEL / "docs"), "docs"),
        (str(WURZEL / "LICENSE"), "."),
        (str(WURZEL / "RECHTLICHES.md"), "."),
        *BEIGABEN,
    ],
    hiddenimports=VERSTECKT,
    hookspath=[],
    runtime_hooks=[],
    excludes=DRAUSSEN,
    noarchive=False,
)

pyz = PYZ(analyse.pure)

#: **Hier stand ein Startbild – bewusst nicht mehr.** Gedacht war es
#: gegen die Stille beim Start: Die .exe ist eine einzige Datei, Windows
#: packt sie bei jedem Start aus, und in einer VM dauerte das 20–25
#: Sekunden ohne jedes Lebenszeichen.
#:
#: Drei Anläufe. Zwei echte Fehler dabei behoben (ein PNG mit 16 Bit
#: Farbtiefe – Tk kann nur 8 und meldet es nicht –, und
#: ``always_on_top=False``, wodurch das randlose Fenster hinter den
#: Desktop rutschte). Danach war das Bild einwandfrei: 520×300, 8 Bit,
#: TrueColor, nicht verschränkt, kein Alphakanal. Der Bau meldete
#: »Building Splash«. Auf einem richtigen Windows-11-Laptop kam am
#: 2026-08-30 trotzdem nur ein leeres Fenster.
#:
#: **Ausgebaut aus einem anderen Grund als dem Fehler.** Auf echter
#: Hardware startet MailBurg in wenigen Sekunden – der Anlass ist damit
#: weg. Ein Bild, das aufblitzt und wieder verschwindet, verunsichert
#: mehr als die Wartezeit, gegen die es antreten sollte. Und ein leeres
#: erst recht.
#:
#: Wer es wieder aufgreift, sucht zuerst die Antwort darauf, warum die
#: Ressource nicht ankommt – nicht am Bild, das war in Ordnung.

exe = EXE(
    pyz,
    analyse.scripts,
    analyse.binaries,
    analyse.datas,
    [],
    name="MailBurg",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX presst die Datei kleiner, bringt MailBurg aber regelmäßig in
    # Verdacht: Virenscanner schlagen bei gepackten Programmen häufiger
    # an, und eine unsignierte Datei hat es ohnehin schwer genug.
    upx=False,
    # Kein Konsolenfenster: Wer doppelklickt, will das Programm sehen
    # und nicht ein schwarzes Fenster daneben.
    console=False,
    disable_windowed_traceback=False,
    icon=str(WURZEL / "assets" / "mailburg.ico"),
    version=str(WURZEL / "werkzeuge" / "fassung.txt"),
)
