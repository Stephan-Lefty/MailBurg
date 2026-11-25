"""Fehlende Pakete per Knopfdruck – statt per Befehl zum Abtippen.

**Der Anlass war ein Nachmittag voller Terminalbefehle.** Am
2026-11-25 richtete Stephan MailBurg auf einem frisch installierten
GuideOS ein und musste nacheinander PySide6, tesseract und die
deutschen Sprachdaten von Hand nachinstallieren – jedes Mal, nachdem
ihn eine Meldung darauf hingewiesen hatte. Seine Vorgabe danach:

    Egal wo man MailBurg installiert, wir müssen dem User immer die
    Chance geben, dass er per Klick die Pakete nachinstallieren kann,
    die noch benötigt werden! Und dann ein erledigt kommt, damit er
    die Einrichtung weiter vornehmen kann. Alles andere ist
    unprofessionell.
"""

from __future__ import annotations

import unittest
from unittest import mock

from mailburg.core import nachruesten


class PaketverwaltungTest(unittest.TestCase):
    """Erkannt wird sie am vorhandenen Programm, nicht am Namen."""

    def test_ueber_das_programm_und_nicht_ueber_os_release(self) -> None:
        """**``/etc/os-release`` kennt Dutzende Ableger**, und der
        nächste heißt wieder anders. ``apt-get`` heißt überall so."""
        with mock.patch.object(nachruesten.sys, "platform", "linux"), \
                mock.patch.object(
                    nachruesten.shutil, "which",
                    side_effect=lambda w: "/usr/bin/pacman"
                    if w == "pacman" else None):
            self.assertEqual(nachruesten.paketverwaltung(), "pacman")

    def test_apt_geht_vor(self) -> None:
        """Wo beides liegt, gewinnt apt – auf einem Debian mit
        nachinstalliertem pacman wäre pacman die falsche Wahl."""
        with mock.patch.object(nachruesten.sys, "platform", "linux"), \
                mock.patch.object(
                    nachruesten.shutil, "which",
                    side_effect=lambda w: f"/usr/bin/{w}"):
            self.assertEqual(nachruesten.paketverwaltung(), "apt")

    def test_unter_windows_gibt_es_keine(self) -> None:
        with mock.patch.object(nachruesten.sys, "platform", "win32"):
            self.assertIsNone(nachruesten.paketverwaltung())


class BefehlTest(unittest.TestCase):
    """Was gleich ausgeführt wird, muss vorher lesbar dastehen."""

    def _mit(self, verwaltung: str):
        return mock.patch.object(
            nachruesten, "paketverwaltung", return_value=verwaltung)

    def test_debian_bekommt_apt_get(self) -> None:
        with self._mit("apt"):
            teile = nachruesten.befehl(nachruesten.BAUSTEINE)

        self.assertEqual(teile[:3], ["apt-get", "install", "-y"])
        self.assertIn("tesseract-ocr-deu", teile)
        self.assertIn("poppler-utils", teile)

    def test_arch_bekommt_pacman(self) -> None:
        with self._mit("pacman"):
            teile = nachruesten.befehl(nachruesten.BAUSTEINE)

        self.assertEqual(teile[:2], ["pacman", "-S"])
        self.assertIn("tesseract-data-deu", teile)

    def test_jedes_paket_nur_einmal(self) -> None:
        """Zwei Bausteine können auf dasselbe Paket zeigen. Zweimal
        dasselbe zu installieren wäre nicht falsch, sähe aber nach
        einem Fehler aus."""
        doppelt = (
            nachruesten.Baustein(
                name="A", wofuer="x", pruefen="a",
                pakete={"apt": ("gleich",)}),
            nachruesten.Baustein(
                name="B", wofuer="y", pruefen="b",
                pakete={"apt": ("gleich", "anders")}),
        )

        with self._mit("apt"):
            namen = nachruesten.paketnamen(doppelt)

        self.assertEqual(namen, ["gleich", "anders"])

    def test_als_liste_und_nicht_als_zeichenkette(self) -> None:
        """**Damit nichts durch eine Shell läuft.** Die Paketnamen
        stehen zwar fest im Modul – aber ein Befehl, der sich
        zusammenbauen lässt, wird irgendwann aus einer Datei
        zusammengebaut."""
        with self._mit("apt"):
            self.assertIsInstance(
                nachruesten.befehl(nachruesten.BAUSTEINE), list)

    def test_ohne_bekannte_verwaltung_kein_befehl(self) -> None:
        with mock.patch.object(
                nachruesten, "paketverwaltung", return_value=None):
            self.assertEqual(nachruesten.befehl(nachruesten.BAUSTEINE), [])


class AbtippenTest(unittest.TestCase):
    """Der Rückfallweg, wenn es keinen Knopf gibt."""

    def test_hinter_dem_befehl_klebt_kein_satzzeichen(self) -> None:
        """**Die Falle vom 2026-11-25.** In einer Meldung stand
        »… tesseract-ocr-deu, unter Arch: …«; Stephan markierte den
        Befehl, kopierte das Komma mit und bekam »Paket
        tesseract-ocr-deu, kann nicht gefunden werden«.
        """
        with mock.patch.object(
                nachruesten, "paketverwaltung", return_value="apt"):
            zeile = nachruesten.zum_abtippen(nachruesten.BAUSTEINE)

        self.assertTrue(zeile.startswith("sudo apt-get install"))
        for zeichen in (",", ";", "."):
            self.assertFalse(
                zeile.rstrip().endswith(zeichen),
                f"Der Befehl endet auf »{zeichen}«: {zeile}",
            )

    def test_ohne_etwas_zu_tun_bleibt_es_leer(self) -> None:
        with mock.patch.object(
                nachruesten, "paketverwaltung", return_value="apt"):
            self.assertEqual(nachruesten.zum_abtippen([]), "")


class WarumNichtTest(unittest.TestCase):
    """**Was nicht geht, wird gesagt statt verschwiegen.**

    Ein Knopf, der nichts tut, ist schlimmer als keiner – und ein
    fehlender Knopf ohne Begründung lässt den Anwender raten.
    """

    def test_unter_windows_bringt_die_exe_alles_mit(self) -> None:
        with mock.patch.object(nachruesten.sys, "platform", "win32"):
            grund = nachruesten.warum_nicht()

        self.assertIn("MailBurg.exe", grund)

    def test_im_flatpak_geht_es_nicht(self) -> None:
        with mock.patch.object(nachruesten.sys, "platform", "linux"), \
                mock.patch.object(nachruesten, "_im_flatpak",
                                  return_value=True):
            grund = nachruesten.warum_nicht()

        self.assertIn("Flatpak", grund)

    def test_ohne_pkexec_kein_knopf(self) -> None:
        """PolicyKit bringt den Passwortdialog mit; ohne das darf kein
        Programm etwas installieren."""
        with mock.patch.object(nachruesten.sys, "platform", "linux"), \
                mock.patch.object(nachruesten, "_im_flatpak",
                                  return_value=False), \
                mock.patch.object(nachruesten, "paketverwaltung",
                                  return_value="apt"), \
                mock.patch.object(nachruesten.shutil, "which",
                                  return_value=None):
            grund = nachruesten.warum_nicht()

        self.assertIn("pkexec", grund)

    def test_bei_unbekannter_verwaltung_steht_welche_bekannt_sind(self) -> None:
        with mock.patch.object(nachruesten.sys, "platform", "linux"), \
                mock.patch.object(nachruesten, "_im_flatpak",
                                  return_value=False), \
                mock.patch.object(nachruesten, "paketverwaltung",
                                  return_value=None):
            grund = nachruesten.warum_nicht()

        for bekannt in ("apt", "pacman", "dnf", "zypper"):
            self.assertIn(bekannt, grund)

    def test_wenn_alles_da_ist_bleibt_es_leer(self) -> None:
        with mock.patch.object(nachruesten.sys, "platform", "linux"), \
                mock.patch.object(nachruesten, "_im_flatpak",
                                  return_value=False), \
                mock.patch.object(nachruesten, "paketverwaltung",
                                  return_value="apt"), \
                mock.patch.object(nachruesten.shutil, "which",
                                  return_value="/usr/bin/pkexec"):
            self.assertEqual(nachruesten.warum_nicht(), "")


class ImTerminalTest(unittest.TestCase):
    """Der Lauf im sichtbaren Terminal.

    **Der erste Entwurf nahm ``pkexec``** – ein grafischer
    Passwortdialog, und dahinter läuft etwas, das niemand sieht.
    Stephans Einwand vom 2026-11-25 wiegt schwerer: Im Terminal sieht
    der Anwender, was installiert wird, und bei einem Fehler steht die
    Ursache da statt in einem Rückgabewert.
    """

    def _baustein(self, name="Texterkennung"):
        return nachruesten.Baustein(
            name=name, wofuer="x" * 40, pruefen="tesseract",
            pakete={"apt": ("tesseract-ocr",)})

    def test_der_befehl_laeuft_mit_sudo_im_terminal(self) -> None:
        with mock.patch.object(nachruesten, "paketverwaltung",
                               return_value="apt"), \
                mock.patch.object(nachruesten, "terminal",
                                  return_value=("/usr/bin/xterm", "-e")), \
                mock.patch.object(nachruesten.subprocess, "Popen") as popen:
            nachruesten.im_terminal([self._baustein()], "/tmp/marke")

        aufruf = popen.call_args[0][0]
        self.assertEqual(aufruf[0], "/usr/bin/xterm")
        self.assertIn("sudo apt-get install", aufruf[-1])

    def test_am_ende_entsteht_die_fertigmarke(self) -> None:
        """**Daran erkennt MailBurg das Ende, nicht am Prozess.**

        ``gnome-terminal`` kehrt sofort zurück, weil es die Arbeit an
        einen laufenden Server weiterreicht – wer auf diesen Prozess
        wartet, wartet nicht. Eine Datei verhält sich bei jedem
        Terminal gleich.
        """
        with mock.patch.object(nachruesten, "paketverwaltung",
                               return_value="apt"), \
                mock.patch.object(nachruesten, "terminal",
                                  return_value=("/usr/bin/xterm", "-e")), \
                mock.patch.object(nachruesten.subprocess, "Popen") as popen:
            nachruesten.im_terminal([self._baustein()], "/tmp/marke mit raum")

        innen = popen.call_args[0][0][-1]
        self.assertIn("echo $?", innen)
        # Ein Pfad mit Leerzeichen darf die Shell nicht zerlegen.
        self.assertIn("'/tmp/marke mit raum'", innen)

    def test_ohne_terminal_passiert_nichts(self) -> None:
        with mock.patch.object(nachruesten, "paketverwaltung",
                               return_value="apt"), \
                mock.patch.object(nachruesten, "terminal", return_value=None):
            self.assertIsNone(
                nachruesten.im_terminal([self._baustein()], "/tmp/m"))

    def test_debian_wird_zuerst_gefragt(self) -> None:
        """``x-terminal-emulator`` zeigt über das Alternativen-System
        auf das Terminal, das der Anwender wirklich benutzt."""
        self.assertEqual(nachruesten.TERMINALS[0][0], "x-terminal-emulator")


class ErgebnisTest(unittest.TestCase):
    """Ob es geklappt hat – am Rechner nachgesehen."""

    def _baustein(self, da: bool):
        baustein = nachruesten.Baustein(
            name="Texterkennung", wofuer="x" * 40, pruefen="tesseract",
            pakete={"apt": ("tesseract-ocr",)})
        return mock.patch.object(
            type(baustein), "da", lambda self: da), baustein

    def test_erledigt_heisst_nachgesehen_und_nicht_geglaubt(self) -> None:
        """**``apt-get`` meldet auch dann Erfolg, wenn es nichts zu tun
        fand** – und ein Anwender kann die Passwortabfrage weggeklickt
        haben. Was zählt, ist allein, ob der Baustein jetzt da ist.
        """
        patch, baustein = self._baustein(da=True)
        with patch:
            geschafft, meldung = nachruesten.ergebnis([baustein])

        self.assertTrue(geschafft)
        self.assertIn("Erledigt", meldung)

    def test_was_fehlt_wird_beim_namen_genannt(self) -> None:
        patch, baustein = self._baustein(da=False)
        with patch, mock.patch.object(
                nachruesten, "paketverwaltung", return_value="apt"):
            geschafft, meldung = nachruesten.ergebnis([baustein])

        self.assertFalse(geschafft)
        self.assertIn("Texterkennung", meldung)

    def test_und_der_weg_von_hand_steht_dabei(self) -> None:
        """Ein Fehlschlag ohne Ausweg wäre eine Sackgasse."""
        patch, baustein = self._baustein(da=False)
        with patch, mock.patch.object(
                nachruesten, "paketverwaltung", return_value="apt"):
            _geschafft, meldung = nachruesten.ergebnis([baustein])

        self.assertIn("sudo apt-get install", meldung)


class BausteineTest(unittest.TestCase):
    """Die Tabelle selbst – sie ist der Kern dieses Moduls."""

    def test_jeder_baustein_kennt_alle_vier_verwaltungen(self) -> None:
        """Eine Lücke hier heißt: Auf diesem System gibt es keinen
        Knopf, und niemand merkt es beim Bauen."""
        for baustein in nachruesten.BAUSTEINE:
            for verwaltung in ("apt", "pacman", "dnf", "zypper"):
                with self.subTest(baustein=baustein.name, wo=verwaltung):
                    self.assertTrue(baustein.pakete.get(verwaltung))

    def test_jeder_sagt_wofuer(self) -> None:
        """**Ein Paketname ist keine Begründung.** Wer »tesseract-ocr«
        liest, weiß nicht, warum er es braucht."""
        for baustein in nachruesten.BAUSTEINE:
            with self.subTest(baustein=baustein.name):
                self.assertGreater(len(baustein.wofuer), 30)
                self.assertNotIn("tesseract", baustein.name.lower())

    def test_pyside6_steht_nicht_drin(self) -> None:
        """**Henne und Ei.** Ohne Qt gibt es kein Fenster, in dem ein
        Knopf stehen könnte. Dafür ist seit dem 2026-11-25 das
        ``Depends`` des Debian-Pakets da."""
        alle = " ".join(
            " ".join(sum(b.pakete.values(), ())) for b in nachruesten.BAUSTEINE
        )
        self.assertNotIn("pyside", alle.lower())


try:
    from PySide6.QtWidgets import QApplication  # noqa: F401

    HAT_QT = True
except ImportError:  # pragma: no cover
    HAT_QT = False


@unittest.skipUnless(HAT_QT, "PySide6 fehlt")
class EingehaengtTest(unittest.TestCase):
    """**An jeder Stelle derselbe Dialog – und er wird auch gerufen.**

    Ein Dialog, den niemand aufruft, ist dasselbe wie keiner. Genau
    das war am 2026-10-09 der Fall: ``core/erkennung.py`` sagte seit
    jeher »nach jedem Abruf«, und der Dienst rief es nie auf. Fünf
    Wochen lang blieb auf jedem Server jeder Scan stumm, und alle
    Tests waren grün – sie prüften die Funktion, nicht den Weg zu ihr.
    """

    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_der_assistent_fragt_vor_der_einrichtung(self) -> None:
        """**Die beste Stelle im ganzen Programm.** Wer MailBurg zum
        ersten Mal startet, soll nicht auf halbem Weg merken, dass
        die Hälfte nicht geht."""
        from mailburg.ui import assistent

        gerufen = []
        with mock.patch("mailburg.ui.nachruesten.fehlendes_nachruesten",
                        side_effect=lambda *a, **k: gerufen.append(True)):
            assistent.WillkommenSeite().validatePage()

        self.assertTrue(gerufen, "Der Assistent fragt nicht nach.")

    def test_ein_abbruch_haelt_den_assistenten_nicht_auf(self) -> None:
        """Ohne Texterkennung ist MailBurg benutzbar – nur
        eingescannte PDF bleiben unauffindbar. Wer ablehnt, hat das
        gelesen und entschieden; ihn dann nicht weiterzulassen wäre
        eine Strafe für eine zulässige Wahl."""
        from mailburg.ui import assistent

        with mock.patch("mailburg.ui.nachruesten.fehlendes_nachruesten",
                        return_value=False):
            self.assertTrue(assistent.WillkommenSeite().validatePage())

    def test_die_texterkennung_fragt_vor_dem_lauf(self) -> None:
        """**Die Stelle, an der der ganze Befund anfing.** Bis zum
        2026-11-25 lief der Durchgang los, las null Dokumente und
        schrieb darunter klein, dass tesseract fehle."""
        import inspect

        from mailburg.ui import texterkennung

        quelle = inspect.getsource(texterkennung.Texterkennungsdialog._starten)

        self.assertIn("fehlendes_nachruesten", quelle)
        # Vor dem Läufer, nicht danach: Sonst liest er erst null
        # Dokumente und fragt hinterher.
        self.assertLess(quelle.index("fehlendes_nachruesten"),
                        quelle.index("Erkennungslauf"))


if __name__ == "__main__":
    unittest.main()
