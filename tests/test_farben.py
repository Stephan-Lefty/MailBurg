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

    #: Namen, die absichtlich auf denselben Wert zeigen. Die Server
    #: Edition führt kein eigenes Rot: Zwei Rot, die sich um Nuancen
    #: unterscheiden, wären schlimmer als eines – niemand könnte sie
    #: auseinanderhalten, aber jeder müsste sich fragen, welches gerade
    #: gemeint ist. Dass sie gleich *bleiben*, prüft
    #: ``tests/test_serverlogo.py``.
    ZWEITNAMEN = {"SERVER_ROT", "SERVER_ROT_HELL"}

    def test_keine_farbe_doppelt(self):
        """Zwei Namen für fast denselben Ton sind eine Fehlerquelle.

        Ausgenommen sind ausdrückliche Zweitnamen – die zeigen auf
        *genau* denselben Wert und sind damit keine zweite Farbe,
        sondern ein zweiter Blickwinkel auf dieselbe.
        """
        werte = [
            wert for name, wert in _palette().items()
            if name not in self.ZWEITNAMEN
        ]
        self.assertEqual(len(werte), len(set(werte)))

    def test_die_zweitnamen_zeigen_wirklich_auf_bekannte_farben(self):
        """Sonst schmuggelt sich unter dem Etikett eine neue Farbe ein."""
        palette = _palette()
        uebrige = {
            wert for name, wert in palette.items()
            if name not in self.ZWEITNAMEN
        }
        for name in self.ZWEITNAMEN:
            with self.subTest(name=name):
                self.assertIn(palette[name], uebrige)

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


class BereichsrahmenTest(unittest.TestCase):
    """Die Kanten, die die Oberfläche gliedern.

    Aus dem Nutzer-Feedback vom 2026-09-01: »Für meinen Geschmack fehlen
    da ein paar Rahmen oder farbliche Abhebungen.« Die Antwort darauf
    darf keine ausgedachte Farbe sein – sie säße im dunklen Thema falsch
    und im Hochkontrast-Thema erst recht, also ausgerechnet dort, wo
    Kanten am nötigsten sind.
    """

    @classmethod
    def setUpClass(cls):
        try:
            from PySide6.QtWidgets import QApplication
        except ImportError:  # pragma: no cover
            raise unittest.SkipTest("PySide6 fehlt")
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")

    def test_die_teilergriffe_sind_sichtbar(self):
        """Sonst weiß niemand, dass sich die Bereiche verschieben lassen."""
        from mailburg.ui import farben

        blatt = farben.bereichsrahmen()

        self.assertIn("QSplitter::handle", blatt)

    def test_der_mailkopf_hebt_sich_ab(self):
        from mailburg.ui import farben

        blatt = farben.bereichsrahmen()

        self.assertIn("QLabel#mailkopf", blatt)
        self.assertIn("border-bottom", blatt)

    def test_keine_einprogrammierte_farbe(self):
        """Jeder Farbwert muss aus der Palette des Themas stammen.

        Ein fester Ton säße in zwei von drei Themen falsch. Geprüft wird
        deshalb, dass jeder Hexwert im Stylesheet auch wirklich in der
        aktuellen Palette vorkommt.
        """
        import re

        from PySide6.QtGui import QPalette

        from mailburg.ui import farben

        palette = self.app.palette()
        aus_der_palette = {
            palette.color(rolle).name()
            for rolle in (
                QPalette.Window, QPalette.WindowText, QPalette.Base,
                QPalette.AlternateBase, QPalette.Text, QPalette.Button,
                QPalette.ButtonText, QPalette.Mid, QPalette.Midlight,
                QPalette.Dark, QPalette.Light, QPalette.Shadow,
                QPalette.Highlight, QPalette.HighlightedText,
            )
        }

        for wert in re.findall(r"#[0-9a-fA-F]{6}", farben.bereichsrahmen()):
            with self.subTest(wert=wert):
                self.assertIn(
                    wert.lower(), {f.lower() for f in aus_der_palette},
                    f"»{wert}« steht in keiner Palettenrolle – "
                    f"eine ausgedachte Farbe bricht fremde Themen",
                )

    def test_die_kante_ist_gegen_den_inhalt_zu_sehen(self):
        """Eine Grenze, die man nicht sieht, ist keine.

        Gemessen wird gegen ``Base`` – den Hintergrund der Bereiche, die
        sie trennt. 1,15 war der Wert *ohne* Kante, und der war zu wenig;
        die Linie selbst muss deutlich darüber liegen.
        """
        from PySide6.QtGui import QPalette

        from mailburg import farben as grundfarben
        from mailburg.ui import farben

        palette = self.app.palette()
        gemessen = grundfarben.kontrast(
            farben.kante(), palette.color(QPalette.Base).name()
        )

        self.assertGreater(
            gemessen, 1.5, "Die Trennlinie geht im Inhalt unter"
        )


if __name__ == "__main__":
    unittest.main()
