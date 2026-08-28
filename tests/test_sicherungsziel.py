"""Ob MailBurg merkt, dass das Sicherungsziel fehlt.

**Der Fall, um den es geht.** Eine Sicherung schreibt nach
``/mnt/…/Storage-Box/``. Ist das ein Einhängepunkt und die Platte hängt
nicht, existiert der Ordner trotzdem – leer, auf der Systemplatte.
``mkdir -p`` legt den Rest an, das Packen läuft durch, und am Ende steht
eine Sicherung an einem Ort, den niemand gemeint hat. Auf derselben
Platte wie das Archiv womöglich, also genau dort, wo sie im Ernstfall
mit verlorengeht.

Auffallen würde das erst, wenn man die Sicherung braucht. Bis dahin
läuft der Zeitplan Monat für Monat und meldet Erfolg. Am 2026-08-28
nachgestellt: MailBurg legte den Ordner an, schrieb hinein und gab 0
zurück – ohne ein Wort.
"""

from __future__ import annotations

import pathlib
import tempfile
import unittest

from mailburg.core import sicherung
from mailburg.core.archive import Archive


class ZielpruefungTest(unittest.TestCase):
    def setUp(self) -> None:
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.wurzel = pathlib.Path(self.ordner.name)

        self.archiv = self.wurzel / "Archiv"
        Archive.create(self.archiv).close()
        self.ziel = self.wurzel / "Sicherungen"

    def test_leerer_ordner_gilt_als_fehlende_platte(self) -> None:
        """Der Kernfall: Einhängepunkt da, Datenträger nicht."""
        self.ziel.mkdir()
        darf, grund = sicherung.ziel_pruefen(self.archiv, self.ziel)

        self.assertFalse(darf)
        self.assertIn("nicht", grund.lower())

    def test_fehlender_ordner_ebenso(self) -> None:
        darf, _grund = sicherung.ziel_pruefen(self.archiv, self.ziel)
        self.assertFalse(darf)

    def test_von_hand_darf_angelegt_werden(self) -> None:
        """Wer danebensteht, richtet gerade erst ein."""
        darf, grund = sicherung.ziel_pruefen(
            self.archiv, self.ziel, anlegen=True
        )

        self.assertTrue(darf, grund)
        self.assertTrue((self.ziel / sicherung.MARKE).is_file())

    def test_danach_geht_es_auch_im_zeitplan(self) -> None:
        sicherung.marke_setzen(self.ziel)
        darf, grund = sicherung.ziel_pruefen(self.archiv, self.ziel)
        self.assertTrue(darf, grund)

    def test_und_faellt_wieder_auf_wenn_die_platte_verschwindet(self) -> None:
        sicherung.marke_setzen(self.ziel)
        (self.ziel / sicherung.MARKE).unlink()

        darf, _grund = sicherung.ziel_pruefen(self.archiv, self.ziel)
        self.assertFalse(darf)

    def test_gewachsener_bestand_wird_nicht_abgewiesen(self) -> None:
        """Wer dort schon Sicherungen liegen hat, soll weitermachen können.

        Die Prüfung kam erst am 2026-08-28 dazu. Ein Ordner voller
        Sicherungen ohne Marke ist kein Fehler, sondern älter als die
        Regel – die Marke wird nachgetragen.
        """
        self.ziel.mkdir()
        (self.ziel / "archiv-2026-01-01.tar.zst").write_bytes(b"alt")

        darf, grund = sicherung.ziel_pruefen(self.archiv, self.ziel)

        self.assertTrue(darf, grund)
        self.assertTrue((self.ziel / sicherung.MARKE).is_file())

    def test_eine_datei_als_ziel_meint_ihren_ordner(self) -> None:
        sicherung.marke_setzen(self.ziel)
        darf, grund = sicherung.ziel_pruefen(
            self.archiv, self.ziel / "sicherung-2026-08-28.tar.zst"
        )
        self.assertTrue(darf, grund)


class GleichePlatteTest(unittest.TestCase):
    """Eine Sicherung neben dem Original ist keine.

    Der Hinweis stand bisher nur im Text des Einrichtungsfensters –
    »Nicht auf dieselbe Platte wie das Archiv« –, geprüft wurde er nicht.
    """

    def setUp(self) -> None:
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.wurzel = pathlib.Path(self.ordner.name)
        self.archiv = self.wurzel / "Archiv"
        Archive.create(self.archiv).close()

    def test_daneben_faellt_auf(self) -> None:
        self.assertTrue(
            sicherung.gleiche_platte(self.archiv, self.wurzel / "Sicherungen")
        )

    def test_ein_pfad_der_noch_nicht_existiert_zaehlt_den_elternteil(self) -> None:
        """Sonst ließe sich die Prüfung durch einen neuen Ordner aushebeln."""
        self.assertTrue(
            sicherung.gleiche_platte(
                self.archiv, self.wurzel / "gibt" / "es" / "noch" / "nicht"
            )
        )


class BefehlTest(unittest.TestCase):
    """Und dasselbe über die Kommandozeile – dort läuft der Zeitplan."""

    def setUp(self) -> None:
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.wurzel = pathlib.Path(self.ordner.name)
        self.archiv = self.wurzel / "Archiv"
        Archive.create(self.archiv).close()
        self.ziel = self.wurzel / "Sicherungen"

    def _sichern(self, *zusatz: str) -> int:
        from mailburg.__main__ import main

        return main(["sichern", str(self.archiv), str(self.ziel), *zusatz])

    def test_der_zeitplan_bricht_ab_und_meldet_es(self) -> None:
        """Der Rückgabewert entscheidet, ob systemd den Fehlschlag zeigt."""
        self.ziel.mkdir()
        self.assertEqual(self._sichern("--leise"), 1)
        self.assertEqual(list(self.ziel.glob("*.tar*")), [])

    def test_von_hand_legt_an_und_sichert(self) -> None:
        self.assertEqual(self._sichern(), 0)
        self.assertTrue(list(self.ziel.glob("*.tar*")))

    def test_und_danach_laeuft_der_zeitplan(self) -> None:
        self._sichern()
        self.assertEqual(self._sichern("--leise"), 0)


if __name__ == "__main__":
    unittest.main()
