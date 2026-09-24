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

    def test_kein_qt_unter_den_erforderlichen(self):
        """**Die Zusage des Projekts, auch im Paket.**

        Wer nur die Kommandozeile braucht – etwa auf einem Server –,
        soll sich kein Qt installieren müssen. Die Oberfläche steht
        deshalb unter Recommends und lässt sich abwählen.

        **Der Schlüsselbund stand hier bis zum 2026-09-23 ebenfalls**,
        mit derselben Begründung. Sie trägt bei ihm nicht: Qt braucht
        wirklich nur, wer ein Fenster will – ohne Schlüsselbund dagegen
        wird jedes Passwort bei jedem Abruf neu erfragt, auch auf der
        Kommandozeile, und ein Abruf im Hintergrund läuft gar nicht.

        Den Ausschlag gab, dass ein bloß empfohlenes Paket von
        ``apt autoremove`` weggeräumt werden darf. Genau das ist einer
        Anwenderin passiert; sie hätte daraufhin ihre Passwörter neu
        eingetippt – in einen Speicher, den es nicht mehr gab. Ein
        kleines, auf manchen Servern unnötiges Paket wiegt weniger.
        """
        self.assertIn("python3", self.werkzeug.DEPENDS)
        for unerwuenscht in ("pyside", "qt", "tesseract"):
            with self.subTest(paket=unerwuenscht):
                self.assertNotIn(unerwuenscht, self.werkzeug.DEPENDS.lower())

    def test_die_oberflaeche_wird_empfohlen(self):
        """Sonst installiert apt ein MailBurg ohne Fenster."""
        self.assertIn("pyside6", self.werkzeug.RECOMMENDS)

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



class HinweisBeiFehlendemQtTest(unittest.TestCase):
    """Was MailBurg rät, wenn die Oberfläche fehlt.

    **Ein Hinweis auf den falschen Weg ist schlimmer als keiner.** Wer
    MailBurg als Debian-Paket installiert hat und ``pip install`` liest,
    tut entweder nichts oder bringt seine Systempakete durcheinander.
    Derselbe Fehler wie am 2026-09-03, als der Suchpfad-Hinweis auf
    ``~/.bashrc`` zeigte, während der Anwender fish benutzte.

    Der Fall ist nicht ausgedacht: Unter Debian 13 liegt PySide6 bereit,
    unter Ubuntu 24.04 gibt es es gar nicht als Paket – dort läuft
    dieser Text also wirklich auf.
    """

    def _hinweis(self, aus_paket: bool) -> str:
        from unittest import mock

        from mailburg.ui import app

        with mock.patch.object(app, "aus_systempaket", return_value=aus_paket):
            return app._qt_fehlt()

    def test_im_systempaket_wird_apt_genannt(self):
        text = self._hinweis(True)

        self.assertIn("apt install python3-pyside6", text)
        self.assertNotIn("pip install", text)

    def test_und_die_luecke_bei_ubuntu_steht_dabei(self):
        """Sonst sucht jemand ein Paket, das es dort nicht gibt."""
        self.assertIn("Ubuntu", self._hinweis(True))

    def test_sonst_bleibt_es_bei_pip(self):
        text = self._hinweis(False)

        self.assertIn("pip install", text)
        self.assertNotIn("apt install", text)

    def test_beide_wege_nennen_die_kommandozeile_als_ausweg(self):
        """Ohne Oberfläche ist MailBurg nicht unbenutzbar."""
        for aus_paket in (True, False):
            with self.subTest(systempaket=aus_paket):
                self.assertIn("mailburg --help", self._hinweis(aus_paket))

    def test_die_erkennung_haengt_am_ablageort(self):
        """``dist-packages`` ist Debian, ``site-packages`` ist pip."""
        from unittest import mock

        from mailburg.ui import app

        for ort, erwartet in (
            ("/usr/lib/python3/dist-packages/mailburg/ui/app.py", True),
            ("/home/wer/.local/share/mailburg/venv/lib/python3.13/"
             "site-packages/mailburg/ui/app.py", False),
        ):
            with self.subTest(ort=ort):
                with mock.patch.object(app, "__file__", ort):
                    self.assertEqual(app.aus_systempaket(), erwartet)

    def test_im_appimage_hilft_weder_pip_noch_apt(self):
        """**Ein Rat auf den falschen Weg ist schlimmer als keiner.**

        Ein AppImage bringt Qt mit. Fehlt es trotzdem, ist die Datei
        beschädigt oder falsch gebaut – ``pip install`` hilft dagegen
        nicht, und ``apt`` auch nicht.

        Am 2026-09-16 im Prüflauf gesehen: Das AppImage riet zu
        ``pip install 'mailburg[oberflaeche]'``, weil
        ``aus_systempaket()`` nur ``dist-packages`` kennt und ein
        AppImage keines ist.
        """
        from unittest import mock

        from mailburg.ui import app

        with mock.patch.dict(
            "os.environ", {"APPIMAGE": "/opt/MailBurg-x86_64.AppImage"}
        ):
            text = app._qt_fehlt()

        self.assertNotIn("pip install", text)
        self.assertNotIn("apt install", text)
        # Stattdessen: neu laden – und wenn das nicht hilft, melden.
        self.assertIn("releases/latest", text)
        self.assertIn("issues", text)

    def test_linux_mint_wird_beim_namen_genannt(self):
        """**Wer nicht gemeint ist, fühlt sich nicht angesprochen.**

        Der Hinweis nannte nur Ubuntu. Der Anwender, der ihn am
        2026-09-14 gebraucht hätte, saß vor Linux Mint – und hätte selbst
        dann, wenn er ihn zu Gesicht bekommen hätte, nicht erkannt, dass
        er gemeint ist.
        """
        self.assertIn("Linux Mint", self._hinweis(True))


class StummerFehlstartTest(unittest.TestCase):
    """**Ein Programm, das startet und nichts tut, ist ein kaputtes.**

    Der Hinweis auf das fehlende PySide6 ging auf ``stderr``. Ein
    Menüeintrag startet ohne Terminal (``Terminal=false`` in der
    ``.desktop``-Datei) – die Zeile fiel also ins Nichts, das Programm
    endete mit Code 2, und für den Anwender sah es so aus:

        »Wenn ich das Tool starte, passiert gar nichts.«

    So gemeldet am 2026-09-14 von einem Anwender auf Linux Mint. Er hat
    sich dafür entschuldigt – »meist liegt es ja an dem Honk vor dem
    Monitor«. **Es lag am Programm.**

    Dasselbe Muster wie dreimal zuvor, hier in seiner ärgerlichsten
    Form: Die Auskunft war vollständig da und wurde nirgends abgeholt.
    """

    def _melden(self, *, tty: bool, bildschirm: bool, vorhanden=("zenity",)):
        import sys
        from unittest import mock

        from mailburg.ui import app

        gerufen = []
        umgebung = {"DISPLAY": ":0"} if bildschirm else {}
        with mock.patch.object(sys.stderr, "isatty", lambda: tty), \
             mock.patch.dict("os.environ", umgebung, clear=True), \
             mock.patch("shutil.which",
                        lambda n: f"/usr/bin/{n}" if n in vorhanden else None), \
             mock.patch("subprocess.run",
                        lambda *a, **k: gerufen.append(list(a[0]))), \
             mock.patch("builtins.print"):
            app._sichtbar_melden("Titel", "Der Text")
        return gerufen

    def test_ohne_terminal_kommt_ein_fenster(self):
        gerufen = self._melden(tty=False, bildschirm=True)

        self.assertTrue(gerufen, "Die Meldung bleibt unsichtbar")
        self.assertIn("Der Text", " ".join(gerufen[0]))

    def test_im_terminal_bleibt_es_bei_der_zeile(self):
        """Wer dort startet, hat sie schon gelesen – ein Fenster wäre Lärm."""
        self.assertEqual(self._melden(tty=True, bildschirm=True), [])

    def test_ohne_bildschirm_wird_niemand_behelligt(self):
        """Auf einem Server gibt es niemanden, dem man etwas zeigen könnte."""
        self.assertEqual(self._melden(tty=False, bildschirm=False), [])

    def test_es_reicht_irgendeines_der_werkzeuge(self):
        """MailBurg verlangt keines davon – es nimmt, was da ist."""
        for werkzeug in ("zenity", "kdialog", "xmessage", "notify-send"):
            with self.subTest(werkzeug=werkzeug):
                gerufen = self._melden(
                    tty=False, bildschirm=True, vorhanden=(werkzeug,)
                )

                self.assertTrue(gerufen, f"{werkzeug} wird nicht genutzt")
                self.assertEqual(gerufen[0][0], werkzeug)

    def test_ohne_jedes_werkzeug_faellt_es_nicht_um(self):
        """Dann bleibt nur die Zeile – aber nichts stürzt ab."""
        self.assertEqual(
            self._melden(tty=False, bildschirm=True, vorhanden=()), []
        )

    def test_die_zeile_auf_stderr_bleibt_in_jedem_fall(self):
        """Sie ist das, was in einem Fehlerbericht landet."""
        import io
        import sys
        from unittest import mock

        from mailburg.ui import app

        gefangen = io.StringIO()
        with mock.patch.object(sys, "stderr", gefangen), \
             mock.patch.dict("os.environ", {}, clear=True):
            app._sichtbar_melden("Titel", "Der Text")

        self.assertIn("Der Text", gefangen.getvalue())


class PostinstTest(unittest.TestCase):
    """Gesagt wird es, **bevor** jemand vergeblich klickt.

    PySide6 steht in ``Recommends``, damit das Paket auch auf einen
    Server passt. Führt eine Distribution das Paket gar nicht – Ubuntu
    und Linux Mint tun das nicht –, installiert ``apt`` es schweigend
    nicht, und MailBurg liegt ohne Oberfläche auf der Platte.
    """

    def _skript(self) -> str:
        laden = util.spec_from_file_location(
            "deb_bauen_probe", WURZEL / "werkzeuge" / "deb_bauen.py"
        )
        modul = util.module_from_spec(laden)
        laden.loader.exec_module(modul)
        return modul.POSTINST

    def test_es_prueft_auf_pyside(self):
        self.assertIn("import PySide6", self._skript())

    def test_es_nennt_beide_wege(self):
        text = self._skript()

        self.assertIn("apt install python3-pyside6", text)
        self.assertIn("install.sh", text)
        self.assertIn("Linux Mint", text)

    def test_ein_hinweis_bricht_keine_installation_ab(self):
        """**Kein ``exit 1``.** Die Kommandozeile läuft auch ohne Qt, und
        wer einen Server bestückt, will genau das. Ein Paket, das sich
        wegen eines Hinweises nicht installieren lässt, wäre schlimmer
        als der Hinweis.
        """
        zeilen = [z.strip() for z in self._skript().splitlines() if z.strip()]

        self.assertNotIn("exit 1", zeilen)
        self.assertEqual(zeilen[-1], "exit 0")

    def test_nur_beim_einrichten(self):
        """``postinst`` wird auch bei ``abort-upgrade`` gerufen – dann hat
        niemand etwas installiert, und der Hinweis wäre verwirrend."""
        self.assertIn('"$1" != "configure"', self._skript())


if __name__ == "__main__":
    unittest.main()
