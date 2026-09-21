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
        """**Auch die Dateien in der Wurzel, nicht nur ``docs/``.**

        Bis zum 21.09.2026 sah dieser Wächter allein in ``docs/`` nach.
        README, CHANGELOG, TODO und RECHTLICHES waren ungeprüft – also
        ausgerechnet die Seiten, die auf GitHub als erstes aufgehen. Eine
        echte Adresse dort wäre nie aufgefallen, und der Test hätte
        weiterhin grün gemeldet.

        Bemerkt beim Anlegen der ``CONTRIBUTING.md``: Sie fiel durch
        jedes Raster, weil sie nicht in ``docs/`` liegt. Dieselbe Klasse
        wie die Lesbarkeitsprüfung, die zehn von einunddreißig Fenstern
        kannte – **eine Prüfung, deren Umfang von Disziplin abhängt, ist
        keine.**

        Nachgesehen: Zum Zeitpunkt der Erweiterung war keine der
        Wurzel-Dateien zu beanstanden. Die Lücke war also eine Flanke,
        keine Altlast.
        """
        import re

        erlaubt = (".example", ".test", ".invalid", "example.com",
                   "example.net", "example.org", "@meine-firma", "@ihre-firma")
        for datei in self._alle_texte():
            text = datei.read_text(encoding="utf-8")
            for adresse in re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", text):
                sauber = adresse.rstrip(">`.,)")
                with self.subTest(datei=datei.name, adresse=sauber):
                    self.assertTrue(
                        sauber.endswith(erlaubt),
                        f"{datei.name}: {sauber} ist keine Beispieladresse",
                    )

    @staticmethod
    def _alle_texte():
        """Jede Markdown-Datei des Projekts – in ``docs/`` und daneben.

        Neue Dateien sind damit von selbst erfasst. Eine Liste von Hand
        hält nicht: Wer eine Datei anlegt, denkt an die Datei, nicht an
        die Liste.
        """
        wurzel = pathlib.Path(__file__).resolve().parent.parent
        return sorted(wurzel.glob("*.md")) + sorted(
            (wurzel / "docs").glob("*.md")
        )

    def test_der_waechter_sieht_auch_in_die_wurzel(self):
        """Damit die Erweiterung nicht unbemerkt zurückgedreht wird."""
        namen = {d.name for d in self._alle_texte()}

        for pflicht in ("README.md", "README.en.md", "CHANGELOG.md",
                        "TODO.md", "CONTRIBUTING.md"):
            self.assertIn(pflicht, namen)


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

    def test_die_readme_nennt_die_aktuelle_fassung(self) -> None:
        """Die erste Zahl, die ein Besucher der Projektseite liest.

        **Am 2026-09-21 stand dort 1.4.8, während 1.5.0 veröffentlicht
        war.** Kein Test hat das gemeldet, weil es keinen gab – und
        gemerkt hat es Stephan beim Blick auf die eigene Seite.

        Eine Fassungsnummer in der Doku veraltet lautlos. Sie sieht auch
        dann richtig aus, wenn sie falsch ist, und sagt dem Leser
        obendrein etwas Falsches über das, was er gerade herunterlädt.

        **Dieser Wächter hält keinen Wortlaut fest, sondern erzwingt
        einen.** Das ist der Unterschied zu dem Test, der am 2026-09-07
        den Satz »Microsoft-Konten gehen derzeit nicht« konservierte: Der
        hier wird rot, *bis* die Doku nachgezogen ist.
        """
        from mailburg import __version__

        for datei, muster in (
            ("README.md", "**Fassung {},"),
            ("README.en.md", "**Version {},"),
        ):
            inhalt = (self.wurzel / datei).read_text(encoding="utf-8")
            erwartet = muster.format(__version__)
            self.assertIn(
                erwartet, inhalt,
                f"{datei} nennt nicht die Fassung {__version__} – "
                f"gesucht: {erwartet!r}",
            )


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


class OhneTerminalBrichtNichtsAbTest(unittest.TestCase):
    """``install.sh`` darf ohne angeschlossene Tastatur nicht aufgeben.

    **Am 2026-09-21 aufgelaufen**, beim Aktualisieren von Stephans
    Rechner auf die 1.5.0. Das Skript lief aus einer Werkzeugsitzung
    heraus, also ohne Terminal an ``stdin``. An der Frage nach den
    Systempaketen bekam ``read`` sofort EOF und lieferte 1 – und unter
    ``set -euo pipefail`` endet das Skript damit auf der Stelle.

    **Und zwar still.** Keine Fehlermeldung, die Ausgabe hörte mitten im
    Absatz auf, MailBurg war hinterher *nicht* aktualisiert. Einen
    Rückgabewert 1 gab es zwar – nur lief das Skript durch ein
    ``| tail``, und eine Pipe liefert den Wert ihres *letzten* Glieds.
    Gemerkt haben wir es allein daran, dass hinterher die
    Fassungsnummer nachgesehen wurde.

    Dieselbe Klasse wie der Zeitplan, der ins Leere zeigt (1.4.4), und
    wie das Programm, das startet und nichts tut (1.4.6): **Es sieht
    erledigt aus.** Ein Abbruch, der aussieht wie ein Ende, ist teurer
    als ein Absturz.

    Automatisch zu installieren wäre keine Abhilfe – ``sudo`` fragte
    dann seinerseits nach einem Passwort und hinge genauso. Also
    übersprungen, aber laut.
    """

    def setUp(self) -> None:
        self.skript = (
            pathlib.Path(__file__).resolve().parent.parent / "install.sh"
        ).read_text(encoding="utf-8")

    def _lauf(self, mit_terminal: bool):
        """Führt den Frageblock aus – wahlweise mit oder ohne Terminal.

        Ausgeführt, nicht gelesen: Ob eine Fallunterscheidung stimmt,
        sieht man ihrem Text nicht an. Das ist die Lehre vom 2026-09-03.

        **Ohne Rückgabeannotation, und das hat einen Grund.** Hier stand
        ``-> "subprocess.CompletedProcess"``, während der Import erst
        eine Zeile tiefer steht. Als Zeichenkette wertet Python das nie
        aus, die Tests liefen grün – pyflakes sieht trotzdem hin und
        machte die CI auf dem Tag v1.5.0 rot.
        """
        import subprocess

        zeilen = self.skript.splitlines()
        i = next(n for n, z in enumerate(zeilen)
                 if z.strip().startswith("if [[ -t 0 ]]"))
        j = next(n for n in range(i + 1, len(zeilen))
                 if zeilen[n].strip() == "fi"
                 and zeilen[n + 1].strip().startswith("if [[ !"))
        block = "\n".join(zeilen[i:j + 1])

        programm = "\n".join([
            "set -euo pipefail",
            "hinweis() { printf '%s\\n' \"$*\"; }",
            block,
            'printf "ANTWORT=%s\\n" "$antwort"',
            'printf "DURCHGELAUFEN\\n"',
        ])
        return subprocess.run(
            ["bash", "-c", programm],
            capture_output=True, text=True,
            # Ohne Terminal heißt: stdin ist eine Datei oder eine Pipe.
            # Genau so läuft es aus einem anderen Skript heraus.
            stdin=None if mit_terminal else subprocess.DEVNULL,
        )

    def test_ohne_terminal_laeuft_es_weiter(self) -> None:
        fertig = self._lauf(mit_terminal=False)
        self.assertEqual(fertig.returncode, 0, fertig.stderr)
        self.assertIn("DURCHGELAUFEN", fertig.stdout)

    def test_ohne_terminal_wird_nichts_installiert(self) -> None:
        """Sonst hinge ``sudo`` an seiner eigenen Passwortfrage."""
        fertig = self._lauf(mit_terminal=False)
        self.assertIn("ANTWORT=n", fertig.stdout)

    def test_ohne_terminal_steht_es_in_der_ausgabe(self) -> None:
        """**Stillschweigend überspringen wäre der gleiche Fehler.**

        Wer die Ausgabe später liest, muss sehen, dass hier etwas
        ausgelassen wurde – sonst hält er die Texterkennung für
        eingerichtet.
        """
        fertig = self._lauf(mit_terminal=False)
        self.assertIn("Kein Terminal", fertig.stdout)

    def test_die_frage_steht_noch_im_skript(self) -> None:
        """Mit Terminal wird weiterhin gefragt, nicht entschieden.

        Beim Bauen der Abhilfe war die Frage einen Moment lang ganz
        verschwunden – der Block las dann von einem Kanal, auf dem
        nichts stand, und niemand erfuhr, worum es ging.
        """
        self.assertIn('read -r -p "  Installieren? [J/n] " antwort',
                      self.skript)

    def test_auch_ein_abgerissenes_terminal_bricht_nicht_ab(self) -> None:
        """Strg+D mitten in der Eingabe, oder eine tote SSH-Sitzung."""
        self.assertIn('antwort || antwort=""', self.skript)
