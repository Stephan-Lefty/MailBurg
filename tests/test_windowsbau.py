"""Tests für den Bauplan der Windows-Fassung.

Gebaut werden kann hier nichts – PyInstaller packt immer für das System,
auf dem es läuft, und das ist Linux. Geprüft wird deshalb der Bauplan
selbst: ob er die Dinge nennt, ohne die die fertige Datei entweder gar
nicht startet oder etwas Wichtiges nicht kann.

Das ist keine Förmlichkeit. Eine ``.exe``, die sich bauen lässt und
beim Start über ein fehlendes Modul stolpert, ist schlimmer als keine:
Sie fällt erst dem Anwender auf, und der hat kein Python, um
nachzusehen, woran es liegt.
"""

from __future__ import annotations

import pathlib
import unittest

WURZEL = pathlib.Path(__file__).resolve().parent.parent


class BauplanTest(unittest.TestCase):
    """Was in der gepackten Fassung stecken muss."""

    def setUp(self) -> None:
        self.spec = (WURZEL / "werkzeuge" / "mailburg.spec").read_text(
            encoding="utf-8"
        )

    def test_der_schluesselbund_kommt_mit(self) -> None:
        """Sonst fragt MailBurg bei jedem Abruf nach dem Passwort.

        ``keyring`` sucht seinen Speicher zur Laufzeit über
        Einstiegspunkte. PyInstaller sieht davon nichts und ließe die
        Windows-Anbindung weg – die fertige Datei könnte dann keine
        Passwörter merken, und der Abruf im Hintergrund wäre unmöglich.
        """
        self.assertIn("keyring.backends.Windows", self.spec)
        self.assertIn("win32ctypes", self.spec)

    def test_kein_konsolenfenster(self) -> None:
        """Wer doppelklickt, will das Programm sehen, kein schwarzes Fenster."""
        self.assertIn("console=False", self.spec)

    def test_das_symbol_ist_dabei(self) -> None:
        self.assertIn("mailburg.ico", self.spec)
        self.assertTrue((WURZEL / "assets" / "mailburg.ico").is_file())

    def test_die_anleitungen_werden_mitgeliefert(self) -> None:
        """Wer eine einzelne Datei lädt, hat sonst keine Dokumentation."""
        self.assertIn('"docs"', self.spec)
        self.assertIn("LICENSE", self.spec)

    def test_upx_bleibt_aus(self) -> None:
        """Gepackte Programme lösen häufiger Virenwarnungen aus.

        Eine unsignierte Datei hat es bei SmartScreen ohnehin schwer
        genug; ein zusätzlicher Verdachtsgrund für ein paar Megabyte
        wäre ein schlechter Tausch.
        """
        self.assertIn("upx=False", self.spec)

    def test_der_einstieg_existiert(self) -> None:
        self.assertTrue((WURZEL / "werkzeuge" / "start_gui.py").is_file())


class EinstiegTest(unittest.TestCase):
    """Der Startpunkt der gepackten Fassung."""

    def setUp(self) -> None:
        self.quelle = (WURZEL / "werkzeuge" / "start_gui.py").read_text(
            encoding="utf-8"
        )

    def test_freeze_support_steht_drin(self) -> None:
        """Ohne das startet sich das Programm endlos selbst neu.

        Unter Windows gibt es kein ``fork()``; Python startet für jeden
        Arbeitsprozess die Datei erneut. In einer gepackten Anwendung
        *ist* diese Datei die Anwendung – also öffnet jeder Prozess ein
        neues Fenster, das wieder Prozesse startet. MailBurg zerlegt
        Anhänge in einem Prozesspool und liefe genau hinein.
        """
        self.assertIn("freeze_support", self.quelle)

        # **Und zwar als erste Anweisung im Hauptblock.** Geprüft wird
        # die Ausführungs-, nicht die Textreihenfolge: Ein Import in
        # einer Funktion weiter oben läuft erst, wenn sie gerufen wird,
        # und das ist danach. Die frühere Textprüfung schlug deshalb
        # fehl, als die Weiche zwischen Fenster und Kommandozeile
        # dazukam - obwohl daran nichts falsch war.
        hauptblock = self.quelle.split('if __name__ == "__main__":', 1)[1]
        anweisungen = [
            z.strip() for z in hauptblock.splitlines()
            if z.strip() and not z.strip().startswith("#")
        ]
        self.assertEqual(anweisungen[0], "multiprocessing.freeze_support()")


class FassungsangabeTest(unittest.TestCase):
    """Die Nummer in der ``.exe`` wird abgeleitet, nicht abgeschrieben.

    Genau daran ist es schon einmal gescheitert: ``pyproject.toml`` trug
    0.1.0, während das Programm 0.9.0 meldete, und pip installierte eine
    Fassung, die es nicht mehr gab. Eine dritte Stelle mit derselben
    Zahl wäre die dritte Gelegenheit, dass sie auseinanderläuft.
    """

    def _zahlenfolge(self, fassung: str) -> str:
        import sys

        sys.path.insert(0, str(WURZEL / "werkzeuge"))
        from fassung_erzeugen import zahlenfolge

        return zahlenfolge(fassung)

    def test_die_uebliche_form(self) -> None:
        self.assertEqual(self._zahlenfolge("0.9.0"), "0, 9, 0, 0")

    def test_windows_verlangt_immer_vier_zahlen(self) -> None:
        for fassung in ("1.0", "2", "0.9.0"):
            with self.subTest(fassung=fassung):
                self.assertEqual(len(self._zahlenfolge(fassung).split(",")), 4)

    def test_ein_zusatz_wird_abgeschnitten(self) -> None:
        """»0.9.0rc1« ist für Windows keine Zahl – die Anzeige ist kein Vertrag."""
        self.assertEqual(self._zahlenfolge("2.3.4rc1"), "2, 3, 4, 0")

    def test_die_erzeugte_datei_nennt_die_echte_fassung(self) -> None:
        import subprocess
        import sys
        import tempfile

        from mailburg import __version__

        with tempfile.TemporaryDirectory() as ordner:
            ziel = pathlib.Path(ordner) / "fassung.txt"
            subprocess.run(
                [sys.executable, str(WURZEL / "werkzeuge" / "fassung_erzeugen.py"),
                 str(ziel)],
                check=True, capture_output=True,
            )
            inhalt = ziel.read_text(encoding="utf-8")

        self.assertIn(f"'{__version__}'", inhalt)
        self.assertIn("MailBurg", inhalt)


class BaulaufTest(unittest.TestCase):
    """Wann der Windows-Bau läuft – und wann ausdrücklich nicht.

    GitHub rechnet Windows-Minuten doppelt, und dieses Konto hat schon
    einmal an einem einzigen Arbeitstag sein Monatskontingent verbraucht
    (1.800 von 2.000). Ein Build je Push wäre der schnellste Weg
    dorthin zurück.
    """

    #: Bewusst ohne PyYAML gelesen. Die Testsuite läuft in der CI mit der
    #: nackten Standardbibliothek – so, wie MailBurg selbst ohne
    #: Fremdpakete auskommt. Ein Test, der ein Paket nachfordert, wäre
    #: der erste Riss in dieser Regel, und für das bisschen Textsuche
    #: hier lohnt er nicht.
    def setUp(self) -> None:
        self.text = (
            WURZEL / ".github" / "workflows" / "windows-exe.yml"
        ).read_text(encoding="utf-8")

        # Der Abschnitt zwischen "on:" und dem nächsten Schlüsselwort
        # ganz links.
        self.ausloeser: list[str] = []
        drin = False
        for zeile in self.text.splitlines():
            if zeile.startswith("on:"):
                drin = True
                continue
            if drin:
                if zeile and not zeile[0].isspace():
                    break
                if zeile.startswith("  ") and not zeile.startswith("    "):
                    self.ausloeser.append(zeile.strip().rstrip(":").split(":")[0])

    def test_laeuft_nicht_bei_jedem_push(self) -> None:
        self.assertNotIn("push", self.ausloeser)
        self.assertNotIn("pull_request", self.ausloeser)
        self.assertNotIn("schedule", self.ausloeser)

    def test_laeuft_bei_einer_veroeffentlichung(self) -> None:
        self.assertIn("release", self.ausloeser)
        self.assertIn("workflow_dispatch", self.ausloeser)

    def test_die_datei_wird_ausprobiert(self) -> None:
        """Eine .exe, die nur gebaut wurde, ist nicht geprüft."""
        self.assertIn("--version", self.text)
        self.assertIn("MailBurg \\d+\\.\\d+\\.\\d+", self.text)

    def test_es_gibt_eine_pruefsumme(self) -> None:
        """Bei einer unsignierten Datei das Mindeste."""
        self.assertIn("SHA256", self.text)

    def test_alle_zusaetze_werden_eingepackt(self) -> None:
        """Wer eine fertige Datei lädt, installiert nichts nach."""
        for zusatz in ("oberflaeche", "imap", "anhaenge", "packen"):
            with self.subTest(zusatz=zusatz):
                self.assertIn(zusatz, self.text)


if __name__ == "__main__":
    unittest.main()


class SymbolUndTitelTest(unittest.TestCase):
    """Zwei Schönheitsfehler, die nur in der gepackten Fassung auffielen.

    Beide sind harmlos und beide wirken schäbig – bei einem Programm,
    das man ohne Installation aus dem Netz lädt und dem man seine Post
    anvertrauen soll, ist das keine Kleinigkeit.
    """

    def setUp(self) -> None:
        self.quelle = (WURZEL / "mailburg" / "ui" / "app.py").read_text(
            encoding="utf-8"
        )

    def test_das_symbol_wird_auch_im_gepackten_ordner_gesucht(self) -> None:
        """PyInstaller entpackt sich in ein Verzeichnis, das erst entsteht.

        Ohne diesen Fall zeigte das Fenster unter Windows ein leeres
        Blatt: Das Symbol steckte zwar in der ``.exe`` und erschien in
        der Dateiliste, aber Qt braucht es zusätzlich für das Fenster.
        """
        self.assertIn("_MEIPASS", self.quelle)
        self.assertIn("mailburg.ico", self.quelle)

    def test_kein_anzeigename(self) -> None:
        """Sonst steht der Programmname zweimal im Titel.

        Qt hängt ``applicationDisplayName`` jedem Fenstertitel an, und
        die Fenster nennen MailBurg bereits selbst – heraus kam
        »MailBurg – Mailarchiv - MailBurg«.
        """
        self.assertNotIn("setApplicationDisplayName", self.quelle)
        self.assertIn("setApplicationName", self.quelle)

    def test_der_name_wird_nur_einmal_gesetzt(self) -> None:
        self.assertEqual(self.quelle.count("setApplicationName("), 1)


class GrafikenTest(unittest.TestCase):
    """Die Bilder müssen in die gepackte Datei und dort gefunden werden.

    Beim ersten Wurf lag nur die ``.ico`` darin – und der
    Willkommensbildschirm zeigte kein Logo mehr, weil die Burg mit dem
    Schriftzug aus einer SVG kommt. Das Erste, was ein neuer Anwender
    sieht, war damit kahl (2026-08-28).
    """

    def test_die_banner_werden_eingepackt(self) -> None:
        spec = (WURZEL / "werkzeuge" / "mailburg.spec").read_text(
            encoding="utf-8"
        )

        for datei in ("banner.svg", "banner-dark.svg", "icon.svg"):
            with self.subTest(datei=datei):
                self.assertIn(datei, spec)
                self.assertTrue((WURZEL / "assets" / datei).is_file())

    def test_qt_kann_svg_zeichnen(self) -> None:
        """QPixmap lädt das Modul zur Laufzeit – PyInstaller sieht das nicht."""
        spec = (WURZEL / "werkzeuge" / "mailburg.spec").read_text(
            encoding="utf-8"
        )

        self.assertIn("PySide6.QtSvg", spec)
        # Und es darf nicht zugleich ausgeschlossen sein.
        draussen = spec.split("DRAUSSEN = [", 1)[1].split("]", 1)[0]
        self.assertNotIn("QtSvg", draussen)

    def test_der_gepackte_ordner_wird_durchsucht(self) -> None:
        """Sonst nützt das Einpacken nichts."""
        quelle = (WURZEL / "mailburg" / "ui" / "bilder.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("_MEIPASS", quelle)

    def test_der_gepackte_ordner_kommt_zuerst(self) -> None:
        """Was mitgeliefert wurde, gilt – nicht irgendetwas vom System."""
        import sys
        import tempfile
        from unittest import mock

        from mailburg.ui import bilder

        with tempfile.TemporaryDirectory() as ordner:
            with mock.patch.object(sys, "_MEIPASS", ordner, create=True):
                orte = bilder._orte()

        self.assertEqual(str(orte[0]), str(pathlib.Path(ordner) / "assets"))


class WeicheTest(unittest.TestCase):
    """Die .exe muss Fenster und Kommandozeile auseinanderhalten.

    Unter Linux gibt es zwei Startbefehle, ``mailburg`` und
    ``mailburg-gui``. Unter Windows gibt es eine Datei, und die muss
    beides können.

    Ohne die Weiche wurde jedes Argument als Archivpfad gedeutet:
    ``MailBurg.exe abrufen --leise C:\\Archiv`` öffnete ein Fenster mit
    dem Archiv »abrufen«, fand keines und blieb mit einem Fehlerdialog
    stehen. Der eingerichtete Zeitplan ruft genau so auf – er hätte alle
    30 Minuten ein Fenster geöffnet, statt Post zu holen. Aufgefallen am
    2026-08-28, als ein Prüfschritt im Bau-Workflow hängenblieb, weil er
    auf einen Klick wartete, den auf einem Bauserver niemand macht.
    """

    def setUp(self) -> None:
        import sys

        sys.path.insert(0, str(WURZEL / "werkzeuge"))
        import start_gui

        self.start = start_gui

    def test_die_befehle_werden_abgefragt_nicht_aufgezaehlt(self) -> None:
        """Eine Liste im Quelltext würde beim nächsten Befehl vergessen."""
        befehle = self.start._befehle()

        for erwartet in ("abrufen", "sichern", "suchen", "werkzeuge"):
            with self.subTest(befehl=erwartet):
                self.assertIn(erwartet, befehle)

    def test_der_zeitplan_ruft_einen_bekannten_befehl(self) -> None:
        """Sonst öffnet die Aufgabenplanung alle 30 Minuten ein Fenster."""
        quelle = (
            WURZEL / "mailburg" / "core" / "aufgabenplanung.py"
        ).read_text(encoding="utf-8")

        befehle = self.start._befehle()
        # Was in aufgabenplanung.py als erstes Wort der Argumente steht.
        for zeile in quelle.splitlines():
            if "abrufen --leise" in zeile:
                self.assertIn("abrufen", befehle)
            if "sichern --leise" in zeile:
                self.assertIn("sichern", befehle)

    def test_ohne_argumente_kommt_das_fenster(self) -> None:
        """Wer doppelklickt, will kein Hilfetext."""
        quelle = (WURZEL / "werkzeuge" / "start_gui.py").read_text(
            encoding="utf-8"
        )

        # Die Oberfläche steht als letztes, ohne Bedingung davor.
        self.assertIn("from mailburg.ui.app import main", quelle)
        self.assertLess(
            quelle.index("kommandozeile"),
            quelle.index("from mailburg.ui.app import main"),
        )
