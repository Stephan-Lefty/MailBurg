# -*- mode: python ; coding: utf-8 -*-
"""Bauplan für ``MailBurg-Server-Einrichten.exe``.

Daraus entsteht das Einrichtungsfenster für den Serverdienst als eine
Datei, die man auf einen frischen Windows Server legen und doppelklicken
kann.

**Warum es das gibt.** Am 2026-10-02 wurde der Dienst zum ersten Mal
aufgesetzt. Von zehn Schritten verlangten acht einen PowerShell-Befehl
aus einer PDF; als der Dienst nicht startete, stand der Grund in einem
Ereignisprotokoll, das man mit einem weiteren Befehl durchsucht.
Stephans Urteil: Das muss in ein Fenster.

**Eigene Datei neben ``mailburg.spec``, nicht ein zweites Ziel darin.**
Der Inhalt ist ein anderer: hier pywin32, starlette und uvicorn, dort
poppler und tesseract. Zusammengelegt trüge jede Fassung den Ballast der
anderen – die Server-Datei 150 MB Texterkennung, die ein
Einrichtungsprogramm nie anfasst.

Gebaut wird mit::

    pyinstaller werkzeuge/server_einrichten.spec

**PyInstaller packt immer für das System, auf dem es läuft.** Diese
Fassung entsteht nur unter Windows; unter Linux startet man dasselbe
Fenster mit ``mailburg-server-einrichten``.
"""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

WURZEL = Path(SPECPATH).parent

EINSTIEG = str(WURZEL / "werkzeuge" / "start_server_einrichten.py")

WINDOWS = sys.platform == "win32"

#: Was mitmuss, obwohl es niemand ausdrücklich importiert.
VERSTECKT = [
    # Qt zeichnet das Wappen aus einer SVG; QPixmap lädt das Modul erst
    # zur Laufzeit nach, PyInstaller sieht den Bedarf nicht.
    "PySide6.QtSvg",
    # uvicorn sucht seine Umsetzungen über Namen, nicht über Importe.
    # Ohne sie startet der Dienst mit »unknown loop« oder gar nicht.
    *collect_submodules("uvicorn"),
]

if WINDOWS:
    VERSTECKT += [
        "keyring.backends.Windows",
        "win32ctypes.core",
        *collect_submodules("win32ctypes"),
        # **Der Kern dieser Fassung.** Ohne pywin32 kann das Fenster den
        # Dienst nicht anlegen - und genau dafür ist es da.
        "win32serviceutil",
        "win32service",
        "win32event",
        "servicemanager",
    ]
else:
    VERSTECKT += [
        "keyring.backends.SecretService",
        "keyring.backends.chainer",
        "secretstorage",
    ]

#: Was Platz kostet und niemand braucht.
#:
#: **Ohne Texterkennung.** poppler und tesseract wären 150 MB für etwas,
#: das ein Einrichtungsprogramm nie aufruft. Wer Scans durchsuchen will,
#: tut das im Archivfenster oder auf der Kommandozeile.
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

analyse = Analysis(
    [EINSTIEG],
    pathex=[str(WURZEL)],
    binaries=[],
    datas=[
        # Das rote Wappen der Weboberfläche und das Programmsymbol.
        (str(WURZEL / "assets" / "icon.svg"), "assets"),
        (str(WURZEL / "assets" / "mailburg.ico"), "assets"),
        # Die Anleitung kommt mit: Wer eine einzelne Datei auf einen
        # Server legt, hat sonst keine Dokumentation daneben.
        (str(WURZEL / "docs" / "server-einrichten.md"), "docs"),
        (str(WURZEL / "docs" / "server.md"), "docs"),
    ],
    hiddenimports=VERSTECKT,
    hookspath=[],
    runtime_hooks=[],
    excludes=DRAUSSEN,
    noarchive=False,
)

pyz = PYZ(analyse.pure)

exe = EXE(
    pyz,
    analyse.scripts,
    analyse.binaries,
    analyse.datas,
    [],
    name="MailBurg-Server-Einrichten",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # **Kein Konsolenfenster.** Wer doppelklickt, will das Fenster und
    # kein schwarzes Rechteck daneben. Damit hat der Prozess aber keine
    # Standardausgabe – deshalb hängt sich ``--pruefen`` über
    # ``AttachConsole`` an die PowerShell, aus der es gerufen wurde
    # (siehe ``start_server_einrichten._konsole_anhaengen``).
    console=False,
    disable_windowed_traceback=False,
    icon=str(WURZEL / "assets" / "mailburg.ico") if WINDOWS else None,
)
