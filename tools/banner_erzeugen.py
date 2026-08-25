#!/usr/bin/env python3
"""Setzt das Banner als SVG zusammen.

Aufruf aus dem Wurzelverzeichnis::

    python3 tools/banner_erzeugen.py

Erzeugt ``assets/banner.svg``. Der Schriftzug wird dabei aus der Schrift in
Pfade umgewandelt (siehe :mod:`schrift_zu_pfaden`), die Burg stammt aus
``icon.svg`` und wird nur anders eingefärbt.

**Eine Burg, zwei Farbgebungen.** Die Vorlage hat für Banner und Symbol zwei
leicht verschiedene Zeichnungen. Hier ist es dieselbe Geometrie – einmal
weiß auf blauem Grund, einmal farbig auf durchsichtigem. Das ist nicht
Bequemlichkeit, sondern besser: Ein Zeichen, das in jeder Verwendung
identisch ist, prägt sich ein.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schrift_zu_pfaden import schriftdatei, zu_pfaden  # noqa: E402

WURZEL = Path(__file__).resolve().parent.parent
ASSETS = WURZEL / "assets"

SCHRIFT = "URW Gothic:style=Demi"

#: Maße des Bildfelds. Das Seitenverhältnis entspricht der Vorlage.
BREITE, HOEHE = 1200, 420

#: Die Burg stammt aus icon.svg (Bildfeld 512), Inhalt dort x 54 bis 458 und
#: y 55 bis 447. Skala und Versatz rücken sie mit etwas Luft ins Bildfeld.
BURG_SKALA = 1.02
BURG_X, BURG_Y = -45, -46

#: Grundfarben und ihre Entsprechung für dunkle Oberflächen.
FARBEN = {
    "wort": ("#0d2141", "#d6dde8"),
    "turm": ("#3a4048", "#97a1ad"),
    "boden": ("#3a4048", "#97a1ad"),
    "unter": ("#55606e", "#9aa5b3"),
    "scharte": ("#20262f", "#5b6672"),
}

SCHRIFT_GROESSE = 169
UNTER_GROESSE = 29
UNTER_SPERRUNG = 0.16

TEXT_X = 500
GRUNDLINIE = 240
UNTER_GRUNDLINIE = 320

# Die Burg aus icon.svg, nach Bauteilen getrennt, damit jedes seine eigene
# Farbe bekommen kann. Die Geometrie ist unverändert übernommen.
BODEN = "M56 446 C150 420 362 420 456 446 C362 428 150 428 56 446 Z"
MAST = "M250 55 h9 v120 h-9 Z"
FAHNE = "M259 66 C292 59 316 80 346 73 C336 97 306 112 259 107 Z"
MITTELTURM = ("M180 148 h32 v20 h20 v-20 h45 v20 h20 v-20 h32 v24 "
              "l-12 36 v50 h-125 v-50 l-12 -36 Z")
# Im Banner ist die Burg farbig, und daraus folgt eine andere Schichtung als
# beim einfarbigen Symbol: Der Mittelbau ist blau, die grauen Seitentürme
# stehen davor und reichen bis zum Boden durch. Eine durchgehende Mauer wie
# im Symbol würde den blauen Mittelbau verdecken.
TURM_LINKS = "M89 220 h21 v12 h13 v-12 h24 v12 h13 v-12 h20 v213 h-91 Z"
TURM_RECHTS = "M329 220 h21 v12 h13 v-12 h23 v12 h13 v-12 h21 v213 h-91 Z"
MITTELBAU = "M150 256 h209 v177 h-209 Z"

#: Schießscharten. Oben rund, unten gerade - das gibt der Burg erst ihren
#: Charakter, ohne sie zu überladen.
SCHARTE_LINKS = "M124 302 a11 11 0 0 1 22 0 v62 h-22 Z"
SCHARTE_RECHTS = "M364 302 a11 11 0 0 1 22 0 v62 h-22 Z"
SCHARTEN_MITTE = (
    "M199 196 a8 8 0 0 1 16 0 v32 h-16 Z "
    "M247 190 a8 8 0 0 1 16 0 v38 h-16 Z "
    "M295 196 a8 8 0 0 1 16 0 v32 h-16 Z"
)
TORBOGEN = "M173 435 v-69 a81.5 83 0 0 1 163 0 v69 Z"
UMSCHLAG = "M200 338 h109 a10 10 0 0 1 10 10 v75 a10 10 0 0 1 -10 10 h-109 a10 10 0 0 1 -10 -10 v-75 a10 10 0 0 1 10 -10 Z"
KLAPPE = "M189 345 L254.5 406 L320 345"


def bauen() -> str:
    datei = schriftdatei(SCHRIFT)
    mail, breite_mail, _ = zu_pfaden("Mail", datei, SCHRIFT_GROESSE)
    burg, breite_burg, _ = zu_pfaden("Burg", datei, SCHRIFT_GROESSE)
    unter, breite_unter, _ = zu_pfaden(
        "E-MAILS. SICHER BEWAHRT.", datei, UNTER_GROESSE, UNTER_SPERRUNG
    )

    gesamt = breite_mail + breite_burg
    # Der Untertitel wird unter dem Schriftzug zentriert, die Zierlinien
    # füllen den Rest bis zu dessen Kanten.
    unter_x = TEXT_X + (gesamt - breite_unter) / 2
    linie_lang = (gesamt - breite_unter) / 2 - 22
    linie_y = UNTER_GRUNDLINIE - UNTER_GROESSE * 0.32

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {BREITE} {HOEHE}"
     width="{BREITE}" height="{HOEHE}" role="img" aria-label="MailBurg – E-Mails. Sicher bewahrt.">
  <title>MailBurg – E-Mails. Sicher bewahrt.</title>
  <style>
    /* Die Grundfarben stehen als fill-Attribut an den Elementen selbst,
       nicht in Variablen. Das ist Absicht: CSS-Variablen werden von
       schlanken Renderern wie rsvg nicht ausgewertet, und GitHub entfernt
       Stilangaben aus eingebetteten SVG ganz. Ohne Auswertung fielen die
       Flächen auf Schwarz zurück. So wirkt der dunkle Modus, wo CSS
       unterstützt wird - und wo nicht, sieht es trotzdem richtig aus. */
    @media (prefers-color-scheme: dark) {{
      .wort  {{ fill: {FARBEN["wort"][1]}; }}
      .turm  {{ fill: {FARBEN["turm"][1]}; }}
      .boden {{ fill: {FARBEN["boden"][1]}; }}
      .unter {{ fill: {FARBEN["unter"][1]}; }}
      .scharte {{ fill: {FARBEN["scharte"][1]}; }}
    }}
  </style>

  <!-- Burg -->
  <g transform="translate({BURG_X} {BURG_Y}) scale({BURG_SKALA})">
    <path class="boden" fill="{FARBEN["boden"][0]}" d="{BODEN}"/>

    <!-- Dahinter: der hohe Turm mit Fahne. Der Mast ist grau wie das
         Mauerwerk, nur das Tuch trägt die Farbe. -->
    <path class="turm" fill="{FARBEN["turm"][0]}" d="{MAST}"/>
    <path fill="#1668e3" d="{FAHNE}"/>
    <path fill="#1668e3" d="{MITTELTURM}"/>
    <path fill="#0d3a8a" d="{SCHARTEN_MITTE}"/>

    <!-- Davor: eine durchgehende graue Front aus beiden Türmen und dem
         Mauerstück dazwischen. -->
    <path class="turm" fill="{FARBEN["turm"][0]}" d="{MITTELBAU}"/>
    <path class="turm" fill="{FARBEN["turm"][0]}" d="{TURM_LINKS}"/>
    <path class="turm" fill="{FARBEN["turm"][0]}" d="{TURM_RECHTS}"/>
    <path class="scharte" fill="{FARBEN["scharte"][0]}" d="{SCHARTE_LINKS}"/>
    <path class="scharte" fill="{FARBEN["scharte"][0]}" d="{SCHARTE_RECHTS}"/>

    <!-- Das Tor bricht die graue Front auf und bringt die Farbe nach vorn -->
    <path fill="#1668e3" d="{TORBOGEN}"/>
    <path fill="#ffffff" d="{UMSCHLAG}"/>
    <path fill="none" stroke="#1668e3" stroke-width="11"
          stroke-linecap="round" stroke-linejoin="round" d="{KLAPPE}"/>
  </g>

  <!-- Wortmarke: "Mail" im dunklen Ton, "Burg" im Blau der Marke -->
  <g class="wort" fill="{FARBEN["wort"][0]}" transform="translate({TEXT_X} {GRUNDLINIE})">
{mail}
  </g>
  <g fill="#1668e3" transform="translate({TEXT_X + breite_mail:.2f} {GRUNDLINIE})">
{burg}
  </g>

  <!-- Untertitel mit Zierlinien -->
  <g class="unter" fill="{FARBEN["unter"][0]}" transform="translate({unter_x:.2f} {UNTER_GRUNDLINIE})">
{unter}
  </g>
  <rect x="{TEXT_X}" y="{linie_y:.2f}" width="{linie_lang:.2f}" height="3" fill="#1668e3"/>
  <rect x="{TEXT_X + gesamt - linie_lang:.2f}" y="{linie_y:.2f}"
        width="{linie_lang:.2f}" height="3" fill="#1668e3"/>
</svg>
"""


def dunkelfassung(svg: str) -> str:
    """Erzeugt aus dem Banner eine Fassung für dunkle Oberflächen.

    Nötig, weil GitHub Stilangaben aus eingebetteten SVG entfernt – die
    ``@media``-Regel im Banner greift dort nicht. Für die Einbindung per
    ``<picture>`` braucht es deshalb eine eigene Datei, in der die hellen
    Farbwerte schon eingesetzt sind.
    """
    for hell, dunkel in FARBEN.values():
        svg = svg.replace(f'fill="{hell}"', f'fill="{dunkel}"')
    return svg


def main() -> int:
    import subprocess

    svg = bauen()
    (ASSETS / "banner.svg").write_text(svg, encoding="utf-8")
    (ASSETS / "banner-dark.svg").write_text(dunkelfassung(svg), encoding="utf-8")

    # Rastergrafiken für Stellen, an denen SVG nicht taugt – etwa als
    # Vorschaubild in sozialen Netzen.
    for name in ("banner", "banner-dark"):
        for breite in (1600, 800):
            subprocess.run(
                ["rsvg-convert", "-w", str(breite),
                 str(ASSETS / f"{name}.svg"), "-o", str(ASSETS / f"{name}-{breite}.png")],
                check=False,
            )

    fuer = ASSETS / "banner.svg"
    print(f"banner.svg und banner-dark.svg geschrieben ({fuer.stat().st_size:,} Byte)")
    print("dazu je eine Rasterfassung in 1600 und 800 Pixeln Breite")
    return 0


if __name__ == "__main__":
    sys.exit(main())
