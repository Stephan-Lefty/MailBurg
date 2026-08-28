"""Die Farbpalette – Form der Werte, Kontraste, Vollständigkeit."""

from __future__ import annotations

import re
import unittest

from mailburg import farben


def _palette() -> dict[str, str]:
    """Alle Farbkonstanten des Moduls."""
    return {
        name: wert
        for name, wert in vars(farben).items()
        if name.isupper() and isinstance(wert, str) and wert.startswith("#")
    }


class Form(unittest.TestCase):
    def test_alle_werte_sind_sechsstellige_hexwerte(self):
        for name, wert in _palette().items():
            with self.subTest(name=name):
                self.assertRegex(wert, r"^#[0-9a-f]{6}$")

    def test_keine_farbe_doppelt(self):
        werte = list(_palette().values())
        self.assertEqual(len(werte), len(set(werte)))

    def test_palette_ist_nicht_leer(self):
        self.assertGreaterEqual(len(_palette()), 15)

    def test_rgb(self):
        self.assertEqual(farben.rgb("#1668e3"), (22, 104, 227))
        self.assertEqual(farben.rgb("#fff"), (255, 255, 255))

    def test_rgb_lehnt_unsinn_ab(self):
        for falsch in ("blau", "#12345", "#gggggg"):
            with self.subTest(wert=falsch):
                with self.assertRaises(ValueError):
                    farben.rgb(falsch)


class Kontraste(unittest.TestCase):
    """WCAG 2.1 verlangt 4.5 für Fließtext und 3.0 für große Schrift.

    Diese Zahlen sieht man einem Farbwert nicht an - man rechnet sie nach.
    Genau deshalb steht die Prüfung hier und nicht in einer Anleitung: Der
    Fehler bei GRAU_MITTE stand jahrelang unbemerkt in dieser Palette.
    """

    def test_weiss_auf_blau(self):
        # Das Icon: weiße Zeichnung auf blauem Grund.
        self.assertGreater(farben.kontrast(farben.WEISS, farben.BLAU), 4.5)
        self.assertGreater(farben.kontrast(farben.WEISS, farben.BLAU_TIEF), 4.5)

    def test_fliesstext_im_hellen_thema(self):
        self.assertGreater(farben.kontrast(farben.GRAU, farben.GRAU_PAPIER), 4.5)
        self.assertGreater(farben.kontrast(farben.GRAU_DUNKEL, farben.WEISS), 4.5)

    def test_fliesstext_im_dunklen_thema(self):
        self.assertGreater(farben.kontrast(farben.GRAU_HELL, farben.GRAU_NACHT), 4.5)
        self.assertGreater(farben.kontrast(farben.GRAU_HELL, farben.GRAU_KOHLE), 4.5)

    def test_verweise_sind_lesbar(self):
        self.assertGreater(farben.kontrast(farben.BLAU, farben.GRAU_PAPIER), 4.5)
        # Auf dunklem Grund braucht es das helle Blau; das dunkle wäre zu leise.
        self.assertGreater(farben.kontrast(farben.BLAU_LEUCHT, farben.GRAU_NACHT), 4.5)

    def test_signalfarben_sind_lesbar(self):
        self.assertGreater(farben.kontrast(farben.ROT, farben.GRAU_PAPIER), 4.5)
        self.assertGreater(farben.kontrast(farben.GRUEN, farben.GRAU_PAPIER), 4.5)
        self.assertGreater(farben.kontrast(farben.ROT_HELL, farben.GRAU_NACHT), 4.5)
        self.assertGreater(farben.kontrast(farben.GRUEN_HELL, farben.GRAU_NACHT), 4.5)

    def test_zweitangaben_sind_lesbar(self):
        # Zurückgenommener Text braucht je Thema einen eigenen Ton. GRAU_MITTE
        # auf hellem Grund erreicht nur 2,48 und verfehlt damit sogar die 3,0
        # für große Schrift - deshalb gibt es GRAU_LEISE. Der Fehler stand in
        # der übernommenen Palette und ist erst hier aufgefallen.
        self.assertGreater(farben.kontrast(farben.GRAU_LEISE, farben.GRAU_PAPIER), 4.5)
        self.assertGreater(farben.kontrast(farben.GRAU_MITTE, farben.GRAU_NACHT), 4.5)

    def test_grau_mitte_taugt_nicht_fuer_hellen_grund(self):
        # Hält den Grund fest, warum es zwei Töne gibt. Wer GRAU_MITTE hier
        # einsetzt, macht Text unlesbar, ohne dass es auffällt.
        self.assertLess(farben.kontrast(farben.GRAU_MITTE, farben.GRAU_PAPIER), 3.0)

    def test_kontrast_ist_symmetrisch(self):
        a = farben.kontrast(farben.WEISS, farben.BLAU)
        b = farben.kontrast(farben.BLAU, farben.WEISS)
        self.assertAlmostEqual(a, b, places=10)

    def test_gleiche_farbe_hat_kontrast_eins(self):
        self.assertAlmostEqual(farben.kontrast(farben.BLAU, farben.BLAU), 1.0)

    def test_schwarz_auf_weiss_ist_das_hoechste(self):
        self.assertAlmostEqual(farben.kontrast("#000000", "#ffffff"), 21.0, places=1)


class AlsCss(unittest.TestCase):
    def test_beide_themen_liefern_dieselben_namen(self):
        namen = [
            set(re.findall(r"(--[a-z-]+):", farben.als_css(dunkel)))
            for dunkel in (False, True)
        ]
        self.assertEqual(namen[0], namen[1])

    def test_hell_und_dunkel_unterscheiden_sich(self):
        self.assertNotEqual(farben.als_css(False), farben.als_css(True))

    def test_waehler_stimmt(self):
        self.assertTrue(farben.als_css(False).startswith(":root {"))
        self.assertIn('data-thema="dunkel"', farben.als_css(True))

    def test_werte_stammen_aus_der_palette(self):
        # Eine zweite, von Hand geschriebene Liste derselben Werte wiche früher
        # oder später ab - und man fände es erst, wenn ein Knopf eine andere
        # Farbe hat als der Rest.
        erlaubt = set(_palette().values())
        for dunkel in (False, True):
            for wert in re.findall(r": (#[0-9a-f]{6});", farben.als_css(dunkel)):
                with self.subTest(dunkel=dunkel, wert=wert):
                    self.assertIn(wert, erlaubt)


if __name__ == "__main__":
    unittest.main()
