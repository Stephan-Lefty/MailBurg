"""Welche Grafik zum Erscheinungsbild passt.

Banner und Programmsymbol gibt es in einer hellen und einer dunklen
Fassung. Welche genommen wird, entscheidet nicht eine Einstellung, sondern
das Erscheinungsbild des Systems: Wer sein KDE oder GNOME dunkel gestellt
hat, soll kein weiß leuchtendes Banner vorgesetzt bekommen.

**Wo die Dateien liegen, weiß** :mod:`mailburg.bilder`. Diese Suche
stand bis zum 2026-09-04 hier – bis die Weboberfläche sie ebenfalls
brauchte, und die darf nicht von PySide6 abhängen.
"""

from __future__ import annotations

from pathlib import Path

from mailburg.bilder import finden, orte

#: Nur damit bestehende Aufrufer nicht brechen; neue nehmen
#: ``mailburg.bilder`` unmittelbar.
_orte = orte

__all__ = ["banner", "dunkel", "finden"]


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
