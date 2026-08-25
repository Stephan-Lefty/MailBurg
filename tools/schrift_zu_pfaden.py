#!/usr/bin/env python3
"""Wandelt einen Schriftzug in SVG-Pfade um.

Aufruf::

    python3 tools/schrift_zu_pfaden.py "MailBurg" --schrift "URW Gothic:style=Demi" --groesse 100

Warum Pfade und nicht ``<text>``: Ein Logo muss überall gleich aussehen. Ein
``<text>``-Element greift auf die Schriften des Betrachters zu – fehlt die
richtige, setzt der Browser irgendetwas anderes ein und das Logo ist ein
anderes. Als Pfad ist der Schriftzug eine Zeichnung und von keiner
installierten Schrift mehr abhängig.

Die Schrift wird also einmal beim Erzeugen gebraucht, danach nie wieder.
"""

from __future__ import annotations

import argparse
import subprocess
import sys


def schriftdatei(muster: str) -> str:
    """Findet die Datei zu einer Schriftbeschreibung über fontconfig."""
    ergebnis = subprocess.run(
        ["fc-match", muster, "-f", "%{file}"], capture_output=True, text=True
    )
    pfad = ergebnis.stdout.strip()
    if not pfad:
        sys.exit(f"Keine Schrift gefunden für: {muster}")
    return pfad


def zu_pfaden(
    text: str, datei: str, groesse: float, sperrung: float = 0.0
) -> tuple[str, float, float]:
    """Setzt ``text`` und gibt Pfaddaten, Breite und Höhe zurück.

    Die Grundlinie liegt bei y=0, der Text läuft nach rechts. In Schriften
    zeigt die y-Achse nach oben, in SVG nach unten – deshalb wird beim
    Zeichnen gespiegelt.

    ``sperrung`` erweitert die Abstände zwischen den Zeichen, angegeben in
    Anteilen der Schriftgröße. Für den Untertitel gebraucht, der in der
    Vorlage deutlich gesperrt ist.
    """
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.ttLib import TTFont

    font = TTFont(datei)
    einheiten = font["head"].unitsPerEm
    faktor = groesse / einheiten
    zeichensatz = font.getBestCmap()
    glyphen = font.getGlyphSet()
    breiten = font["hmtx"].metrics

    # Kerning aus der alten kern-Tabelle, falls vorhanden. Moderne Schriften
    # legen es in GPOS ab, das wäre deutlich aufwändiger auszuwerten - für
    # einen Schriftzug aus acht Zeichen lohnt der Aufwand nicht.
    kerning: dict[tuple[str, str], int] = {}
    if "kern" in font:
        for tabelle in font["kern"].kernTables:
            kerning.update(tabelle.kernTable)

    teile: list[str] = []
    x = 0.0
    vorher: str | None = None

    for zeichen in text:
        name = zeichensatz.get(ord(zeichen))
        if name is None:
            x += groesse * 0.3  # unbekanntes Zeichen: Lücke lassen
            vorher = None
            continue

        if vorher is not None:
            x += kerning.get((vorher, name), 0) * faktor

        stift = SVGPathPen(glyphen)
        glyphen[name].draw(stift)
        daten = stift.getCommands()
        if daten:
            teile.append(
                f'<path transform="translate({x:.2f} 0) scale({faktor:.6f} {-faktor:.6f})" '
                f'd="{daten}"/>'
            )

        x += breiten[name][0] * faktor + sperrung * groesse
        vorher = name

    if sperrung:
        x -= sperrung * groesse

    hoehe = (font["hhea"].ascender - font["hhea"].descender) * faktor
    return "\n".join(teile), x, hoehe


def main() -> int:
    p = argparse.ArgumentParser(description="Schriftzug in SVG-Pfade umwandeln")
    p.add_argument("text")
    p.add_argument("--schrift", default="URW Gothic:style=Demi")
    p.add_argument("--groesse", type=float, default=100.0)
    p.add_argument("--sperrung", type=float, default=0.0)
    args = p.parse_args()

    datei = schriftdatei(args.schrift)
    pfade, breite, hoehe = zu_pfaden(args.text, datei, args.groesse, args.sperrung)

    print(f"<!-- {args.text!r} in {datei}, Breite {breite:.1f} -->", file=sys.stderr)
    print(f"BREITE={breite:.2f} HOEHE={hoehe:.2f}", file=sys.stderr)
    print(pfade)
    return 0


if __name__ == "__main__":
    sys.exit(main())
