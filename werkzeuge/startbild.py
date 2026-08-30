#!/usr/bin/env python3
"""Erzeugt das Startbild für die gepackte Windows-Fassung.

**Warum es das braucht.** Die ``.exe`` ist eine einzige Datei, und
Windows packt sie bei jedem Start vollständig in einen temporären
Ordner aus – 152 MB, jedes Mal. Auf einer schnellen Platte sind das
wenige Sekunden, auf einem älteren Rechner spürbar mehr. In dieser Zeit
tut sich auf dem Bildschirm nichts: kein Fenster, kein Symbol in der
Leiste, nichts. Stephans Satz dazu am 2026-08-30: »Wir müssen dem User
das Gefühl geben, dass sich was tut und ihn nicht verunsichern.«

**Was das Startbild kann und was nicht.** PyInstaller zeigt es, bevor
ausgepackt wird – es ist also nach etwa einer Sekunde da. Möglich sind
ein Bild und *eine* Textzeile. Ein Fortschrittsbalken ist nicht
vorgesehen; die Wunschvorstellung eines sich öffnenden und schließenden
Umschlags erst recht nicht, denn zu diesem Zeitpunkt läuft noch kein
Qt, das etwas zeichnen könnte.

Deshalb steht »MailBurg wird geladen« fest im Bild. Die Zeile darunter
füllt PyInstaller während des Auspackens selbst mit Dateinamen; sobald
Python läuft, übernimmt ``ui.app`` sie mit deutschen Etappen.

Aufruf::

    python werkzeuge/startbild.py

Das Ergebnis landet in ``assets/startbild.png`` und wird von
``werkzeuge/mailburg.spec`` eingebunden.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
BANNER = WURZEL / "assets" / "banner.svg"
ZIEL = WURZEL / "assets" / "startbild.png"

#: Maße des Startbilds. Breit genug für den Schriftzug, hoch genug für
#: die Zeile darunter – und klein genug, dass es auf einem Notebook
#: nicht wie ein Fenster wirkt.
BREITE, HOEHE = 520, 300

#: Wo die Laufzeile steht. Muss zu ``text_pos`` in der .spec passen;
#: ein Test wacht darüber.
TEXTZEILE_Y = 258

HINTERGRUND = "#ffffff"
RAHMEN = "#c8d0da"
SCHRIFT = "#3a4048"
SCHRIFTART = "DejaVu-Sans"


def _werkzeug(name: str) -> bool:
    from shutil import which

    return which(name) is not None


def bauen() -> int:
    if not BANNER.is_file():
        print(f"Fehlt: {BANNER}", file=sys.stderr)
        return 1
    for name in ("rsvg-convert", "magick"):
        if not _werkzeug(name):
            print(f"Nicht gefunden: {name}", file=sys.stderr)
            return 1

    logo = ZIEL.parent / "_logo-fuer-startbild.png"
    # Das Banner freigestellt, auf gut zwei Drittel der Bildbreite.
    subprocess.run(
        ["rsvg-convert", "-w", "400", str(BANNER), "-o", str(logo)],
        check=True,
    )

    subprocess.run(
        [
            "magick",
            "-size", f"{BREITE}x{HOEHE}", f"xc:{HINTERGRUND}",
            # Ein dünner Rahmen: Ohne ihn verschwimmt das Bild auf einem
            # hellen Schreibtisch mit dem Hintergrund.
            "-stroke", RAHMEN, "-strokewidth", "1", "-fill", "none",
            "-draw", f"rectangle 0,0 {BREITE - 1},{HOEHE - 1}",
            str(logo), "-gravity", "north", "-geometry", "+0+40",
            "-composite",
            # »MailBurg wird geladen« gehört ins Bild, nicht in die
            # Laufzeile: Die überschreibt PyInstaller beim Auspacken.
            # »-annotate«, nicht »-annotation« – letzteres bricht mit
            # einem nackten Rückgabewert 11 ab, ohne zu sagen, warum.
            # Und eine gerade Schrift: ImageMagick nimmt sonst eine
            # kursive, die neben dem Schriftzug fehl am Platz wirkt.
            "-stroke", "none", "-fill", SCHRIFT,
            "-font", SCHRIFTART, "-pointsize", "18", "-gravity", "north",
            "-annotate", "+0+208", "MailBurg wird geladen",
            str(ZIEL),
        ],
        check=True,
    )
    logo.unlink(missing_ok=True)

    print(f"  {ZIEL.relative_to(WURZEL)}  ({ZIEL.stat().st_size / 1024:.0f} kB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(bauen())
