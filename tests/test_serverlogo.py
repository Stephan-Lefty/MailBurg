"""Das Wappen der Server Edition.

Dieselbe Burg in Rot, mit dem Wort SERVER über dem »urg« von Burg.
Geprüft wird zweierlei: dass die Farben lesbar sind – auf hellem *und*
dunklem Grund – und dass die Dateien wirklich aus dem Skript stammen und
nicht jemand von Hand hineingemalt hat.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from importlib import util
from pathlib import Path

from mailburg import farben

WURZEL = Path(__file__).resolve().parent.parent
ZIEL = WURZEL / "assets" / "server"


def _werkzeug():
    laden = util.spec_from_file_location(
        "server_logo", WURZEL / "werkzeuge" / "server_logo.py"
    )
    modul = util.module_from_spec(laden)
    laden.loader.exec_module(modul)
    return modul


class FarbenTest(unittest.TestCase):
    """Rot ist nicht gleich Rot – es kommt auf den Untergrund an."""

    def test_das_wort_ist_auf_weiss_lesbar(self):
        self.assertGreaterEqual(
            farben.kontrast(farben.SERVER_ROT, farben.WEISS), 4.5
        )

    def test_das_wort_ist_auf_dunklem_grund_lesbar(self):
        """``SERVER_ROT`` käme dort nur auf 2,71 – deshalb der helle Ton."""
        self.assertLess(
            farben.kontrast(farben.SERVER_ROT, farben.GRAU_NACHT), 4.5,
            "Wenn das plötzlich reicht, ist die Palette verändert worden",
        )
        self.assertGreaterEqual(
            farben.kontrast(farben.SERVER_ROT_HELL, farben.GRAU_NACHT), 4.5
        )

    def test_die_weisse_burg_traegt_so_gut_wie_beim_blauen(self):
        """Der Maßstab ist das Original, nicht die 4,5 aus WCAG.

        Ein erster Anlauf verlangte hier 4,5 – und schlug fehl. Beim
        Nachrechnen kam heraus: Das *blaue* Icon erreicht am hellen Ende
        nur 3,51. Die Schwelle war also strenger als der Bestand, den sie
        schützen sollte. Für ein Logo gilt WCAG ohnehin nicht; was zählt,
        ist, dass die Server-Fassung nicht schlechter wird als die, die
        seit Wochen im Einsatz ist.
        """
        for blau, rot in zip(farben.ICON_VERLAUF, farben.SERVER_ICON_VERLAUF):
            with self.subTest(blau=blau, rot=rot):
                self.assertGreaterEqual(
                    farben.kontrast(farben.WEISS, rot),
                    farben.kontrast(farben.WEISS, blau),
                )

    def test_die_schlitze_heben_sich_vom_turm_ab(self):
        """Sonst ist der Turm eine Fläche statt einer Burg."""
        self.assertGreater(
            farben.kontrast(farben.SERVER_ROT_TIEF, farben.SERVER_ROT), 1.5
        )

    def test_die_leitfarbe_ist_die_der_palette(self):
        """Zwei Rot, die sich um Nuancen unterscheiden, wären schlimmer als eins."""
        self.assertEqual(farben.SERVER_ROT, farben.ROT)
        self.assertEqual(farben.SERVER_ROT_HELL, farben.ROT_HELL)


class MasseTest(unittest.TestCase):
    """Das Logo darf nicht höher werden als das der Desktop-Fassung.

    Stephan am 2026-08-31: »das rote Wort darf nicht höher sein als das B
    von Burg«. Es sitzt deshalb in dem Streifen, den die Minuskeln von
    »urg« freilassen.
    """

    def setUp(self):
        self.werkzeug = _werkzeug()

    def test_das_wort_setzt_an_der_kante_des_u_an(self):
        """Eingemessen am gerenderten Bild: Die Tinte des »u« beginnt bei 951,25."""
        self.assertAlmostEqual(self.werkzeug.WORT_X, 951.25, places=2)

    def test_es_sind_umrisse_und_keine_schrift(self):
        """``textLength`` wertet rsvg nicht aus – gemessen am 2026-08-31.

        Der erste Anlauf setzte das Wort als ``<text>``. Im Browser hätte
        es gesessen, in den erzeugten PNG war es 162 statt 300 Einheiten
        breit. Und die PNG sind das, was ausgeliefert wird.
        """
        self.assertEqual(self.werkzeug.WORT_PFADE.count("<path"), len("SERVER"))
        self.assertNotIn("textLength", self.werkzeug.WORT_PFADE)

    @unittest.skipIf(shutil.which("magick") is None, "ImageMagick fehlt")
    def test_der_block_sitzt(self):
        """Nicht gerechnet, sondern am Bild nachgemessen.

        Stephan am 2026-08-31: »Das S von Server fängt mit der äußeren
        Kante vom u an. Und das R von Server endet rechts mit der rechten
        Kante vom g« – und höher als das B darf es nicht werden.
        """
        lupe = 4
        with tempfile.TemporaryDirectory() as ordner:
            svg = Path(ordner) / "wort.svg"
            png = Path(ordner) / "wort.png"
            svg.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 420">'
                f'<g fill="#000" transform="translate({self.werkzeug.WORT_X} '
                f'{self.werkzeug.WORT_GRUNDLINIE})">{self.werkzeug.WORT_PFADE}'
                "</g></svg>",
                encoding="utf-8",
            )
            subprocess.run(
                ["magick", "-background", "white", str(svg),
                 "-resize", str(1200 * lupe), "-alpha", "remove", str(png)],
                check=True, capture_output=True,
            )
            box = subprocess.run(
                ["magick", str(png), "-fuzz", "5%", "-format", "%@", "info:"],
                check=True, capture_output=True, text=True,
            ).stdout.strip()

        breite, hoehe, links, oben = (
            int(z) for z in re.match(r"(\d+)x(\d+)\+(\d+)\+(\d+)", box).groups()
        )
        links, rechts = links / lupe, (links + breite) / lupe
        oben, unten = oben / lupe, (oben + hoehe) / lupe

        # Der Schriftzug steht auf der Grundlinie 240, seine Versalien sind
        # 739 Glypheneinheiten hoch (× 0,169), die Minuskeln 554.
        skala = 0.169
        kante_u, kante_g = 951.25, 1200.00
        oberkante_b = 240 - 739 * skala
        oberkante_urg = 240 - 554 * skala

        self.assertAlmostEqual(links, kante_u, delta=0.5)
        self.assertAlmostEqual(rechts, kante_g, delta=0.5)
        self.assertGreaterEqual(
            oben, oberkante_b,
            "SERVER ragt über das B – das Logo würde höher als das blaue",
        )
        self.assertLess(
            unten, oberkante_urg, "SERVER klebt auf den Buchstaben von »urg«"
        )


class ErzeugtTest(unittest.TestCase):
    """Die Dateien stammen aus dem Skript, nicht aus der Hand.

    Dasselbe Prinzip wie bei den Bildern der Anleitung: Was von Hand
    nachgebessert wird, veraltet still, sobald sich das Original ändert.
    """

    def setUp(self):
        self.werkzeug = _werkzeug()

    def test_alle_dateien_liegen_vor(self):
        erwartet = ["icon.svg", "banner.svg", "banner-dark.svg",
                    "icon.png", "mailburg-server.ico"]
        erwartet += [f"banner-{b}.png" for b in self.werkzeug.BREITEN]
        erwartet += [f"banner-dark-{b}.png" for b in self.werkzeug.BREITEN]
        erwartet += [f"icon-{g}.png" for g in self.werkzeug.ICONGROESSEN]

        for name in erwartet:
            with self.subTest(datei=name):
                self.assertTrue((ZIEL / name).is_file(), f"{name} fehlt")

    def test_kein_markenblau_mehr_darin(self):
        """Ein übersehener Blauton fällt im Kleinen sonst nicht auf."""
        for name in ("icon.svg", "banner.svg", "banner-dark.svg"):
            inhalt = (ZIEL / name).read_text(encoding="utf-8")
            for blau in (farben.BLAU, farben.BLAU_DUNKEL, *farben.ICON_VERLAUF):
                with self.subTest(datei=name, farbe=blau):
                    self.assertNotIn(
                        blau, inhalt, f"{name} trägt noch {blau}"
                    )

    def test_das_wort_steht_in_beiden_fassungen(self):
        hell = (ZIEL / "banner.svg").read_text(encoding="utf-8")
        dunkel = (ZIEL / "banner-dark.svg").read_text(encoding="utf-8")

        # Das Wort besteht aus Umrissen, nicht aus Schrift – nach ">SERVER<"
        # zu suchen wäre der alte, verworfene Ansatz.
        for name, inhalt in (("hell", hell), ("dunkel", dunkel)):
            with self.subTest(fassung=name):
                self.assertIn('class="edition"', inhalt)
                self.assertIn(self.werkzeug.WORT_PFADE.strip(), inhalt)
        # Die helle Fassung schaltet per @media um, wo CSS ausgewertet wird.
        self.assertIn(f".edition {{ fill: {farben.SERVER_ROT_HELL}; }}", hell)
        # Die dunkle trägt den hellen Ton fest – sie wird dort eingebunden,
        # wo GitHub die Stilangaben entfernt.
        self.assertIn(f'fill="{farben.SERVER_ROT_HELL}"', dunkel)

    def test_die_bilder_tragen_keinen_zeitstempel(self):
        """Sonst ist »aus dem Skript erzeugt« nicht nachprüfbar.

        ImageMagick legt von sich aus einen ``tIME``-Chunk und drei
        ``tEXt``-Chunks mit der Uhrzeit an. Damit unterscheidet sich jede
        Datei bei jedem Lauf, obwohl kein Pixel anders ist – fünfzehn
        geänderte Dateien im Diff, die nichts bedeuten, und keine
        Möglichkeit zu zeigen, dass zweimal dasselbe herauskommt.

        Am 2026-08-31 aufgefallen, als ein Lauf ohne jede Änderung am
        Skript fünfzehn Dateien anfasste.
        """
        import struct

        for datei in sorted(ZIEL.glob("*.png")):
            rohdaten = datei.read_bytes()
            stelle, gefunden = 8, []
            while stelle < len(rohdaten):
                laenge = struct.unpack(">I", rohdaten[stelle:stelle + 4])[0]
                art = rohdaten[stelle + 4:stelle + 8].decode("latin1")
                if art in ("tIME", "tEXt", "zTXt", "iTXt"):
                    gefunden.append(art)
                stelle += 12 + laenge

            with self.subTest(datei=datei.name):
                self.assertEqual(
                    gefunden, [],
                    f"{datei.name} trägt {gefunden} – der Lauf ist nicht "
                    f"wiederholbar",
                )

    def test_der_verlauf_hat_eine_eigene_kennung(self):
        """Sonst greift auf einer Seite mit beiden Icons das zweite ins erste."""
        inhalt = (ZIEL / "icon.svg").read_text(encoding="utf-8")

        self.assertIn("mbs-grund", inhalt)
        self.assertNotIn('id="mb-grund"', inhalt)


if __name__ == "__main__":
    unittest.main()
