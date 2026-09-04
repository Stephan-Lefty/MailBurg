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


class WindowsFassungKannAllesTest(unittest.TestCase):
    """Die ``.exe`` muss enthalten, was MailBurg kann.

    **Wer eine fertige Datei herunterlädt, installiert nichts nach.** Dort
    gibt es kein pip und keine Extras; was beim Bauen fehlt, fehlt
    endgültig.

    Am 2026-08-31 wäre genau das schiefgegangen: Die Verschlüsselung kam
    dazu, die Installationszeile des Bau-Workflows blieb stehen, und die
    erste ``.exe`` der 1.0 hätte kein verschlüsseltes Archiv geöffnet –
    auch keines, das auf dem Server oder unter Linux angelegt wurde. Die
    Meldung hätte zu »pip install« geraten, und das ist bei einer
    ``.exe`` eine Sackgasse.

    Aufgefallen ist es nur, weil Stephan nach der Server Edition im
    Release fragte.
    """

    def setUp(self) -> None:
        self.wurzel = pathlib.Path(__file__).resolve().parent.parent
        self.workflow = (
            self.wurzel / ".github" / "workflows" / "windows-exe.yml"
        ).read_text(encoding="utf-8")

    def test_jedes_extra_wird_mit_eingebaut(self) -> None:
        import tomllib

        daten = tomllib.loads(
            (self.wurzel / "pyproject.toml").read_text(encoding="utf-8")
        )
        extras = set(daten["project"]["optional-dependencies"])

        # ``alles`` ist nur eine Sammlung, und der Windows-Dienst hängt
        # an pywin32 - der ist bis zur Prüfung im Oktober 2026 nicht
        # dabei. Alles Übrige gehört in die gepackte Fassung.
        pflicht = extras - {"alles", "server-windows"}

        for extra in sorted(pflicht):
            with self.subTest(extra=extra):
                self.assertIn(
                    extra,
                    self.workflow,
                    f"»{extra}« fehlt in der Installationszeile der .exe – "
                    f"wer sie herunterlädt, kann das nicht nachrüsten",
                )


class SuchpfadhinweisTest(unittest.TestCase):
    """Der Hinweis auf den Suchpfad muss zur Shell des Anwenders passen.

    Am 2026-09-03 gemeldet: »Ich habe noch das Problem, dass ich es nach
    der Installation nicht via Konsole starten kann, aber das liegt
    vermutlich an fish.«

    Es lag an fish, und der Fehler war doppelt. Erstens prüfte das Skript
    seinen **eigenen** Suchpfad – den von bash, in dem es läuft. Viele
    Distributionen tragen ``~/.local/bin`` in ``/etc/profile`` ein, das
    fish gar nicht liest: bash findet den Ordner, das Skript schweigt,
    und in der Shell des Anwenders fehlt er trotzdem. Zweitens nannte der
    Hinweis ``~/.bashrc`` – eine Datei, die weder fish noch zsh anfassen.

    Ein Hinweis, der auf die falsche Datei zeigt, ist schlimmer als
    keiner: Wer die Zeile dort einträgt, sucht den Fehler danach überall,
    nur nicht mehr im Suchpfad.
    """

    def setUp(self) -> None:
        self.skript = (
            pathlib.Path(__file__).resolve().parent.parent / "install.sh"
        ).read_text(encoding="utf-8")

    def _abschnitt(self, anfang: str, ende: str) -> str:
        """Schneidet einen Block aus dem Skript heraus.

        Das ganze ``install.sh`` laufen zu lassen ginge nicht – es würde
        eine Python-Umgebung anlegen und Pakete holen. Geprüft wird
        deshalb der Block selbst, aber **ausgeführt**, nicht gelesen: Ob
        eine Fallunterscheidung stimmt, sieht man ihrem Text nicht an.
        """
        zeilen = self.skript.splitlines()
        i = next(n for n, z in enumerate(zeilen) if z.startswith(anfang))
        j = next(n for n in range(i + 1, len(zeilen)) if zeilen[n] == ende)
        return "\n".join(zeilen[i:j + 1])

    def _lauf(self, shell: str, im_suchpfad: bool = False) -> str:
        import os
        import subprocess
        import tempfile

        with tempfile.TemporaryDirectory() as heim:
            bin_ordner = os.path.join(heim, ".local", "bin")
            programm = "\n".join([
                f'BIN="{bin_ordner}"',
                "hinweis() { printf '%s\\n' \"$*\"; }",
                self._abschnitt("suchpfad_fehlt()", "}"),
                self._abschnitt("if suchpfad_fehlt; then", "fi"),
            ])
            umgebung = dict(os.environ)
            umgebung["SHELL"] = shell
            umgebung["HOME"] = heim
            pfad = "/usr/bin:/bin"
            if im_suchpfad:
                pfad = f"{bin_ordner}:{pfad}"
            umgebung["PATH"] = pfad
            fertig = subprocess.run(
                ["bash", "-c", programm],
                capture_output=True, text=True, env=umgebung,
            )
            self.assertEqual(fertig.returncode, 0, fertig.stderr)
            return fertig.stdout

    def test_fish_bekommt_fish_add_path(self) -> None:
        ausgabe = self._lauf("/usr/bin/fish")
        self.assertIn("fish_add_path", ausgabe)
        self.assertNotIn("bashrc", ausgabe)

    def test_zsh_bekommt_die_zshrc(self) -> None:
        ausgabe = self._lauf("/usr/bin/zsh")
        self.assertIn(".zshrc", ausgabe)
        self.assertNotIn("bashrc", ausgabe)

    def test_bash_bleibt_bei_der_bashrc(self) -> None:
        ausgabe = self._lauf("/bin/bash")
        self.assertIn(".bashrc", ausgabe)

    def test_wer_den_ordner_im_suchpfad_hat_wird_nicht_belaestigt(self) -> None:
        self.assertEqual(self._lauf("/bin/bash", im_suchpfad=True).strip(), "")


class WappenInDerExeTest(unittest.TestCase):
    """Was die Weboberfläche ausliefert, muss in der ``.exe`` stecken.

    **Wer eine fertige Datei herunterlädt, installiert nichts nach.**
    Fehlt ein Bild in der Spezifikation, liefert der Dienst dort eine 404
    aus – und niemand merkt es, weil eine Seite ohne Wappen genauso
    funktioniert wie eine mit. Genau deshalb dieser Test.
    """

    def setUp(self) -> None:
        self.wurzel = pathlib.Path(__file__).resolve().parent.parent
        self.spec = (
            self.wurzel / "werkzeuge" / "mailburg.spec"
        ).read_text(encoding="utf-8")

    def test_jede_ausgelieferte_datei_wird_mitgepackt(self) -> None:
        from mailburg.server.dienst import WAPPEN

        for name, _ in WAPPEN.values():
            with self.subTest(datei=name):
                self.assertIn(
                    pathlib.PurePosixPath(name).name,
                    self.spec,
                    f"»{name}« liefert der Dienst aus, die .exe bringt es "
                    f"aber nicht mit",
                )

    def test_die_dateien_gibt_es_wirklich(self) -> None:
        """Sonst steht in der Tabelle ein Name, den niemand mehr erzeugt."""
        from mailburg.server.dienst import WAPPEN

        for name, _ in WAPPEN.values():
            with self.subTest(datei=name):
                self.assertTrue((self.wurzel / "assets" / name).is_file())
