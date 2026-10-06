"""Was über der Trefferliste steht.

**Der Anlass kommt aus dem Betrieb (06.10.2026).** In MailStore sieht
man beim Öffnen, wie viele Mails im Archiv liegen; in MailBurg stand
dort nach einer Suche nur die Trefferzahl. Wer sehen will, dass sein
Archiv wächst, musste das Suchfeld leeren.

**Die Zahl im Archiv ist die ganze, und das ist eine Festlegung.**
Überall sonst gilt: Was jemand nicht sehen darf, taucht in keiner Zahl
auf. Hier nicht – Stephans Vorgabe vom 2026-10-06: *Die Gesamtzahl
aller Mails dürfen alle sehen, auch wenn sie nur auf einen kleinen Teil
zugreifen können.*

Der Grund trägt: Sie sagt, wie groß das Archiv ist und dass es wächst.
Wer weiß, dass 70.000 Mails darin liegen, weiß deshalb über keine
einzige etwas. Die **Trefferzahl** daneben bleibt eingeschränkt – sie
handelt vom Inhalt.
"""

from __future__ import annotations

import unittest

from mailburg.server.seiten import ergebniszeile


class ErgebniszeileTest(unittest.TestCase):
    def test_ohne_suche_steht_der_bestand_da(self):
        """Der Fall, um den es Stephan ging."""
        self.assertEqual(ergebniszeile(0, "", 70264), "70.264 Mails im Archiv.")

    def test_nach_einer_suche_beides(self):
        """»1.234 von 70.264« sagt mehr als »1.234«."""
        text = ergebniszeile(1234, "rechnung", 70264)

        self.assertIn("1.234 Treffer", text)
        self.assertIn("70.264 Mails im Archiv", text)

    def test_ohne_suchbegriff_wird_die_zahl_nicht_doppelt_genannt(self):
        """Treffer und Bestand sind dann dasselbe – zweimal gelesen
        sieht das aus wie ein Fehler."""
        text = ergebniszeile(70264, "", 70264)

        self.assertEqual(text.count("70.264"), 1)

    def test_ohne_treffer_bleibt_der_bestand_sichtbar(self):
        """Gerade dann ist er nützlich: Das Archiv ist nicht leer, die
        Suche war nur zu eng."""
        text = ergebniszeile(0, "nixdawas", 70264)

        self.assertIn("nichts gefunden", text)
        self.assertIn("70.264", text)

    def test_ein_leeres_archiv_erfindet_keine_zahl(self):
        self.assertEqual(ergebniszeile(0, "", 0), "")

    def test_wer_wenig_sehen_darf_sieht_trotzdem_den_ganzen_bestand(self):
        """**Die Festlegung, um die es geht.**

        Ein Zugang mit einem einzigen Postfach findet zwölf Treffer –
        und sieht trotzdem, dass das Archiv 70.264 Mails umfasst. Das
        ist gewollt: Die Zahl handelt vom Bestand, nicht von seinem
        Inhalt.
        """
        text = ergebniszeile(12, "rechnung", 70264)

        self.assertIn("12 Treffer", text)
        self.assertIn("70.264 Mails im Archiv", text)


class SichtTest(unittest.TestCase):
    """Die Grenze verläuft zwischen Bestand und Inhalt."""

    def test_der_bestand_wird_ohne_sicht_gezaehlt(self):
        """**Eine Festlegung, kein Versehen.** Wer das ändert, ändert
        eine Entscheidung – deshalb steht sie hier fest."""
        import inspect

        from mailburg.server import lesen

        quelle = inspect.getsource(lesen.routen)

        self.assertIn('im_archiv=archiv.index.count("")', quelle)

    def test_die_treffer_dagegen_mit_sicht(self):
        """Die Trefferzahl handelt vom Inhalt und bleibt eingeschränkt –
        sonst verriete sie, dass es Post gibt, die verborgen ist."""
        import inspect

        from mailburg.server import lesen

        quelle = inspect.getsource(lesen.routen)

        self.assertIn("sicht=blick", quelle)
