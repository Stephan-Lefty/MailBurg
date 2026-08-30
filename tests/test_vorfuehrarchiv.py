"""Das Archiv zum Vorführen.

Wer MailBurg in einem Video zeigt, darf dabei nicht seine eigene Post
zeigen. Dieses Werkzeug legt dafür ein Archiv mit erfundener Post an –
und die Prüfung, die hier am meisten wiegt, ist nicht, ob es läuft,
sondern **ob wirklich nichts Echtes darin steht**.
"""

from __future__ import annotations

import tempfile
import unittest
from importlib import util
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent


def _werkzeug():
    laden = util.spec_from_file_location(
        "vorfuehrarchiv", WURZEL / "werkzeuge" / "vorfuehrarchiv.py"
    )
    modul = util.module_from_spec(laden)
    laden.loader.exec_module(modul)
    return modul


class ErfundeneDatenTest(unittest.TestCase):
    """Keine echte Adresse, keine echte Domain."""

    def setUp(self):
        self.werkzeug = _werkzeug()

    def test_jede_adresse_endet_auf_example(self):
        """RFC 2606 reserviert diese Endung – sie gehört nie jemandem.

        Stünde in einer Vorführung eine echte Domain, bekäme deren
        Inhaber Post von allen, die das Beispiel nachspielen.
        """
        adressen = [eintrag[1] for eintrag in self.werkzeug.POST]
        adressen += [eintrag[1] for eintrag in self.werkzeug.ZWEITE_POST]
        adressen += [self.werkzeug.ICH, self.werkzeug.ZWEITES]

        for adresse in adressen:
            with self.subTest(adresse=adresse):
                self.assertTrue(
                    adresse.endswith(".example"),
                    f"{adresse} ist keine reservierte Beispieladresse",
                )

    def test_die_post_reicht_ueber_mehrere_jahre(self):
        """Sonst findet »jahr:« nichts und die Vorführung fällt in sich zusammen."""
        alter = [eintrag[4] for eintrag in self.werkzeug.POST]

        self.assertTrue(any(t < 90 for t in alter), "nichts Frisches")
        self.assertTrue(any(365 < t < 700 for t in alter), "nichts aus dem Vorjahr")
        self.assertTrue(any(t > 700 for t in alter), "nichts Älteres")

    def test_mehrere_ordner_und_zwei_postfaecher(self):
        """Ein Postfachbaum mit einem Eintrag zeigt nicht, wozu er da ist."""
        ordner = {eintrag[2] for eintrag in self.werkzeug.POST}

        self.assertGreaterEqual(len(ordner), 4)
        self.assertNotEqual(self.werkzeug.ICH, self.werkzeug.ZWEITES)


class AngelegtesArchivTest(unittest.TestCase):
    """Was herauskommt, muss sich auch durchsuchen lassen."""

    def setUp(self):
        self.werkzeug = _werkzeug()

    def test_die_suche_findet_etwas(self):
        """Der eigentliche Zweck – und der Grund für das ``with``.

        Journal und Index schreiben ihren letzten Stand erst beim
        Schließen weg. Ohne das läge die Post zwar auf der Platte, die
        Suche fände aber nichts: genau das, was vorgeführt werden soll.
        """
        from mailburg.core.archive import Archive

        with tempfile.TemporaryDirectory() as ordner:
            ziel = Path(ordner) / "Vorfuehrung"
            anzahl = self.werkzeug.anlegen(ziel)

            with Archive.open(ziel) as archiv:
                self.assertEqual(archiv.index.count(), anzahl)
                self.assertTrue(archiv.index.search("rechnung"))
                self.assertTrue(archiv.index.search("von:kraemer"))

    def test_geschaeftlich_ist_die_vorgabe(self):
        """Nur dort gibt es Journal, Einstufung, Fristen und Auskunft."""
        from mailburg.core.archive import Archive

        with tempfile.TemporaryDirectory() as ordner:
            ziel = Path(ordner) / "Vorfuehrung"
            self.werkzeug.anlegen(ziel)

            with Archive.open(ziel) as archiv:
                self.assertTrue(archiv.mode.is_business)

    def test_privat_auf_wunsch(self):
        from mailburg.core.archive import Archive

        with tempfile.TemporaryDirectory() as ordner:
            ziel = Path(ordner) / "Vorfuehrung"
            self.werkzeug.anlegen(ziel, geschaeftlich=False)

            with Archive.open(ziel) as archiv:
                self.assertFalse(archiv.mode.is_business)


class LoeschschutzTest(unittest.TestCase):
    """``--neu`` löscht einen Ordner. Das darf nicht der falsche sein."""

    def setUp(self):
        self.werkzeug = _werkzeug()

    def test_fremder_ordner_bleibt_stehen(self):
        """Ein vertipptes Ziel darf kein fremdes Archiv mitnehmen."""
        with tempfile.TemporaryDirectory() as ordner:
            fremd = Path(ordner) / "Wichtig"
            fremd.mkdir()
            (fremd / "unterlagen.txt").write_text("nicht weg", encoding="utf-8")

            code = self.werkzeug.main([str(fremd), "--neu"])

            self.assertEqual(code, 1)
            self.assertTrue((fremd / "unterlagen.txt").is_file())

    def test_ohne_neu_wird_nichts_angefasst(self):
        with tempfile.TemporaryDirectory() as ordner:
            code = self.werkzeug.main([ordner])

            self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
