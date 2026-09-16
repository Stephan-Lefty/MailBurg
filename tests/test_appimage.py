"""Das AppImage – eine Datei, ausführbar machen, starten.

**Warum es das gibt.** Am 2026-09-14 meldete ein Anwender auf Linux
Mint: »Wenn ich das Tool starte, passiert gar nichts.« Das Debian-Paket
zieht die Oberfläche aus der Distribution nach, und Ubuntu, Mint,
Pop!_OS und Zorin führen PySide6 dort nicht. Für ihn blieb ein
``git clone`` und eine Viertelstunde Übersetzen.

Gepackt wird hier nichts – das braucht PyInstaller und ``appimagetool``
und gehört in die CI. Geprüft wird, was MailBurg dem AppImage *vorlegt*:
der Verzeichnisbaum, der Starter, der Menüeintrag. Genau dort sitzen die
Fehler dieser Art, und sie fallen erst beim Anwender auf.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from importlib import util
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent


def _werkzeug():
    laden = util.spec_from_file_location(
        "appimage_bauen_probe", WURZEL / "werkzeuge" / "appimage_bauen.py"
    )
    modul = util.module_from_spec(laden)
    laden.loader.exec_module(modul)
    return modul


class AufbauTest(unittest.TestCase):
    """Was im AppDir liegen muss, damit daraus ein AppImage wird."""

    def setUp(self):
        self.werkzeug = _werkzeug()
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.basis = Path(self.ordner.name)

        # Ein Stellvertreter für das, was PyInstaller liefert.
        self.dist = self.basis / "dist"
        self.dist.mkdir()
        (self.dist / "MailBurg").write_text(
            '#!/bin/sh\necho "MailBurg 0.0.0-probe"\n', encoding="utf-8"
        )
        (self.dist / "MailBurg").chmod(0o755)

        self.appdir = self.werkzeug.appdir_bauen(self.dist, self.basis)

    def test_der_starter_ist_ausfuehrbar(self):
        """**Ein Skript, das nicht ausführbar ist, ist keines.**

        Beim Debian-Paket hat ``dpkg-deb`` denselben Fehler am selben Tag
        gemeldet und den Bau verweigert. ``appimagetool`` merkt es nicht
        und baut ein Paket, das sich nicht starten lässt.
        """
        starter = self.appdir / "AppRun"

        self.assertTrue(starter.is_file())
        self.assertTrue(os.access(starter, os.X_OK))

    def test_der_starter_laeuft_wirklich(self):
        ergebnis = subprocess.run(
            [str(self.appdir / "AppRun")],
            capture_output=True, text=True, check=False, timeout=30,
        )

        self.assertEqual(ergebnis.returncode, 0, ergebnis.stderr)
        self.assertIn("MailBurg", ergebnis.stdout)

    def test_der_suchpfad_des_systems_bleibt_erhalten(self):
        """**Sonst findet die Texterkennung ihre Werkzeuge nicht.**

        ``pdftotext`` und ``tesseract`` kommen unter Linux aus der
        Distribution; das AppImage bringt sie bewusst nicht mit. Wer den
        Suchpfad überschreibt statt ihn zu ergänzen, bekommt ein
        MailBurg, das meldet, die Texterkennung sei nicht installiert –
        während sie danebenliegt.
        """
        starter = (self.appdir / "AppRun").read_text(encoding="utf-8")

        self.assertIn('PATH="$HIER/usr/bin:$PATH"', starter)

    def test_die_anzeigeart_wird_nicht_festgeschrieben(self):
        """Qt soll selbst zwischen Wayland und X11 wählen.

        Wer ``QT_QPA_PLATFORM`` im Starter festlegt, bricht die jeweils
        andere Sitzungsart – und zwar für alle, die sie benutzen.
        """
        starter = (self.appdir / "AppRun").read_text(encoding="utf-8")

        self.assertNotIn("QT_QPA_PLATFORM", starter)

    def test_der_menueeintrag_ist_da_und_vollstaendig(self):
        eintrag = (self.appdir / "mailburg.desktop").read_text(encoding="utf-8")

        for zeile in ("Type=Application", "Name=MailBurg",
                      "Exec=MailBurg", "Icon=mailburg",
                      "Categories=Office;Email;"):
            with self.subTest(zeile=zeile):
                self.assertIn(zeile, eintrag)

    def test_das_symbol_liegt_an_beiden_stellen(self):
        """AppImage sucht es neben ``AppRun``, die Menüs des Systems im
        Freedesktop-Baum. Fehlt es, steht in der Leiste ein grauer
        Platzhalter."""
        self.assertTrue((self.appdir / "mailburg.svg").is_file())
        self.assertTrue(
            (self.appdir / "usr" / "share" / "icons" / "hicolor"
             / "scalable" / "apps" / "mailburg.svg").is_file()
        )

    def test_ohne_gepacktes_programm_gibt_es_eine_ansage(self):
        """Und keinen Traceback: Wer das Werkzeug ohne PyInstaller-Lauf
        aufruft, soll lesen, was zu tun ist."""
        leer = self.basis / "leer"
        leer.mkdir()

        with self.assertRaises(SystemExit) as gefangen:
            self.werkzeug.appdir_bauen(leer, self.basis / "ziel")

        self.assertIn("pyinstaller", str(gefangen.exception))


class DateinameTest(unittest.TestCase):
    """**Keine Fassungsnummer im Dateinamen, und das ist Absicht.**

    Der Pfad zur Datei wandert in den Zeitplan für den regelmäßigen
    Abruf. Hieße sie ``MailBurg-1.4.6-x86_64.AppImage``, zeigte der
    Zeitplan nach jedem Update ins Leere und der Abruf hörte
    stillschweigend auf – genau der Fehler, der in der 1.4.4 behoben
    wurde. Dieselbe Überlegung wie bei der ``MailBurg.exe``.
    """

    def test_der_name_traegt_keine_fassung(self):
        from mailburg import __version__

        name = _werkzeug().DATEINAME

        self.assertNotIn(__version__, name)
        self.assertTrue(name.endswith(".AppImage"))

    def test_und_er_nennt_die_architektur(self):
        """Ohne sie weiß niemand, ob die Datei auf seinen Rechner passt –
        und AppImage-Werkzeuge lesen sie aus dem Namen."""
        self.assertIn("x86_64", _werkzeug().DATEINAME)


class BauplanTest(unittest.TestCase):
    """Der PyInstaller-Bauplan gilt für beide Systeme.

    Zwei Baupläne, die fast gleich sind, laufen auseinander – und der
    seltener benutzte ist dann der falsche.
    """

    def _spec(self) -> str:
        return (WURZEL / "werkzeuge" / "mailburg.spec").read_text(
            encoding="utf-8"
        )

    def test_der_schluesselbund_kommt_je_system_mit(self):
        """**Unter Windows war das schon einmal der Fehler.** Ohne die
        Anbindung fragt MailBurg bei jedem Abruf nach dem Passwort, und
        der Hintergrundabruf wäre unmöglich. Unter Linux heißt sie
        SecretService statt Windows."""
        spec = self._spec()

        self.assertIn("keyring.backends.Windows", spec)
        self.assertIn("keyring.backends.SecretService", spec)

    def test_windowseigenes_bleibt_unter_windows(self):
        """``win32ctypes`` und die ``.ico`` gibt es unter Linux nicht –
        PyInstaller bricht dort ab, wenn sie trotzdem verlangt werden."""
        spec = self._spec()

        self.assertIn("if WINDOWS", spec)
        self.assertIn('WINDOWS = sys.platform == "win32"', spec)


if __name__ == "__main__":
    unittest.main()
