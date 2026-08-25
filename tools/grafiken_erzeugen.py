#!/usr/bin/env python3
"""Erzeugt Banner und Programmsymbol aus der Ursprungsgrafik.

Aufruf aus dem Wurzelverzeichnis des Projekts::

    python3 tools/grafiken_erzeugen.py

Quelle ist ``assets/Grafik-MailBurg-mit-Icon.png``: links die Burg, in der
Mitte der Schriftzug, rechts das Programmsymbol. Daraus entstehen die
freigestellten Fassungen in ``assets/``.

Warum das ein Skript ist und keine Handarbeit: Das Freistellen hat drei
Fallstricke, die man beim zweiten Mal garantiert wieder übersieht.

1. **Die Burg ist weiß.** Wer schlicht alles Helle durchsichtig macht,
   stanzt sie mit aus – auf dunklem Grund bleibt eine schwarze Burg übrig.
2. **Die Punzen sind weiß.** Die Innenflächen von „a", „B" und „g" sind vom
   Bildrand aus nicht erreichbar. Lässt man sie stehen, sieht man im hellen
   Modus nichts und im dunklen weiße Flecken mitten in den Buchstaben.
3. **Der Schlagschatten ist grau, nicht weiß.** Eine Helligkeitsschwelle
   lässt ihn stehen, und um das Symbol bleibt ein heller Saum sichtbar.

Deshalb wird je nach Bildbereich unterschiedlich vorgegangen – siehe unten.

Zusätzlich zur hellen entsteht eine dunkle Fassung des Banners: Der
Schriftzug „Mail" ist dunkelblau und auf schwarzem Grund kaum zu lesen.
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import numpy as np
    from PIL import Image, ImageFilter
    from scipy import ndimage
except ImportError as exc:  # pragma: no cover
    sys.exit(f"Fehlt: {exc.name}. Nötig sind Pillow, numpy und scipy.")

Image.MAX_IMAGE_PIXELS = None

ASSETS = Path(__file__).resolve().parent.parent / "assets"
QUELLE = ASSETS / "Grafik-MailBurg-mit-Icon.png"

#: Bildausschnitte in der Ursprungsgrafik, ermittelt über die Lücken
#: zwischen den Inhaltsblöcken.
BANNER_BOX = (150, 160, 4370, 1700)
ICON_BOX = (4520, 400, 5800, 1720)

#: Grenze zwischen Burgbild und Schriftzug, auf den Bannerausschnitt bezogen.
TEXT_AB = 1630

#: Ab dieser Größe gilt eine eingeschlossene weiße Fläche als gewolltes
#: Bildelement. Der Briefumschlag hat rund 57.000 und 74.000 Pixel, der
#: weiße Fahnenmast dagegen nur 1.400 – dazwischen ist reichlich Luft.
UMSCHLAG_MINDESTGROESSE = 10_000

#: Größen des Programmsymbols. 16 bis 48 für Fensterleisten und Startmenüs,
#: 512 und 1024 für hochauflösende Bildschirme und die Paketformate.
ICON_GROESSEN = (512, 256, 128, 64, 48, 32, 16)


def weiche_kante(hell: np.ndarray) -> np.ndarray:
    """Verlauf für die Randglättung: je heller, desto durchsichtiger."""
    return np.clip((250 - hell) * 255 // 40, 0, 255)


def banner_freistellen(bild: Image.Image) -> Image.Image:
    """Stellt Burg und Schriftzug frei – mit zwei verschiedenen Regeln.

    Im Burgbereich verschwindet nur, was vom Bildrand aus zusammenhängend
    erreichbar ist, damit der weiße Briefumschlag erhalten bleibt. Kleine
    eingeschlossene Flächen wie der Fahnenmast fliegen trotzdem heraus.

    Im Schriftbereich verschwindet jedes Weiß, denn dort gibt es kein
    gewolltes weißes Element – wohl aber die Punzen der Buchstaben.
    """
    daten = np.array(bild).astype(int)
    hell = daten[:, :, :3].min(axis=2)
    weiss = hell > 240

    markiert, anzahl = ndimage.label(weiss)
    am_rand = (
        set(markiert[0, :]) | set(markiert[-1, :])
        | set(markiert[:, 0]) | set(markiert[:, -1])
    )
    am_rand.discard(0)

    hintergrund = np.isin(markiert, list(am_rand))

    # Eingeschlossene Flächen im Burgbereich: nur die großen sind gewollt.
    groessen = ndimage.sum(weiss, markiert, range(1, anzahl + 1))
    for nummer in range(1, anzahl + 1):
        if nummer in am_rand or groessen[nummer - 1] >= UMSCHLAG_MINDESTGROESSE:
            continue
        hintergrund |= markiert == nummer

    # Im Schriftbereich zählt jedes Weiß als Hintergrund.
    hintergrund[:, TEXT_AB:] = weiss[:, TEXT_AB:]

    alpha = np.full(hell.shape, 255, dtype=np.int16)
    kante = weiche_kante(hell)
    alpha[hintergrund] = kante[hintergrund]

    ergebnis = bild.convert("RGBA")
    ergebnis.putalpha(Image.fromarray(alpha.astype(np.uint8)))
    return ergebnis.crop(ergebnis.getbbox())


def icon_freistellen(bild: Image.Image) -> Image.Image:
    """Stellt das Programmsymbol über seine blaue Fläche frei.

    Nicht über Helligkeit: Der Schlagschatten ringsum ist hellgrau und
    bliebe dabei als Saum stehen. Betriebssysteme setzen ohnehin ihren
    eigenen Schatten, ein mitgelieferter sähe doppelt aus.
    """
    daten = np.array(bild).astype(int)
    blau = (daten[:, :, 2] > daten[:, :, 0] + 25) & (daten[:, :, 2] > 70)

    markiert, anzahl = ndimage.label(blau)
    groessen = ndimage.sum(blau, markiert, range(1, anzahl + 1))
    flaeche = markiert == (int(np.argmax(groessen)) + 1)

    # Die weiße Burg ist ein Loch in der blauen Fläche und gehört dazu.
    form = ndimage.binary_fill_holes(flaeche)
    # Zwei Pixel abtragen, damit vom Schatten nichts hängen bleibt, dann
    # weich zeichnen – sonst hätte die Rundung Treppenstufen.
    form = ndimage.binary_erosion(form, iterations=2)
    alpha = Image.fromarray((form * 255).astype(np.uint8))
    alpha = alpha.filter(ImageFilter.GaussianBlur(1.6))

    ergebnis = bild.convert("RGBA")
    ergebnis.putalpha(alpha)
    ergebnis = ergebnis.crop(ergebnis.getbbox())

    kante = max(ergebnis.size)
    quadrat = Image.new("RGBA", (kante, kante), (0, 0, 0, 0))
    quadrat.paste(
        ergebnis,
        ((kante - ergebnis.width) // 2, (kante - ergebnis.height) // 2),
        ergebnis,
    )
    return quadrat


def aufhellen(bild: Image.Image) -> Image.Image:
    """Macht den Banner für dunkle Oberflächen lesbar.

    „Mail" ist dunkelblau, die Türme sind dunkelgrau – auf schwarzem Grund
    verschwindet beides. Angehoben werden nur diese dunklen Töne; das
    kräftige Blau von „Burg" und der Fahne bleibt unangetastet, damit das
    Erscheinungsbild dasselbe bleibt.

    Angehoben statt invertiert, weil aus Dunkelblau sonst Gelb würde.
    """
    daten = np.array(bild).astype(np.float64)
    spitze = daten[:, :, :3].max(axis=2)
    staerke = (np.clip((130 - spitze) / 130, 0, 1) * 0.86)[:, :, None]
    daten[:, :, :3] = np.where(
        (spitze < 130)[:, :, None],
        daten[:, :, :3] + (255 - daten[:, :, :3]) * staerke,
        daten[:, :, :3],
    )
    return Image.fromarray(daten.astype(np.uint8), "RGBA")


def main() -> int:
    if not QUELLE.exists():
        sys.exit(f"Ursprungsgrafik fehlt: {QUELLE}")

    quelle = Image.open(QUELLE).convert("RGB")

    banner = banner_freistellen(quelle.crop(BANNER_BOX))
    banner.save(ASSETS / "banner.png")
    dunkel = aufhellen(banner)
    dunkel.save(ASSETS / "banner-dark.png")

    for bild, name in ((banner, "banner"), (dunkel, "banner-dark")):
        for breite in (1600, 800):
            hoehe = round(bild.height * breite / bild.width)
            bild.resize((breite, hoehe), Image.LANCZOS).save(
                ASSETS / f"{name}-{breite}.png"
            )

    icon = icon_freistellen(quelle.crop(ICON_BOX))
    icon.resize((1024, 1024), Image.LANCZOS).save(ASSETS / "icon.png")
    for groesse in ICON_GROESSEN:
        icon.resize((groesse, groesse), Image.LANCZOS).save(
            ASSETS / f"icon-{groesse}.png"
        )
    # Windows erwartet alle Größen in einer einzigen Datei.
    icon.resize((256, 256), Image.LANCZOS).save(
        ASSETS / "mailburg.ico",
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
    )

    print(f"Banner {banner.size[0]}×{banner.size[1]}, hell und dunkel")
    print(f"Symbol {icon.size[0]}×{icon.size[1]}, {len(ICON_GROESSEN) + 1} Größen und .ico")
    return 0


if __name__ == "__main__":
    sys.exit(main())
