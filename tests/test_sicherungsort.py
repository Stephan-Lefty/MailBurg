"""Wohin die Sicherungen vorgeschlagen werden.

Der Dialog verlangte einen Ordner, schlug aber keinen vor: Wer das
Häkchen »Das Archiv regelmäßig in eine Datei sichern« setzte und auf
»Übernehmen« ging, bekam »Bitte einen Ordner für die Sicherungen
wählen« – eine Fehlermeldung für einen Zustand, den der Dialog selbst
hergestellt hatte.

Am 2026-08-29 an leeren Feldern auf den Windows-Bildern gesehen.

Der schwierige Teil ist nicht der Vorschlag, sondern die Zurückhaltung:
Eine Sicherung neben dem Original geht mit ihm zusammen verloren. Findet
sich kein Ort auf einer anderen Platte, wird deshalb nichts
vorgeschlagen.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from mailburg.core import orte
from mailburg.core.orte import Ort


def _ort(art: str, pfad: str) -> Ort:
    return Ort(art, Path(pfad) / orte.VORGABENAME, art, 10**11, 10**12)


class SicherungsortTest(unittest.TestCase):
    def _vorsetzen(self, gefunden, geraete):
        """Setzt Ortsliste und Gerätenummern vor.

        ``geraete`` bildet Pfad auf Gerätenummer ab; alles Unbekannte
        liegt auf Gerät 1, also dort, wo hier auch das Archiv liegt.
        Die Patches laufen bis zum Ende des Tests.
        """
        for patch in (
            mock.patch.object(orte, "vorschlagen", lambda: gefunden),
            mock.patch.object(
                orte, "_geraetenummer", lambda p: geraete.get(str(p), 1)
            ),
        ):
            patch.start()
            self.addCleanup(patch.stop)

    def test_die_cloud_kommt_zuerst(self):
        gefunden = [
            _ort("laufwerk", "/mnt/daten"),
            _ort("cloud", "/home/martha/Nextcloud"),
            _ort("extern", "/media/martha/Platte"),
        ]
        geraete = {
            "/mnt/daten": 2,
            "/home/martha/Nextcloud": 3,
            "/media/martha/Platte": 4,
        }
        self._vorsetzen(gefunden, geraete)

        self.assertEqual(
            orte.sicherungsort_vorschlagen("/home/martha/Mailarchiv"),
            Path("/home/martha/Nextcloud") / orte.SICHERUNGSNAME,
        )

    def test_ohne_cloud_die_externe_platte(self):
        gefunden = [
            _ort("laufwerk", "/mnt/daten"),
            _ort("extern", "/media/martha/Platte"),
        ]
        geraete = {"/mnt/daten": 2, "/media/martha/Platte": 4}
        self._vorsetzen(gefunden, geraete)

        self.assertEqual(
            orte.sicherungsort_vorschlagen("/home/martha/Mailarchiv"),
            Path("/media/martha/Platte") / orte.SICHERUNGSNAME,
        )

    def test_nichts_auf_der_platte_des_archivs(self):
        """Der Kern: eine Sicherung neben dem Original ist keine."""
        gefunden = [_ort("cloud", "/home/martha/Nextcloud")]
        # Die Cloud liegt hier auf derselben Platte wie das Archiv –
        # ein Ordner, den ein Cloud-Programm abgleicht, aber eben auf
        # der Systemplatte.
        geraete = {"/home/martha/Nextcloud": 1}
        self._vorsetzen(gefunden, geraete)

        self.assertIsNone(
            orte.sicherungsort_vorschlagen("/home/martha/Mailarchiv")
        )

    def test_lieber_nichts_als_etwas_falsches(self):
        self._vorsetzen([], {})

        self.assertIsNone(orte.sicherungsort_vorschlagen("/beliebig"))

    def test_der_benutzerordner_wird_nie_vorgeschlagen(self):
        """Auch dann nicht, wenn er auf einer anderen Platte läge."""
        gefunden = [_ort("benutzer", "/home/martha")]
        self._vorsetzen(gefunden, {"/home/martha": 9})

        self.assertIsNone(
            orte.sicherungsort_vorschlagen("/mnt/woanders/Mailarchiv")
        )

    def test_eigener_name_fuer_die_sicherungen(self):
        """Nicht »Mailarchiv« – sonst hält man die Stände für das Archiv."""
        self.assertNotEqual(orte.SICHERUNGSNAME, orte.VORGABENAME)


if __name__ == "__main__":
    unittest.main()
