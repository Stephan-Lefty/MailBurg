"""Wie die Suche mit Schreibweisen umgeht.

Groß- und Kleinschreibung ist der Suche gleichgültig, auch bei
Umlauten – das erledigt der Tokenizer des Index. Zwei Fälle erledigt er
aber nicht, und beide treffen ausgerechnet Deutsch: das ß und die
Umschreibung mit e. Darum geht es hier.
"""

from __future__ import annotations

import pathlib
import unittest

class SchreibweisenTest(unittest.TestCase):
    """ß und ss, Umlaut und Umschreibung meinen dasselbe.

    Der Index legt Wörter ohne Umlautpunkte ab, deshalb fand »muller«
    schon immer »Müller«. Zwei Fälle deckte das nicht ab, und beide
    treffen ausgerechnet Deutsch:

    * Das **ß** blieb stehen. »Bahnhofstrasse« fand »Bahnhofstraße«
      nicht – und in der Schweiz gibt es überhaupt kein ß. Bei einem
      Programm mit Aufbewahrungsfristen für DE, AT *und* CH ist das
      keine Kleinigkeit.
    * Die **Umschreibung mit e**, »mueller« statt »müller«. So schreibt
      man in Mailadressen und Dateinamen.

    Am 2026-08-28 nachgemessen, nachdem Stephan fragte, wie es die Suche
    mit Groß- und Kleinschreibung hält.
    """

    def test_die_eingabe_steht_immer_vorn(self):
        from mailburg.search.query import schreibweisen

        self.assertEqual(schreibweisen("Rechnung")[0], "Rechnung")

    def test_ss_und_scharfes_s(self):
        from mailburg.search.query import schreibweisen

        self.assertIn("straße", schreibweisen("strasse"))
        self.assertIn("strasse", schreibweisen("straße"))

    def test_die_umschreibung_mit_e(self):
        from mailburg.search.query import schreibweisen

        self.assertIn("müller", schreibweisen("mueller"))
        self.assertIn("schäfer", schreibweisen("schaefer"))
        self.assertIn("röder", schreibweisen("roeder"))

    def test_mehrere_stellen_im_selben_wort(self):
        """»Strassenmueller« braucht beide Ersetzungen zugleich."""
        from mailburg.search.query import schreibweisen

        self.assertIn("straßenmüller", schreibweisen("strassenmueller"))

    def test_ohne_besonderheit_bleibt_es_bei_einer(self):
        """Sonst bläht sich jede gewöhnliche Suche unnötig auf."""
        from mailburg.search.query import schreibweisen

        self.assertEqual(schreibweisen("rechnung"), ["rechnung"])

    def test_es_ufert_nicht_aus(self):
        """Zwei hoch n Varianten wären langsamer als die Suche selbst."""
        from mailburg.search.query import _HOECHSTENS, schreibweisen

        viele = schreibweisen("massstrassenuebergaenge")
        self.assertLessEqual(len(viele), _HOECHSTENS)

    def test_unsinn_schadet_nicht(self):
        """Aus »Steuer« wird auch »Steür« – das findet eben nichts.

        Die Alternative wäre ein Wörterbuch, und das wüsste bei
        Eigennamen auch nicht weiter.
        """
        from mailburg.search.query import schreibweisen

        varianten = schreibweisen("steuer")
        self.assertIn("steuer", varianten)


class SchreibweisenImArchivTest(unittest.TestCase):
    """Und dasselbe am echten Index, nicht am Nachbau."""

    def setUp(self):
        import tempfile

        from mailburg.core.archive import Archive

        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.pfad = pathlib.Path(self.ordner.name) / "Probe"
        Archive.create(self.pfad).close()

        roh = (
            "From: Bau GmbH <post@example.org>\r\n"
            "To: empfang@example.net\r\n"
            "Subject: Rechnung Bahnhofstraße 7\r\n"
            "Date: Wed, 26 Aug 2026 10:00:00 +0200\r\n"
            "Message-ID: <strasse@example.org>\r\n"
            "\r\n"
            "Die Rückvergütung für Müller ist überwiesen.\r\n"
        ).encode()

        with Archive.open(self.pfad) as archiv:
            archiv.add(roh, account="probe", folder="INBOX")

    def _suchen(self, ausdruck: str) -> int:
        from mailburg.core.archive import Archive

        with Archive.open(self.pfad) as archiv:
            return len(archiv.index.search(ausdruck))

    def test_strasse_findet_strasse_mit_scharfem_s(self):
        self.assertEqual(self._suchen("bahnhofstrasse"), 1)

    def test_und_umgekehrt(self):
        self.assertEqual(self._suchen("bahnhofstraße"), 1)

    def test_gross_und_klein_ist_gleich(self):
        for schreibweise in ("MÜLLER", "müller", "Müller", "muller"):
            with self.subTest(wort=schreibweise):
                self.assertEqual(self._suchen(schreibweise), 1)

    def test_auch_im_betreff_gesucht(self):
        self.assertEqual(self._suchen("betreff:bahnhofstrasse"), 1)
