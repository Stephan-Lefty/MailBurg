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


class BeispieldatenTest(unittest.TestCase):
    """In der Anleitung darf keine Adresse stehen, die jemandem gehört."""

    def test_nur_reservierte_endungen(self):
        # Stünde in der Anleitung eines öffentlichen Programms eine echte
        # Domain, bekäme deren Inhaber Post von allen, die das Beispiel
        # ausprobieren. RFC 2606 reserviert .example, .test, .invalid und
        # example.com/net/org genau dafür.
        import re

        skript = (
            pathlib.Path(__file__).resolve().parent.parent
            / "werkzeuge" / "screenshots.py"
        ).read_text(encoding="utf-8")

        erlaubt = (".example", ".test", ".invalid",
                   "example.com", "example.net", "example.org")
        for adresse in re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", skript):
            with self.subTest(adresse=adresse):
                self.assertTrue(
                    adresse.rstrip('">').endswith(erlaubt),
                    f"{adresse} ist keine reservierte Beispieladresse",
                )

    def test_keine_echten_adressen_in_der_doku(self):
        import re

        wurzel = pathlib.Path(__file__).resolve().parent.parent
        erlaubt = (".example", ".test", ".invalid", "example.com",
                   "example.net", "example.org", "@meine-firma", "@ihre-firma")
        for datei in (wurzel / "docs").glob("*.md"):
            text = datei.read_text(encoding="utf-8")
            for adresse in re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", text):
                sauber = adresse.rstrip(">`.,)")
                with self.subTest(datei=datei.name, adresse=sauber):
                    self.assertTrue(
                        sauber.endswith(erlaubt),
                        f"{datei.name}: {sauber} ist keine Beispieladresse",
                    )


class TestlaufHinterlaesstNichtsTest(unittest.TestCase):
    """Die Testsuite darf das Datenverzeichnis des Anwenders nicht füllen."""

    def test_die_tests_schreiben_woandershin(self):
        # Ein Archiv hält seinen Suchindex außerhalb des Archivordners.
        # Für die Tests heißt das: Jedes wegwerfbare Archiv hinterlässt
        # eine Indexdatei im echten Datenverzeichnis, und die räumt
        # niemand weg - der temporäre Ordner wird ja gelöscht.
        #
        # Bemerkt am 2026-08-26: 5.585 Dateien, 1,5 GB, davon zwei echte.
        # Auffallen kann so etwas nicht, solange die Tests grün sind.
        import os

        from mailburg.core import paths

        self.assertTrue(
            str(paths.data_dir()).startswith(os.environ["XDG_DATA_HOME"]),
            "die Tests schreiben ins echte Datenverzeichnis",
        )
        self.assertIn("mailburg-tests-", str(paths.data_dir()))


class WindowsPythonsucheTest(unittest.TestCase):
    """Windows liefert ein ``python.exe``, das kein Python ist.

    Unter »App-Ausführungsaliase« liegt ein Platzhalter, der nur in den
    Microsoft Store führt. ``Get-Command`` findet ihn, also sieht es aus,
    als wäre Python vorhanden; beim Aufruf schreibt er »Python was not
    found« auf die Fehlerausgabe, und PowerShell macht daraus einen
    NativeCommandError samt Zeilennummer aus dem Installationsskript.

    Wer MailBurg zum ersten Mal einrichtet, liest dann einen
    Stapelauszug statt der Auskunft, dass schlicht Python fehlt. Am
    2026-08-27 auf einem frischen Windows 11 aufgefallen – dem ersten
    echten Windows-Lauf überhaupt.
    """

    def setUp(self) -> None:
        self.skript = (
            pathlib.Path(__file__).resolve().parent.parent / "install.ps1"
        ).read_text(encoding="utf-8")

    def test_die_fehlerausgabe_wird_gedaempft(self) -> None:
        """Sonst reicht PowerShell sie als Programmfehler durch."""
        self.assertIn('$ErrorActionPreference = "SilentlyContinue"', self.skript)
        self.assertIn("finally", self.skript)

    def test_der_rueckgabewert_wird_zurueckgesetzt(self) -> None:
        """Ein stehengelassener Fehlercode verfälscht spätere Prüfungen."""
        self.assertIn("$global:LASTEXITCODE = 0", self.skript)

    def test_nur_eine_echte_fassungsnummer_zaehlt(self) -> None:
        """Der Platzhalter schreibt seinen Hinweis auch auf die Ausgabe.

        Ohne diese Prüfung gälte »Python was not found; run without…«
        als Fassungsnummer, und das Skript liefe mit einem Python
        weiter, das es nicht gibt.
        """
        self.assertIn(r"\d+\.\d+", self.skript)

    def test_der_hinweis_zum_nachinstallieren_steht_drin(self) -> None:
        """Wer keine Python-Installation hat, braucht den Befehl dazu."""
        self.assertIn("winget install Python", self.skript)
        self.assertIn("Python 3.11", self.skript)


class FassungsnummerTest(unittest.TestCase):
    """Die Fassung steht an genau einer Stelle.

    So verlangt es CLAUDE.md – und so war es nicht: ``pyproject.toml``
    blieb bei 0.1.0 stehen, während das Programm längst 0.9.0 meldete.
    Wer MailBurg über pip installierte, bekam damit eine Fassung, die es
    seit Tagen nicht mehr gab. Aufgefallen am 2026-08-27 beim ersten
    Windows-Lauf, weil pip die Nummer beim Installieren ausgibt.
    """

    def setUp(self) -> None:
        self.wurzel = pathlib.Path(__file__).resolve().parent.parent

    def test_pyproject_nennt_keine_eigene_fassung(self) -> None:
        inhalt = (self.wurzel / "pyproject.toml").read_text(encoding="utf-8")

        # Nur die dynamische Angabe, keine fest eingetragene Nummer.
        self.assertIn('dynamic = ["version"]', inhalt)
        for zeile in inhalt.splitlines():
            if zeile.strip().startswith("version = ") and "attr" not in zeile:
                self.fail(f"feste Fassungsnummer in pyproject.toml: {zeile!r}")

    def test_die_fassung_kommt_aus_dem_paket(self) -> None:
        import tomllib

        daten = tomllib.loads(
            (self.wurzel / "pyproject.toml").read_text(encoding="utf-8")
        )
        quelle = daten["tool"]["setuptools"]["dynamic"]["version"]

        self.assertEqual(quelle, {"attr": "mailburg.__version__"})

    def test_beide_wege_nennen_dieselbe(self) -> None:
        """Der Sinn der Übung – hier würde ein Rückfall auffallen."""
        import tomllib

        from mailburg import __version__

        daten = tomllib.loads(
            (self.wurzel / "pyproject.toml").read_text(encoding="utf-8")
        )
        self.assertNotIn("version", set(daten["project"]) - {"dynamic"})
        self.assertRegex(__version__, r"^\d+\.\d+\.\d+")
