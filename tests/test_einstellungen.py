"""Was sich MailBurg von Sitzung zu Sitzung merkt.

Bis zum 2026-08-31 lag das in ``ui/app.py`` und wurde von dort aus dem
Kern heraus geholt. Jetzt liegt es im Kern – und muss dort ohne jedes
Frontend auskommen.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mailburg.core import einstellungen


class OhneOberflaecheTest(unittest.TestCase):
    """Der Grund für den Umzug: Ein Dienst hat keine Oberfläche."""

    def test_das_modul_kennt_kein_qt_und_keine_ui(self):
        import ast

        quelle = Path(einstellungen.__file__).read_text(encoding="utf-8")
        eingelesen = {
            teil.name
            for knoten in ast.walk(ast.parse(quelle))
            if isinstance(knoten, ast.Import)
            for teil in knoten.names
        } | {
            knoten.module
            for knoten in ast.walk(ast.parse(quelle))
            if isinstance(knoten, ast.ImportFrom) and knoten.module
        }

        for verboten in ("PySide6", "mailburg.ui"):
            with self.subTest(modul=verboten):
                self.assertFalse(
                    any(m.startswith(verboten) for m in eingelesen),
                    f"core/einstellungen.py lädt {verboten}",
                )


class MerkenTest(unittest.TestCase):
    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        umgebung = mock.patch.dict(
            os.environ, {"XDG_CONFIG_HOME": self.ordner.name}
        )
        umgebung.start()
        self.addCleanup(umgebung.stop)

    def _archiv(self, name: str) -> Path:
        wo = Path(self.ordner.name) / name
        wo.mkdir()
        (wo / "archive.json").write_text("{}", encoding="utf-8")
        return wo

    def test_ohne_datei_ist_nichts_gemerkt(self):
        self.assertEqual(einstellungen.gemerktes(), {})
        self.assertIsNone(einstellungen.zuletzt_gemerkt())
        self.assertEqual(einstellungen.zuletzt_benutzte(), [])

    def test_ein_eintrag_loescht_die_uebrigen_nicht(self):
        """Sonst löschte das Merken des Archivs die Fenstergröße."""
        einstellungen.merken_unter("breite", 640)
        einstellungen.merken_unter("archiv", "/irgendwo")

        stand = einstellungen.gemerktes()
        self.assertEqual(stand["breite"], 640)
        self.assertEqual(stand["archiv"], "/irgendwo")

    def test_kaputte_datei_wirft_nicht(self):
        """Eine halb geschriebene Datei darf den Start nicht verhindern."""
        einstellungen._datei().write_text("{kein json", encoding="utf-8")

        self.assertEqual(einstellungen.gemerktes(), {})

    def test_eine_liste_statt_eines_woerterbuchs_wirft_nicht(self):
        einstellungen._datei().write_text("[1, 2, 3]", encoding="utf-8")

        self.assertEqual(einstellungen.gemerktes(), {})

    def test_das_zuletzt_geoeffnete_muss_es_noch_geben(self):
        """Eine externe Platte kann abgezogen sein."""
        wo = self._archiv("Archiv")
        einstellungen.merken(wo)
        self.assertEqual(einstellungen.zuletzt_gemerkt(), wo)

        (wo / "archive.json").unlink()
        self.assertIsNone(einstellungen.zuletzt_gemerkt())

    def test_die_zuletzt_benutzten_stehen_vorn_und_nur_einmal(self):
        erst, dann = self._archiv("Erst"), self._archiv("Dann")

        einstellungen.merken(erst)
        einstellungen.merken(dann)
        einstellungen.merken(erst)

        self.assertEqual(
            [p.name for p in einstellungen.zuletzt_benutzte()], ["Erst", "Dann"]
        )

    def test_die_liste_bleibt_kurz(self):
        """Eine Liste, die selbst zur Suche wird, hilft niemandem."""
        for nummer in range(einstellungen.ZULETZT + 3):
            einstellungen.merken(self._archiv(f"A{nummer}"))

        gemerkt = json.loads(einstellungen._datei().read_text(encoding="utf-8"))
        self.assertEqual(len(gemerkt["zuletzt"]), einstellungen.ZULETZT)

    def test_ein_nicht_schreibbarer_ort_bricht_nichts_ab(self):
        """Sich etwas nicht merken zu können ist kein Grund, nicht zu starten."""
        with mock.patch.object(
            Path, "write_text", side_effect=OSError("nur lesbar")
        ):
            einstellungen.merken_unter("breite", 800)  # wirft nicht


if __name__ == "__main__":
    unittest.main()
