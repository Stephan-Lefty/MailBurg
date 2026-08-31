"""Zugänge auf der Kommandozeile.

**Auf einem Server gibt es keine Oberfläche.** Ohne diesen Weg käme
man dort an sein eigenes Archiv nicht heran: Die Rechteverwaltung säße
in einem Fenster, das sich nicht öffnen lässt.

Am 2026-08-31 nachgebaut – beim ersten Ausprobieren des Servers fiel
auf, dass es ihn noch nicht gab.
"""

from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from mailburg.__main__ import main
from mailburg.core.archive import Archive, Mode


class ZugaengeCliTest(unittest.TestCase):
    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.wo = Path(self.ordner.name) / "Archiv"
        with Archive.create(self.wo, name="P", mode=Mode.GESCHAEFTLICH) as a:
            a.add(
                b"From: a@example.org\r\nSubject: Test\r\n\r\nText\r\n",
                account="buchhaltung", folder="INBOX",
            )

    def _ruf(self, *args, passwort: str = "ein-langes-passwort"):
        """Führt einen Befehl aus und gibt Rückgabewert und Ausgabe zurück."""
        aus, fehler = io.StringIO(), io.StringIO()
        with mock.patch("getpass.getpass", return_value=passwort):
            with redirect_stdout(aus), redirect_stderr(fehler):
                code = main(["zugaenge", str(self.wo), *args])
        return code, aus.getvalue() + fehler.getvalue()

    def test_ein_leeres_archiv_sagt_wie_es_geht(self):
        code, text = self._ruf("liste")

        self.assertEqual(code, 0)
        self.assertIn("kein Zugang", text)
        self.assertIn("hinzufuegen", text)

    def test_anlegen_und_auflisten(self):
        self._ruf("hinzufuegen", "chef", "--alle", "--verwalter")
        code, text = self._ruf("liste")

        self.assertEqual(code, 0)
        self.assertIn("chef", text)
        self.assertIn("verwaltet Zugänge", text)
        self.assertIn("sieht alle Postfächer", text)

    def test_wer_nichts_sieht_bekommt_es_gesagt(self):
        """Derselbe Hinweis wie im Dialog – der häufigste Fehler."""
        code, text = self._ruf("hinzufuegen", "neu")

        self.assertEqual(code, 0)
        self.assertIn("sieht noch nichts", text)

        _, liste = self._ruf("liste")
        self.assertIn("sieht nichts", liste)

    def test_ein_zu_kurzes_passwort_wird_abgewiesen(self):
        code, text = self._ruf("hinzufuegen", "kurz", passwort="abc")

        self.assertEqual(code, 1)
        self.assertIn("zu kurz", text)

    def test_ein_unzulaessiger_name(self):
        # Ohne führenden Strich: Den hielte argparse für eine Option,
        # und der Test prüfte dann argparse statt MailBurg.
        code, _ = self._ruf("hinzufuegen", "Anna Feldmann")

        self.assertEqual(code, 1)

    def test_denselben_namen_zweimal(self):
        self._ruf("hinzufuegen", "anna")
        code, _ = self._ruf("hinzufuegen", "anna")

        self.assertEqual(code, 1)

    def test_rechte_aendern(self):
        self._ruf("hinzufuegen", "anna")
        code, text = self._ruf("rechte", "anna", "--nur", "buchhaltung")

        self.assertEqual(code, 0)
        self.assertIn("buchhaltung", text)

        with Archive.open(self.wo) as archiv:
            anna = archiv.benutzer.finden("anna")
            self.assertTrue(anna.darf_sehen("buchhaltung"))
            self.assertFalse(anna.darf_sehen("chefsache"))

    def test_stilllegen_und_zulassen(self):
        self._ruf("hinzufuegen", "anna")

        self._ruf("stilllegen", "anna")
        with Archive.open(self.wo) as archiv:
            self.assertFalse(archiv.benutzer.finden("anna").aktiv)

        self._ruf("zulassen", "anna")
        with Archive.open(self.wo) as archiv:
            self.assertTrue(archiv.benutzer.finden("anna").aktiv)

    def test_ein_neues_passwort(self):
        self._ruf("hinzufuegen", "anna")
        code, _ = self._ruf("passwort", "anna", passwort="das-zweite-lange")

        self.assertEqual(code, 0)
        with Archive.open(self.wo) as archiv:
            self.assertIsNotNone(
                archiv.benutzer.anmelden("anna", "das-zweite-lange")
            )

    def test_ein_unbekannter_name(self):
        code, text = self._ruf("rechte", "niemand", "--alle")

        self.assertEqual(code, 1)
        self.assertIn("gibt es nicht", text)

    def test_der_letzte_verwalter_kann_sich_nicht_entrechten(self):
        """Dieselbe Regel wie im Dialog – sie sitzt im Kern.

        Gerade hier zählt sie: Wer sich am Server aussperrt, hat keine
        Oberfläche mehr, über die er es zurücknehmen könnte.
        """
        self._ruf("hinzufuegen", "chef", "--alle", "--verwalter")

        code, text = self._ruf("rechte", "chef", "--kein-verwalter")

        self.assertEqual(code, 1)
        self.assertIn("niemanden mehr", text)

        with Archive.open(self.wo) as archiv:
            self.assertTrue(archiv.benutzer.finden("chef").verwalter)

    def test_auch_nicht_stilllegen(self):
        self._ruf("hinzufuegen", "chef", "--alle", "--verwalter")

        code, _ = self._ruf("stilllegen", "chef")

        self.assertEqual(code, 1)
        with Archive.open(self.wo) as archiv:
            self.assertTrue(archiv.benutzer.finden("chef").aktiv)

    def test_ein_fehlendes_passwort_faellt_in_der_liste_auf(self):
        """Ein Zugang ohne Passwort sieht aus wie ein fertiger."""
        with Archive.open(self.wo) as archiv:
            from mailburg.core.benutzer import Benutzer

            liste = archiv.benutzer
            liste.hinzufuegen(Benutzer("ohne"))
            archiv.benutzer_setzen(liste)

        _, text = self._ruf("liste")
        self.assertIn("KEIN PASSWORT", text)


class PasswortAbfrageTest(unittest.TestCase):
    def test_das_passwort_steht_nie_in_den_argumenten(self):
        """Sonst stünde es in der Prozessliste und im Shell-Verlauf."""
        from mailburg.__main__ import cmd_zugaenge

        import inspect

        quelle = inspect.getsource(cmd_zugaenge)
        self.assertIn("_passwort_erfragen", quelle)
        self.assertNotIn("args.passwort", quelle)


if __name__ == "__main__":
    unittest.main()
