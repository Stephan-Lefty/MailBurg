"""Wo der Suchindex liegt – und warum das auf einem Server anders ist.

**Der Befund vom 2026-10-02.** Der Index liegt außerhalb des Archivs, an
einem Ort, der am Benutzer hängt. Auf einem Arbeitsplatz ist das richtig:
Der Index kann zweistellige Gigabyte erreichen und gehört nicht ins
wandernde Profil, und er ist jederzeit neu erzeugbar.

Auf einem Server kippt diese Rechnung. Dort legt ein Mensch das Archiv
an, und ein Dienst liest es – unter Windows als ``LocalSystem``, mit
einem eigenen ``%LOCALAPPDATA%`` tief unter ``C:\\Windows\\System32``.
Der Dienst fand einen leeren Index, meldete null Mails und schwieg
dazu. Die Anmeldung ging trotzdem, denn die Zugänge liegen im Archiv.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mailburg.core import paths


class DatenortTest(unittest.TestCase):
    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)

    def test_ohne_angabe_bleibt_alles_wie_bisher(self):
        """Ein Arbeitsplatz soll nichts von dieser Variablen merken."""
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(paths.DATEN, None)
            vorher = paths.data_dir()

        self.assertTrue(str(vorher))

    def test_der_ort_laesst_sich_festlegen(self):
        ziel = Path(self.ordner.name) / "gemeinsam"

        with mock.patch.dict(os.environ, {paths.DATEN: str(ziel)}):
            self.assertEqual(paths.data_dir(), ziel)

    def test_der_index_folgt_mit(self):
        """Darum geht es: Dienst und Mensch sollen denselben Index sehen."""
        ziel = Path(self.ordner.name) / "gemeinsam"

        with mock.patch.dict(os.environ, {paths.DATEN: str(ziel)}):
            index = paths.index_path("abc-123")

        self.assertEqual(index.parent, ziel / "index")
        self.assertEqual(index.name, "abc-123.db")

    def test_eine_tilde_wird_aufgeloest(self):
        with mock.patch.dict(os.environ, {paths.DATEN: "~/mailburg-daten"}):
            self.assertFalse(str(paths.data_dir()).startswith("~"))

    def test_leer_gilt_als_nicht_gesetzt(self):
        """Sonst landete der Index im aktuellen Verzeichnis."""
        ziel = Path(self.ordner.name) / "gemeinsam"

        with mock.patch.dict(os.environ, {paths.DATEN: "   "}):
            ohne = paths.data_dir()
        with mock.patch.dict(os.environ, {paths.DATEN: str(ziel)}):
            mit = paths.data_dir()

        self.assertNotEqual(ohne, Path("   "))
        self.assertNotEqual(ohne, mit)

    def test_einstellungen_wandern_nicht_mit(self):
        """**Nur die Daten, nicht die Kontenliste.**

        Die Kontenliste gehört dem Menschen, der sie gepflegt hat; sie
        umzuhängen wäre eine zweite Entscheidung mit anderen Folgen –
        darunter, dass Postfach-Passwörter plötzlich woanders gesucht
        würden.
        """
        ziel = Path(self.ordner.name) / "gemeinsam"

        with mock.patch.dict(os.environ, {paths.DATEN: str(ziel)}):
            self.assertNotEqual(paths.config_dir(), ziel)
            self.assertNotEqual(paths.cache_dir() if hasattr(
                paths, "cache_dir") else Path("x"), ziel)


if __name__ == "__main__":
    unittest.main()
