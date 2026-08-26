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


class AnleitungenTest(unittest.TestCase):
    """Was verlinkt ist, muss es auch geben."""

    def setUp(self):
        self.wurzel = pathlib.Path(__file__).resolve().parent.parent

    def test_keine_verweise_ins_leere(self):
        # docs/zeitsteuerung.md verwies monatelang auf eine Anleitung, die
        # es nicht gab. Ein toter Verweis ist ärgerlicher als eine
        # fehlende Erwähnung: Er verspricht Hilfe und liefert einen
        # Fehler.
        import re

        for datei in (self.wurzel / "docs").glob("*.md"):
            text = datei.read_text(encoding="utf-8")
            for ziel in re.findall(r"\]\((?!https?:)([^)#]+\.md)[^)]*\)", text):
                with self.subTest(datei=datei.name, ziel=ziel):
                    self.assertTrue(
                        (datei.parent / ziel).resolve().exists(),
                        f"{datei.name} verweist auf {ziel}, das es nicht gibt",
                    )

    def test_jede_anleitung_steht_im_verzeichnis(self):
        verzeichnis = (self.wurzel / "docs" / "README.md").read_text(
            encoding="utf-8")

        for datei in (self.wurzel / "docs").glob("*.md"):
            if datei.name == "README.md":
                continue
            with self.subTest(datei=datei.name):
                self.assertIn(datei.name, verzeichnis)
