"""Das Debian-Paket – geprüft am gebauten Ergebnis, nicht am Skript.

**Warum ein natives Paket.** Unter Windows liefert MailBurg eine
einzelne ``.exe`` mit allem darin; dort gibt es keine Paketverwaltung,
die Qt beistellen könnte. Unter Debian gibt es sie, und ein Paket, das
sein eigenes Qt mitbringt, bekommt dessen Sicherheitsupdates nie.

Was sich hier prüfen lässt, ist der Bau. Ob die angegebenen
Abhängigkeiten wirklich existieren und ob MailBurg nach der Installation
startet, zeigt erst ``.github/workflows/deb.yml`` auf einem echten
Debian-System – hier steht Manjaro.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from importlib import util
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
HAT_DPKG = shutil.which("dpkg-deb") is not None


def _werkzeug():
    laden = util.spec_from_file_location(
        "deb_bauen", WURZEL / "werkzeuge" / "deb_bauen.py"
    )
    modul = util.module_from_spec(laden)
    laden.loader.exec_module(modul)
    return modul


class SteuerdatenTest(unittest.TestCase):
    """Was in der ``control`` steht, ohne dass gebaut werden muss."""

    def setUp(self):
        self.werkzeug = _werkzeug()

    def test_der_kern_haengt_an_nichts_ausser_python(self):
        """**Die Zusage des Projekts, auch im Paket.**

        Wer nur die Kommandozeile braucht – etwa auf einem Server –,
        soll sich kein Qt installieren müssen. Alles andere steht unter
        Recommends und lässt sich abwählen.
        """
        self.assertIn("python3", self.werkzeug.DEPENDS)
        for unerwuenscht in ("pyside", "qt", "keyring"):
            with self.subTest(paket=unerwuenscht):
                self.assertNotIn(unerwuenscht, self.werkzeug.DEPENDS.lower())

    def test_die_oberflaeche_wird_empfohlen(self):
        """Sonst installiert apt ein MailBurg ohne Fenster."""
        self.assertIn("pyside6", self.werkzeug.RECOMMENDS)
        self.assertIn("keyring", self.werkzeug.RECOMMENDS)

    def test_die_texterkennung_ist_nur_ein_vorschlag(self):
        """tesseract wiegt schwer und wird selten gebraucht."""
        self.assertIn("tesseract", self.werkzeug.SUGGESTS)
        self.assertNotIn("tesseract", self.werkzeug.RECOMMENDS)

    def test_die_startskripte_brauchen_kein_pip(self):
        """In einem Debian-Paket gibt es keines, das sie schreiben könnte."""
        skript = self.werkzeug._starter("mailburg.__main__", "main")

        self.assertTrue(skript.startswith("#!/usr/bin/python3"))
        self.assertIn("from mailburg.__main__ import main", skript)


@unittest.skipUnless(HAT_DPKG, "dpkg-deb fehlt")
class GebautesPaketTest(unittest.TestCase):
    """Einmal wirklich bauen und hineinsehen."""

    @classmethod
    def setUpClass(cls):
        cls.werkzeug = _werkzeug()
        cls._tmp = tempfile.TemporaryDirectory()
        cls.paket = cls.werkzeug.bauen(Path(cls._tmp.name))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def _inhalt(self) -> str:
        return subprocess.run(
            ["dpkg-deb", "--contents", str(self.paket)],
            capture_output=True, text=True, check=True,
        ).stdout

    def _control(self) -> str:
        return subprocess.run(
            ["dpkg-deb", "--field", str(self.paket)],
            capture_output=True, text=True, check=True,
        ).stdout

    def test_die_fassung_stammt_aus_dem_programm(self):
        """Eine zweite Stelle liefe früher oder später auseinander."""
        from mailburg import __version__

        self.assertIn(f"Version: {__version__}", self._control())
        self.assertIn(__version__, self.paket.name)

    def test_beide_startbefehle_liegen_drin(self):
        inhalt = self._inhalt()

        self.assertIn("./usr/bin/mailburg\n", inhalt)
        self.assertIn("./usr/bin/mailburg-gui\n", inhalt)

    def test_sie_sind_ausfuehrbar(self):
        for zeile in self._inhalt().splitlines():
            if zeile.endswith("/usr/bin/mailburg"):
                self.assertTrue(zeile.startswith("-rwxr-xr-x"), zeile)
                return
        self.fail("mailburg nicht gefunden")

    def test_die_bilder_kommen_mit(self):
        """Ohne sie hat das Fenster kein Banner und der Dienst kein Wappen."""
        inhalt = self._inhalt()

        self.assertIn("dist-packages/mailburg/assets/", inhalt)

    def test_menueeintrag_und_symbol(self):
        inhalt = self._inhalt()

        self.assertIn("de.stephanlefty.MailBurg.desktop", inhalt)
        self.assertIn("icons/hicolor/48x48/apps/mailburg.png", inhalt)

    def test_lizenz_und_aenderungsprotokoll(self):
        inhalt = self._inhalt()

        self.assertIn("usr/share/doc/mailburg/copyright", inhalt)
        self.assertIn("usr/share/doc/mailburg/changelog.gz", inhalt)

    def test_kein_uebersetzter_bytecode(self):
        """``__pycache__`` im Paket wäre Ballast mit falschen Zeitstempeln."""
        self.assertNotIn("__pycache__", self._inhalt())

    def test_nichts_gehoert_dem_bauenden_benutzer(self):
        """Sonst trägt das Paket die Kennung des Rechners, auf dem es entstand."""
        for zeile in self._inhalt().splitlines():
            if zeile.strip():
                self.assertIn("root/root", zeile, zeile)

    def test_zweimal_bauen_ergibt_dasselbe(self):
        """Byte für Byte, nicht nur der Anfang.

        **Sonst lässt sich nicht belegen, dass ein Paket zu einem Stand
        gehört.** Wer die Datei herunterlädt, kann sie dann selbst
        nachbauen und die Prüfsummen vergleichen – dafür darf weder die
        Bauzeit noch der bauende Benutzer hineinspielen.
        """
        import hashlib

        with tempfile.TemporaryDirectory() as zweit:
            wieder = self.werkzeug.bauen(Path(zweit))

            self.assertEqual(
                hashlib.sha256(self.paket.read_bytes()).hexdigest(),
                hashlib.sha256(wieder.read_bytes()).hexdigest(),
            )


if __name__ == "__main__":
    unittest.main()
