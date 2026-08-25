#!/usr/bin/env python3
"""Erzeugt alle Rasterfassungen aus den SVG-Vorlagen.

Aufruf aus dem Wurzelverzeichnis::

    python3 tools/grafiken_erzeugen.py

Quelle sind ``assets/icon.svg`` und ``assets/banner.svg`` – die Zeichnungen
selbst, nicht die ursprüngliche Pixelgrafik. Daraus entstehen die Größen,
die Betriebssysteme und Paketformate verlangen.

Vorher wurden diese Dateien aus ``Grafik-MailBurg-mit-Icon.png``
freigestellt. Das war Notbehelf und hatte die üblichen Nachteile: Ränder,
die ausfransten, sobald man eine Farbe ändern wollte, und feste Auflösungen.
Die Vorlage bleibt als Ausgangspunkt liegen, gebraucht wird sie nicht mehr.

Braucht ``rsvg-convert`` aus librsvg.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
ASSETS = WURZEL / "assets"

#: 16 bis 48 für Fensterleisten und Startmenüs, 256 bis 1024 für
#: hochauflösende Bildschirme und die Paketformate, 2048 als Vorrat für
#: Druck und alles, was später kommt.
ICON_GROESSEN = (2048, 1024, 512, 256, 128, 64, 48, 32, 16)

#: 800 und 1600 für die Einbindung im README, 2800 als große Fassung.
BANNER_BREITEN = (2800, 1600, 800)


def rendern(quelle: Path, ziel: Path, breite: int, hoehe: int | None = None) -> None:
    befehl = ["rsvg-convert", "-w", str(breite)]
    if hoehe:
        befehl += ["-h", str(hoehe)]
    befehl += [str(quelle), "-o", str(ziel)]
    subprocess.run(befehl, check=True)


def main() -> int:
    if not shutil.which("rsvg-convert"):
        sys.exit("rsvg-convert fehlt. Unter Arch/Manjaro: sudo pacman -S librsvg")

    icon = ASSETS / "icon.svg"
    banner = ASSETS / "banner.svg"
    banner_dunkel = ASSETS / "banner-dark.svg"
    for datei in (icon, banner):
        if not datei.exists():
            sys.exit(f"Fehlt: {datei.relative_to(WURZEL)}")

    for groesse in ICON_GROESSEN:
        # icon.png ohne Zahl im Namen ist die übliche Fassung für den
        # Alltag; die übrigen tragen ihre Kantenlänge im Namen.
        name = "icon.png" if groesse == 1024 else f"icon-{groesse}.png"
        rendern(icon, ASSETS / name, groesse, groesse)

    for quelle, praefix in ((banner, "banner"), (banner_dunkel, "banner-dark")):
        if quelle.exists():
            for breite in BANNER_BREITEN:
                rendern(quelle, ASSETS / f"{praefix}-{breite}.png", breite)

    # Windows erwartet alle Größen in einer einzigen Datei. Dafür braucht es
    # Pillow, rsvg-convert kann kein ICO.
    try:
        from PIL import Image

        gross = Image.open(ASSETS / "icon-256.png")
        gross.save(
            ASSETS / "mailburg.ico",
            sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
        )
    except ImportError:
        print("Pillow fehlt – mailburg.ico wurde nicht erneuert.", file=sys.stderr)

    print(f"{len(ICON_GROESSEN)} Symbolgrößen und die Bannerfassungen erzeugt.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
