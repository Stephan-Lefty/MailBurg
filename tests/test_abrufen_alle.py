"""»Einmal alles nachholen« – der Abruf über jedes bekannte Archiv.

Entstanden am 22.09.2026 aus einer Frage Stephans: Nach einem Fehler,
der Post überspringen ließ, sollten alle Anwender einmal vollständig
abrufen. Drei Archive hießen dafür dreimal einen Pfad heraussuchen, den
man auswendig nicht kennt.

**Was hier geprüft wird, ist vor allem das Verhalten im Zweifel:** dass
ein klemmendes Archiv die übrigen nicht kostet, und dass Übersprungenes
gesagt wird. Ein Lauf, der »fertig« meldet und dabei eine abgezogene
Platte verschwiegen hat, wäre schlimmer als einer, der abbricht.
"""

from __future__ import annotations

import argparse
import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from mailburg.__main__ import _abrufen_ueber_alle, cmd_abrufen


def _argumente(**abweichend) -> argparse.Namespace:
    werte = {
        "archiv": None, "alle": False, "konto": None, "ordner": None,
        "voll": False, "ohne_anhangstext": False, "leise": False,
        "ohne_texterkennung": False, "erkennungsbudget": 0,
    }
    werte.update(abweichend)
    return argparse.Namespace(**werte)


class OhneAngabe(unittest.TestCase):
    def test_ohne_pfad_und_ohne_alle_kommt_eine_ansage(self) -> None:
        """Und keine Fehlermeldung, die nach einem Programmfehler aussieht."""
        fehler = io.StringIO()
        with redirect_stderr(fehler):
            rueckgabe = cmd_abrufen(_argumente())
        self.assertEqual(rueckgabe, 2)
        self.assertIn("--alle", fehler.getvalue())


class UeberAlle(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.basis = Path(self._tmp.name)

    def _archiv(self, name: str) -> Path:
        ordner = self.basis / name
        ordner.mkdir()
        (ordner / "archive.json").write_text("{}", encoding="utf-8")
        return ordner

    def _laufen_lassen(self, pfade, einzelergebnis=0):
        """Führt den Lauf aus, ohne wirklich abzurufen."""
        besucht = []

        def statt_abruf(args):
            besucht.append(args.archiv)
            return einzelergebnis(args) if callable(einzelergebnis) else einzelergebnis

        ausgabe, fehler = io.StringIO(), io.StringIO()
        with mock.patch(
            "mailburg.core.einstellungen.zuletzt_benutzte_pfade",
            return_value=[str(p) for p in pfade],
        ), mock.patch("mailburg.__main__._abrufen_eines", statt_abruf), \
                redirect_stdout(ausgabe), redirect_stderr(fehler):
            rueckgabe = _abrufen_ueber_alle(_argumente(alle=True, voll=True))
        return rueckgabe, besucht, ausgabe.getvalue(), fehler.getvalue()

    def test_jedes_bekannte_archiv_kommt_dran(self) -> None:
        pfade = [self._archiv("Eins"), self._archiv("Zwei"), self._archiv("Drei")]
        rueckgabe, besucht, ausgabe, _ = self._laufen_lassen(pfade)

        self.assertEqual(rueckgabe, 0)
        self.assertEqual(besucht, [str(p) for p in pfade])
        self.assertIn("Alle 3 Archive sind durch", ausgabe)

    def test_die_optionen_wandern_mit(self) -> None:
        """Sonst liefe --voll nur beim ersten Archiv."""
        pfade = [self._archiv("Eins"), self._archiv("Zwei")]
        gesehen = []

        def merken(args):
            gesehen.append(args.voll)
            return 0

        self._laufen_lassen(pfade, einzelergebnis=merken)
        self.assertEqual(gesehen, [True, True])

    def test_ein_verschwundenes_archiv_wird_genannt(self) -> None:
        """**Was ausgelassen wird, muss gesagt werden.**

        Eine abgezogene Platte sähe sonst aus wie ein Archiv, in dem
        nichts Neues war.
        """
        da = self._archiv("Vorhanden")
        weg = self.basis / "AufDerUsbPlatte"
        rueckgabe, besucht, ausgabe, fehler = self._laufen_lassen([da, weg])

        self.assertEqual(besucht, [str(da)])
        self.assertIn("übersprungen", fehler)
        self.assertIn("AufDerUsbPlatte", fehler)
        self.assertEqual(rueckgabe, 0)

    def test_ein_klemmendes_archiv_kostet_die_uebrigen_nichts(self) -> None:
        """Ein gesperrtes oder verschlüsseltes darf den Lauf nicht beenden."""
        pfade = [self._archiv("Eins"), self._archiv("Zwei"), self._archiv("Drei")]

        def zweites_scheitert(args):
            if args.archiv.endswith("Zwei"):
                raise OSError("Platte weg")
            return 0

        rueckgabe, besucht, _ausgabe, fehler = self._laufen_lassen(
            pfade, einzelergebnis=zweites_scheitert
        )

        self.assertEqual(besucht, [str(p) for p in pfade], "alle drei versucht")
        self.assertIn("Platte weg", fehler)
        self.assertEqual(rueckgabe, 1, "und der Lauf meldet, dass etwas fehlt")

    def test_ohne_bekanntes_archiv_wird_das_erklaert(self) -> None:
        """Auf einem frischen Rechner gibt es die Liste noch nicht."""
        rueckgabe, besucht, _ausgabe, fehler = self._laufen_lassen([])

        self.assertEqual(rueckgabe, 2)
        self.assertEqual(besucht, [])
        self.assertIn("noch keines", fehler)


if __name__ == "__main__":
    unittest.main()
