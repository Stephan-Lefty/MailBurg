"""Wo die Grafiken liegen – und welche gerade passt.

Banner und Programmsymbol gibt es in einer hellen und einer dunklen
Fassung. Welche genommen wird, entscheidet nicht eine Einstellung, sondern
das Erscheinungsbild des Systems: Wer sein KDE oder GNOME dunkel gestellt
hat, soll kein weiß leuchtendes Banner vorgesetzt bekommen.

Gesucht wird an mehreren Orten, weil MailBurg auf verschiedene Weisen
installiert sein kann – aus dem Quellordner heraus, als Paket, als
AppImage. Findet sich nichts, bleibt die Stelle eben leer; ein fehlendes
Bild ist kein Grund, das Programm nicht zu starten.
"""

from __future__ import annotations

import sys
from pathlib import Path

def _orte() -> tuple[Path, ...]:
    """Wo Grafiken liegen können, in der Reihenfolge der Suche.

    Eine Funktion und keine Konstante, weil der erste Ort erst zur
    Laufzeit feststeht: In einer gepackten Windows-Fassung entpackt sich
    PyInstaller in ein Verzeichnis, das beim Start entsteht, und
    hinterlegt dessen Pfad in ``sys._MEIPASS``.

    Ohne diesen Fall blieb der Willkommensbildschirm ohne Logo – die
    Burg mit dem Schriftzug, also das Erste, was ein neuer Anwender
    sieht. Am 2026-08-28 in der ersten ausgelieferten Fassung
    aufgefallen.
    """
    orte = []
    gepackt = getattr(sys, "_MEIPASS", None)
    if gepackt:
        orte.append(Path(gepackt) / "assets")
    orte.extend([
        # Aus dem Quellordner heraus – so läuft es während der Entwicklung.
        Path(__file__).resolve().parent.parent.parent / "assets",
        # Neben dem Paket, falls die Grafiken einmal mitgeliefert werden.
        Path(__file__).resolve().parent / "assets",
    # Systemweit installiert.
        Path("/usr/share/mailburg/assets"),
        Path("/usr/share/pixmaps"),
    ])
    return tuple(orte)


def dunkel() -> bool:
    """Ob das System auf ein dunkles Erscheinungsbild eingestellt ist."""
    from PySide6.QtGui import QPalette
    from PySide6.QtWidgets import QApplication

    anwendung = QApplication.instance()
    if anwendung is None:
        return False
    farbe = anwendung.palette().color(QPalette.Window)
    # Nicht die Helligkeit einzelner Kanäle, sondern der wahrgenommene
    # Grauwert: Ein sattes Dunkelblau ist dunkel, auch wenn der Blaukanal
    # hoch steht.
    return (farbe.red() * 299 + farbe.green() * 587 + farbe.blue() * 114) / 1000 < 128


def finden(name: str) -> Path | None:
    """Sucht eine Bilddatei an den bekannten Orten."""
    for ort in _orte():
        kandidat = ort / name
        if kandidat.exists():
            return kandidat
    return None


def banner(breite: int = 560):
    """Das Banner, passend zum Erscheinungsbild und auf Breite gebracht."""
    from PySide6.QtGui import QPixmap

    for name in (("banner-dark.svg", "banner.svg") if dunkel()
                 else ("banner.svg", "banner-dark.svg")):
        pfad = finden(name)
        if pfad is None:
            continue
        bild = QPixmap(str(pfad))
        if bild.isNull():
            continue
        from PySide6.QtCore import Qt

        return bild.scaledToWidth(breite, Qt.SmoothTransformation)
    return None
