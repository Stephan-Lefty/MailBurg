"""Prüfungen am Installationsskript.

Was install.sh anlegt, sieht der Anwender als Erstes – und es lässt sich
schlecht nachträglich richtigstellen: Ein Menüeintrag, der einmal falsch
einsortiert wurde, bleibt es bei jedem, der nicht neu installiert.
"""

from __future__ import annotations

import pathlib
import unittest


class MenueeintragTest(unittest.TestCase):
    """Der Menüeintrag darf nur an einer Stelle auftauchen."""

    def setUp(self):
        self.skript = (
            pathlib.Path(__file__).resolve().parent.parent / "install.sh"
        ).read_text(encoding="utf-8")

    def test_nur_eine_hauptkategorie(self):
        # Office, Utility, Network, Settings, System, Development, Game,
        # Graphics, AudioVideo und Education sind Hauptkategorien. Stehen
        # zwei davon nebeneinander, legt das Menü zwei Einträge an - genau
        # das ist passiert: MailBurg stand unter Büroprogrammen *und*
        # unter Dienstprogrammen.
        haupt = {
            "AudioVideo", "Audio", "Video", "Development", "Education",
            "Game", "Graphics", "Network", "Office", "Science", "Settings",
            "System", "Utility",
        }
        zeile = next(z for z in self.skript.splitlines()
                     if z.startswith("Categories="))
        gesetzt = [t for t in zeile.split("=", 1)[1].split(";") if t]

        self.assertEqual(
            [t for t in gesetzt if t in haupt], ["Office"],
            f"genau eine Hauptkategorie, gefunden: {gesetzt}",
        )
