"""Wo die Grafiken liegen – für alle Teile des Programms.

Gesucht wird an mehreren Orten, weil MailBurg auf verschiedene Weisen
installiert sein kann: aus dem Quellordner heraus, als Paket, als
AppImage, als gepackte Windows-Fassung. Findet sich nichts, bleibt die
Stelle eben leer – ein fehlendes Bild ist kein Grund, das Programm nicht
zu starten.

**Warum das hier steht und nicht in ``ui/``.** Bis zum 2026-09-04
gehörte diese Suche der Oberfläche allein. Dann brauchte sie auch die
Weboberfläche für ihr Wappen – und die darf nicht von PySide6 abhängen,
das im Server gar nicht installiert ist. Was zwei Teile brauchen, gehört
keinem von beiden.
"""

from __future__ import annotations

import sys
from pathlib import Path


def orte() -> tuple[Path, ...]:
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
    gefunden = []
    gepackt = getattr(sys, "_MEIPASS", None)
    if gepackt:
        gefunden.append(Path(gepackt) / "assets")
    gefunden.extend([
        # Aus dem Quellordner heraus – so läuft es während der Entwicklung.
        Path(__file__).resolve().parent.parent / "assets",
        # Neben dem Paket, falls die Grafiken einmal mitgeliefert werden.
        Path(__file__).resolve().parent / "assets",
        # Systemweit installiert.
        Path("/usr/share/mailburg/assets"),
        Path("/usr/share/pixmaps"),
    ])
    return tuple(gefunden)


def finden(name: str) -> Path | None:
    """Sucht eine Bilddatei an den bekannten Orten.

    ``name`` darf einen Unterordner enthalten (``server/icon-64.png``),
    aber **nichts, was aus einer Anfrage stammt**: Ein Name mit ``..``
    darin führte sonst aus dem Bilderverzeichnis hinaus. Aufrufer, die
    von außen kommen – die Weboberfläche –, wählen deshalb aus einer
    festen Tabelle, statt einen Namen durchzureichen.
    """
    for ort in orte():
        kandidat = ort / name
        if kandidat.exists():
            return kandidat
    return None
