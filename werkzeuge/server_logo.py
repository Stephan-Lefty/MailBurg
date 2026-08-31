#!/usr/bin/env python3
"""Erzeugt Icon und Banner der Server Edition aus denen der Desktop-Fassung.

    python werkzeuge/server_logo.py

**Warum abgeleitet und nicht gezeichnet.** Es sind dieselbe Burg, derselbe
Schriftzug, dieselben Maße – nur in Rot und mit dem Wort SERVER darüber.
Zwei getrennt gepflegte Zeichnungen würden auseinanderlaufen, sobald
jemand am Original etwas verschiebt. So ist die Server-Fassung immer die
aktuelle, und ein Blick in dieses Skript sagt, worin genau sie sich
unterscheidet.

**Die Farben.** Das Markenblau wird zum Rot der Palette, der dunkle
Blauton der Fensterschlitze zu einem entsprechend tiefen Rot. Für das
Icon gibt es einen eigenen Verlauf, wie beim blauen auch.

**Das Wort SERVER bildet mit »Burg« einen Block.** Es steht über den
drei Buchstaben »urg«, kantenbündig mit ihnen und nicht höher als das
»B«. Wie das eingemessen wurde, steht bei ``WORT_PFADE``.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
ASSETS = WURZEL / "assets"
ZIEL = ASSETS / "server"

sys.path.insert(0, str(WURZEL))
from mailburg import farben  # noqa: E402 – erst nach dem Pfad möglich

#: Blau wird Rot. Die Werte stehen in ``mailburg/farben.py``, nicht hier –
#: sonst führt das Skript eine zweite Liste derselben Farben, und die
#: weicht irgendwann ab.
FARBEN = {
    farben.BLAU: farben.SERVER_ROT,             # Turm, Fahne, Tor, Schriftzug
    farben.BLAU_DUNKEL: farben.SERVER_ROT_TIEF,  # die Fensterschlitze
}

#: Der Verlauf im Icon. Oben hell, unten tief – wie beim blauen.
VERLAUF = dict(zip(farben.ICON_VERLAUF, farben.SERVER_ICON_VERLAUF))

#: **Das Wort steht als Pfade da, nicht als Schrift.**
#:
#: Der erste Anlauf setzte es als ``<text>`` mit ``textLength`` – auf dem
#: Papier elegant, in der Praxis unbrauchbar: **rsvg wertet
#: ``textLength`` nicht aus.** Gemessen am gerenderten Bild war das Wort
#: 162 statt 300 Einheiten breit. Im Browser hätte es gesessen, in jedem
#: erzeugten PNG nicht – und die PNG sind das, was ausgeliefert wird.
#:
#: Also Umrisse. Sie stammen aus DejaVu Sans Bold, geholt mit fontTools
#: und hier einmal festgeschrieben; das Skript braucht fontTools deshalb
#: nicht. Nebenbei ist das Wort damit auf jedem Rechner dasselbe, auch wo
#: die Schrift fehlt.
#:
#: **Die Maße sind eingemessen, nicht gerechnet.** Der Glyphenursprung
#: ist nicht die Kante des Buchstabens – dazwischen liegt die Seitenlage.
#: Gesetzt wurde deshalb iterativ: rendern, die Tinte am Bild messen,
#: nachziehen. Ergebnis bei vierfacher Auflösung:
#:
#: * linke Kante des S bei 951,50 – die des »u« liegt bei 951,25
#: * rechte Kante des R bei 1200,00 – genau die des »g«
#: * Oberkante bei 115,50 – die des »B« liegt bei 115,11, das Wort bleibt
#:   also darunter und das Logo keinen Punkt höher als das blaue
#: * darunter 1,1 Einheiten Luft bis zum »urg«
#:
#: Stephan am 2026-08-31: »So dass es Server mit dem Wort Burg einen
#: Block ergibt.«
WORT_X, WORT_GRUNDLINIE = 951.25, 143.8

WORT_PFADE = """\
  <path transform="translate(-1.7499 0) scale(0.018285 -0.018285)" d="M1227 1446V1130Q1104 1185 987.0 1213.0Q870 1241 766 1241Q628 1241 562.0 1203.0Q496 1165 496 1085Q496 1025 540.5 991.5Q585 958 702 934L866 901Q1115 851 1220.0 749.0Q1325 647 1325 459Q1325 212 1178.5 91.5Q1032 -29 731 -29Q589 -29 446.0 -2.0Q303 25 160 78V403Q303 327 436.5 288.5Q570 250 694 250Q820 250 887.0 292.0Q954 334 954 412Q954 482 908.5 520.0Q863 558 727 588L578 621Q354 669 250.5 774.0Q147 879 147 1057Q147 1280 291.0 1400.0Q435 1520 705 1520Q828 1520 958.0 1501.5Q1088 1483 1227 1446Z"/>
  <path transform="translate(42.4073 0) scale(0.018285 -0.018285)" d="M188 1493H1227V1202H573V924H1188V633H573V291H1249V0H188Z"/>
  <path transform="translate(85.1749 0) scale(0.018285 -0.018285)" d="M735 831Q856 831 908.5 876.0Q961 921 961 1024Q961 1126 908.5 1170.0Q856 1214 735 1214H573V831ZM573 565V0H188V1493H776Q1071 1493 1208.5 1394.0Q1346 1295 1346 1081Q1346 933 1274.5 838.0Q1203 743 1059 698Q1138 680 1200.5 616.5Q1263 553 1327 424L1536 0H1126L944 371Q889 483 832.5 524.0Q776 565 682 565Z"/>
  <path transform="translate(131.1973 0) scale(0.018285 -0.018285)" d="M10 1493H397L793 391L1188 1493H1575L1022 0H563Z"/>
  <path transform="translate(177.3659 0) scale(0.018285 -0.018285)" d="M188 1493H1227V1202H573V924H1188V633H573V291H1249V0H188Z"/>
  <path transform="translate(220.1334 0) scale(0.018285 -0.018285)" d="M735 831Q856 831 908.5 876.0Q961 921 961 1024Q961 1126 908.5 1170.0Q856 1214 735 1214H573V831ZM573 565V0H188V1493H776Q1071 1493 1208.5 1394.0Q1346 1295 1346 1081Q1346 933 1274.5 838.0Q1203 743 1059 698Q1138 680 1200.5 616.5Q1263 553 1327 424L1536 0H1126L944 371Q889 483 832.5 524.0Q776 565 682 565Z"/>
"""

#: Das Wort auf hellem Grund. Auf Weiß kommt es auf 5,62.
ROT_HELLER_GRUND = farben.SERVER_ROT

#: Und auf dunklem. ``SERVER_ROT`` käme dort nur auf 2,71 – unlesbar.
#: ``SERVER_ROT_HELL`` erreicht 7,07.
ROT_DUNKLER_GRUND = farben.SERVER_ROT_HELL

BREITEN = (800, 1600, 2800)
ICONGROESSEN = (16, 32, 48, 64, 128, 256, 512, 2048)


def _wortmarke(farbe: str) -> str:
    return f"""
  <!-- SERVER, als Block über dem "urg" von Burg. Maße und Herkunft der
       Umrisse stehen in werkzeuge/server_logo.py -->
  <g class="edition" fill="{farbe}" transform="translate({WORT_X} {WORT_GRUNDLINIE})">
{WORT_PFADE}  </g>
"""


def _banner(quelle: Path, ziel: Path, *, dunkel: bool) -> None:
    text = quelle.read_text(encoding="utf-8")

    for alt, neu in FARBEN.items():
        text = text.replace(alt, neu)

    farbe = ROT_DUNKLER_GRUND if dunkel else ROT_HELLER_GRUND
    text = text.replace("\n  <!-- Untertitel", _wortmarke(farbe) + "\n  <!-- Untertitel")

    # In der hellen Fassung schaltet eine @media-Regel auf die dunklen
    # Töne um, wo der Renderer CSS auswertet. Das Wort muss mit.
    if not dunkel:
        text = text.replace(
            "      .scharte { fill: #5b6672; }",
            "      .scharte { fill: #5b6672; }\n"
            f"      .edition {{ fill: {ROT_DUNKLER_GRUND}; }}",
        )

    text = text.replace(
        'aria-label="MailBurg – E-Mails. Sicher bewahrt."',
        'aria-label="MailBurg Server Edition – E-Mails. Sicher bewahrt."',
    ).replace(
        "<title>MailBurg – E-Mails. Sicher bewahrt.</title>",
        "<title>MailBurg Server Edition – E-Mails. Sicher bewahrt.</title>",
    )
    ziel.write_text(text, encoding="utf-8")


def _icon(quelle: Path, ziel: Path) -> None:
    text = quelle.read_text(encoding="utf-8")
    for alt, neu in {**FARBEN, **VERLAUF}.items():
        text = text.replace(alt, neu)
    # Eigene Kennung für den Verlauf: Stehen beide Icons auf derselben
    # Seite, greift sonst das zweite auf den Verlauf des ersten zu.
    text = text.replace("mb-grund", "mbs-grund")
    text = text.replace(
        'aria-label="MailBurg"', 'aria-label="MailBurg Server Edition"'
    ).replace("<title>MailBurg</title>", "<title>MailBurg Server Edition</title>")
    ziel.write_text(text, encoding="utf-8")


def _rendern(svg: Path, png: Path, breite: int) -> None:
    subprocess.run(
        ["magick", "-background", "none", str(svg),
         "-resize", str(breite),
         # **Acht Bit, ausdrücklich.** ImageMagick schreibt sonst 16 Bit,
         # und daran ist am 2026-08-30 schon einmal ein Startbild
         # gescheitert - Tk konnte es nicht lesen und zeigte nichts an.
         "-depth", "8",
         # **Ohne Zeitstempel.** ImageMagick legt sonst einen tIME-Chunk
         # und drei tEXt-Chunks mit der Uhrzeit an. Dann unterscheidet
         # sich jede Datei bei jedem Lauf, obwohl kein Pixel anders ist -
         # fünfzehn geänderte Dateien im Diff, die nichts bedeuten. Und
         # die Zusage, dass sich die Bilder aus dem Skript ergeben, wäre
         # nicht nachprüfbar: Man könnte nie zeigen, dass zweimal
         # dasselbe herauskommt.
         "-define", "png:exclude-chunk=tIME,date,tEXt",
         str(png)],
        check=True, capture_output=True,
    )


def main() -> int:
    if shutil.which("magick") is None:
        print("ImageMagick fehlt – »magick« ist nicht im Suchpfad.",
              file=sys.stderr)
        return 1

    ZIEL.mkdir(parents=True, exist_ok=True)

    _icon(ASSETS / "icon.svg", ZIEL / "icon.svg")
    _banner(ASSETS / "banner.svg", ZIEL / "banner.svg", dunkel=False)
    _banner(ASSETS / "banner-dark.svg", ZIEL / "banner-dark.svg", dunkel=True)

    for breite in BREITEN:
        _rendern(ZIEL / "banner.svg", ZIEL / f"banner-{breite}.png", breite)
        _rendern(ZIEL / "banner-dark.svg", ZIEL / f"banner-dark-{breite}.png", breite)

    for groesse in ICONGROESSEN:
        _rendern(ZIEL / "icon.svg", ZIEL / f"icon-{groesse}.png", groesse)
    shutil.copyfile(ZIEL / "icon-512.png", ZIEL / "icon.png")

    # Die .ico für Windows: mehrere Größen in einer Datei, damit das
    # System für Taskleiste, Fenstertitel und Explorer die passende
    # nehmen kann, statt eine große herunterzurechnen.
    subprocess.run(
        ["magick", *[str(ZIEL / f"icon-{g}.png") for g in (16, 32, 48, 64, 128, 256)],
         str(ZIEL / "mailburg-server.ico")],
        check=True, capture_output=True,
    )

    anzahl = len(list(ZIEL.iterdir()))
    print(f"{anzahl} Dateien in {ZIEL.relative_to(WURZEL)} erneuert.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
