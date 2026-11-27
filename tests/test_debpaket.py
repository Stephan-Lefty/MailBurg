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

    def test_die_oberflaeche_ist_erforderlich(self):
        """**Seit dem 2026-11-25, und damit fällt die letzte Ausnahme.**

        Qt stand bis dahin unter *Recommends*, mit einer Begründung,
        die für sich trug: Wer nur die Kommandozeile braucht – etwa
        auf einem Server –, soll sich kein Qt installieren müssen.

        **Der Anlass für die Umkehr ist GuideOS.** MailBurg wird dort
        mitgeliefert, und wem es mitgeliefert wird, der hat es nicht
        gesucht. Ob der ISO-Bau Empfehlungen mitzieht, entschiede dann
        darüber, ob das Programm ein Fenster hat. Für den Anwender
        sähe das Fehlen so aus: *»Wenn ich das Tool starte, passiert
        gar nichts.«* Genau dieser Satz kam am 2026-09-14 von einem
        Anwender auf Linux Mint, dem das Paket fehlte.

        Der Preis ist bekannt: Ein Linux-Server bekommt Qt mit, ohne
        es zu brauchen. Das wiegt leichter – den Server bestückt
        jemand, der weiß, was er tut; der Arbeitsplatz gehört jemandem,
        der MailBurg vorfindet.

        Damit gilt die Regel aus CLAUDE.md ohne Ausnahme: *Was
        MailBurg zum Laufen braucht, gehört unter Depends.*
        """
        self.assertIn("python3", self.werkzeug.DEPENDS)
        self.assertIn("pyside6", self.werkzeug.DEPENDS.lower())

    def test_die_texterkennung_bleibt_draussen(self):
        """**tesseract nicht**, und das bleibt so: Es wiegt schwer und
        wird selten gebraucht. Ohne Texterkennung ist MailBurg
        benutzbar, nur ein eingescanntes PDF bleibt unauffindbar."""
        for unerwuenscht in ("tesseract", "poppler"):
            with self.subTest(paket=unerwuenscht):
                self.assertNotIn(unerwuenscht, self.werkzeug.DEPENDS.lower())

    def test_die_texterkennung_ist_nur_ein_vorschlag(self):
        """tesseract wiegt schwer und wird selten gebraucht."""
        self.assertIn("tesseract", self.werkzeug.SUGGESTS)
        self.assertNotIn("tesseract", self.werkzeug.RECOMMENDS)

    def test_die_startskripte_brauchen_kein_pip(self):
        """In einem Debian-Paket gibt es keines, das sie schreiben könnte."""
        skript = self.werkzeug._starter("mailburg.__main__", "main")

        self.assertTrue(skript.startswith("#!/usr/bin/python3"))
        self.assertIn("from mailburg.__main__ import main", skript)


def _steuerdatei() -> str:
    """``debian/control`` – die Datei, aus der wirklich gebaut wird."""
    return (WURZEL / "debian" / "control").read_text(encoding="utf-8")


def _feld(name: str, text: str | None = None) -> str:
    """Ein Feld aus ``debian/control``, über Zeilen hinweg.

    Fortsetzungszeilen beginnen in diesem Format mit einem
    Leerzeichen; Kommentarzeilen mit ``#`` gehören nicht dazu.

    ``text`` gibt es, damit die Leselogik selbst prüfbar ist, ohne
    die echte Datei anzufassen – eine Gegenprobe in der Arbeitskopie
    wäre genau der Fehler, den dieser Test verhindern soll.
    """
    zeilen: list[str] = []
    sammeln = False
    for zeile in (text if text is not None else _steuerdatei()).splitlines():
        if zeile.startswith("#"):
            continue
        if zeile.startswith(f"{name}:"):
            sammeln = True
            zeilen.append(zeile.split(":", 1)[1])
            continue
        if sammeln:
            if zeile.startswith((" ", "\t")):
                zeilen.append(zeile)
                continue
            break
    return " ".join(t.strip() for t in zeilen)


class EchteSteuerdatenTest(unittest.TestCase):
    """**Die Datei, die zählt – und zwei Wochen lang die falsche war.**

    Seit dem 06.11.2026 baut die CI mit ``dpkg-buildpackage`` aus
    ``debian/``; ``werkzeuge/deb_bauen.py`` erzeugt kein ausgeliefertes
    Paket mehr. Am 25.11. wurde PySide6 von *Recommends* nach
    *Depends* verschoben – **in der Datei, die nicht mehr gebaut
    wird.** Vier Testdateien prüften sie und waren grün.

    Aufgefallen am 27.11.2026, als der Admin der GuideOS-Distribution
    meldete, MailBurg sei installiert, »die grafische Oberflaeche
    fehlt aber noch« – und schrieb, das Paket gehöre in
    ``debian/control``. Er hatte recht, und das Repository sagte seit
    zwei Tagen das Gegenteil.

    *Eine Prüfung, die die fragliche Umgebung nicht nachstellt, misst
    etwas anderes* – hier in ihrer teuersten Form: Sie hat eine
    Korrektur bestätigt, die nirgends ankam.
    """

    def test_die_oberflaeche_ist_erforderlich(self):
        """Wer MailBurg vorfindet, bekommt sonst ein Programm ohne
        Fenster – eine übergangene Empfehlung merkt niemand."""
        self.assertIn("pyside6", _feld("Depends").lower())

    def test_und_steht_nicht_mehr_unter_recommends(self):
        """An beiden Stellen stünde es doppelt – und wer den einen
        Eintrag später streicht, hielte den anderen für die
        Entscheidung."""
        self.assertNotIn("pyside6", _feld("Recommends").lower())

    def test_der_schluesselbund_und_das_auspacken_sind_erforderlich(self):
        """Beide waren einmal nur empfohlen, beide haben einer
        Anwenderin den Betrieb unmöglich gemacht – siehe die
        Begründungen in ``debian/control``."""
        erforderlich = _feld("Depends").lower()

        for paket in ("python3-keyring", "python3-zstandard"):
            with self.subTest(paket=paket):
                self.assertIn(paket, erforderlich)

    def test_die_texterkennung_bleibt_draussen(self):
        """Ohne sie ist MailBurg benutzbar; nur ein eingescanntes PDF
        bleibt unauffindbar. Dafür gibt es den Nachrüstdialog."""
        self.assertNotIn("tesseract", _feld("Depends").lower())

    def test_der_alte_stand_wuerde_auffallen(self):
        """**Die Gegenprobe, und sie gehört hierher.**

        Ein Test, der nicht rot werden kann, ist keiner – und dieser
        hier wacht über einen Fehler, der zwei Tage lang unbemerkt
        blieb. Geprüft wird deshalb an einer nachgestellten Datei im
        alten Zustand, nicht durch Ändern der echten: Eine
        Gegenprobe in der Arbeitskopie hinterlässt einen Stand, den
        jemand versehentlich einchecken kann.
        """
        vorher = (
            "Package: mailburg\n"
            "Depends: ${python3:Depends},\n"
            "         python3-keyring,\n"
            "         python3-zstandard\n"
            "Recommends: python3-pyside6.qtwidgets,\n"
            "            poppler-utils\n"
        )

        self.assertNotIn("pyside6", _feld("Depends", vorher).lower())
        self.assertIn("pyside6", _feld("Recommends", vorher).lower())

    def test_die_paketfassung_ist_die_des_programms(self):
        """**Sonst käme die Dezemberfassung als 1.8.5 heraus.**

        ``dpkg-buildpackage`` nimmt die Versionsnummer aus
        ``debian/changelog`` und nirgends sonst – ``__version__`` im
        Python-Paket interessiert es nicht. Wer die Fassung erhöht
        und diese Datei vergisst, baut ein Paket mit neuem Inhalt und
        alter Nummer.

        **Der Schaden sieht nicht nach einem Fehler aus:** ``apt``
        vergleicht Nummern. Ein Paket, das dieselbe trägt wie das
        installierte, gilt als schon vorhanden – die neue Fassung
        wird niemandem angeboten, und niemand bekommt eine Meldung
        darüber. Dieselbe Klasse wie der Zeitplan, der auf ein
        verschobenes Programm zeigt: *Was eingerichtet aussieht, ist
        damit nicht eingerichtet.*

        Geprüft wird die erste Zeile, denn dort steht die Fassung,
        die gebaut wird – ältere Einträge darunter sind Geschichte.
        """
        from mailburg import __version__

        erste = (WURZEL / "debian" / "changelog").read_text(
            encoding="utf-8").splitlines()[0]

        self.assertIn(
            f"({__version__})", erste,
            f"debian/changelog beginnt mit »{erste}«, das Programm "
            f"steht auf {__version__} – das Paket bekäme die alte Nummer",
        )

    def test_ein_kommentar_zaehlt_nicht_zum_feld(self):
        """In ``debian/control`` steht die Begründung als
        Kommentarblock über dem Feld – und sie nennt beide
        Paketnamen. Läse die Hilfsfunktion sie mit, wäre jeder Test
        darüber wertlos: Er fände »pyside6« im Kommentar und wäre
        grün, egal wo das Paket wirklich steht."""
        mit_kommentar = (
            "# python3-pyside6.qtwidgets steht seit dem 27.11. unter\n"
            "# Depends und nicht mehr unter Recommends.\n"
            "Recommends: poppler-utils\n"
        )

        self.assertNotIn("pyside6", _feld("Recommends", mit_kommentar).lower())


class BeideSteuerdatenTest(unittest.TestCase):
    """**Zwei Dateien über dieselbe Sache, und keine wusste von der
    anderen.**

    ``werkzeuge/deb_bauen.py`` baut seit dem 06.11.2026 nichts
    Ausgeliefertes mehr, wird aber weiter gepflegt und von vier
    Testdateien gelesen. Solange das so ist, müssen beide dasselbe
    sagen – sonst steht in der einen eine Entscheidung, die nirgends
    gilt, und die nächste Änderung landet wieder in der falschen.

    *Zwei Prüfungen über dieselbe Sache, die sich widersprechen, sind
    in diesem Projekt die häufigste Fehlerklasse überhaupt.*
    """

    #: Was in beiden Listen auftauchen muss. Nicht die vollständige
    #: Liste: ``debian/control`` hat mit ``${python3:Depends}`` eine
    #: Schreibweise, die es im eigenen Bauskript nicht gibt.
    ERFORDERLICH = ("keyring", "zstandard", "pyside6")

    def test_dieselben_pakete_sind_erforderlich(self):
        eigenes = _werkzeug().DEPENDS.lower()
        debian = _feld("Depends").lower()

        for paket in self.ERFORDERLICH:
            with self.subTest(paket=paket):
                self.assertIn(paket, eigenes, "fehlt in deb_bauen.py")
                self.assertIn(paket, debian, "fehlt in debian/control")

    def test_und_keines_steht_hier_erforderlich_und_dort_empfohlen(self):
        """Der Fall, der am 25.11. eintrat – und zwei Tage unbemerkt
        blieb, weil ihn niemand prüfte."""
        empfohlen = f"{_werkzeug().RECOMMENDS} {_feld('Recommends')}".lower()

        for paket in self.ERFORDERLICH:
            with self.subTest(paket=paket):
                self.assertNotIn(paket, empfohlen)


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
