"""Der regelmäßige Abruf unter Windows.

Ausgeführt werden kann hier nichts – ``schtasks.exe`` gibt es unter
Linux nicht. Geprüft wird deshalb, was MailBurg der Aufgabenplanung
*vorlegt*: der Aufgabenname, die Beschreibung, der Befehl. Genau dort
saßen bisher alle Fehler dieser Art.

Das ist keine Förmlichkeit. Ein Zeitplan, der sich anlegen lässt und
nicht läuft, fällt niemandem auf: Es steht ja eine Aufgabe in der Liste.
Gemerkt hätte man es erst, wenn Post fehlt – und dann ist unklar, seit
wann.
"""

from __future__ import annotations

import pathlib
import sys
import unittest
from unittest import mock

from mailburg.core import aufgabenplanung as ap


class NamenTest(unittest.TestCase):
    """Jedes Archiv bekommt eine eigene Aufgabe."""

    def test_der_ordner_steht_vorn(self) -> None:
        """Damit man in der Aufgabenplanung findet, was MailBurg anlegte."""
        name = ap._aufgabenname("Abruf", pathlib.Path("/tmp/Privatarchiv"))
        self.assertTrue(name.startswith("MailBurg\\"))

    def test_zwei_archive_zwei_aufgaben(self) -> None:
        """Sonst überschreibt das zweite Archiv den Zeitplan des ersten.

        Genau dieser Fehler steckte in der Linux-Fassung: Wer
        geschäftlich und privat trennt, hatte am Ende nur noch ein
        beliefertes Archiv – und merkte es erst, wenn dort etwas fehlte.
        """
        privat = ap._aufgabenname("Abruf", pathlib.Path("/tmp/Privatarchiv"))
        firma = ap._aufgabenname("Abruf", pathlib.Path("/tmp/Geschaeftlich"))
        self.assertNotEqual(privat, firma)

    def test_abruf_und_sicherung_kommen_sich_nicht_ins_gehege(self) -> None:
        archiv = pathlib.Path("/tmp/Archiv")
        self.assertNotEqual(
            ap._aufgabenname("Abruf", archiv),
            ap._aufgabenname("Sicherung", archiv),
        )

    def test_sonderzeichen_werden_entschaerft(self) -> None:
        """Ein Ordnername darf alles – ein Aufgabenname nicht."""
        name = ap._aufgabenname("Abruf", pathlib.Path("/tmp/Post: 2026/alt"))
        # Nur der eine Trenner, den die Aufgabenplanung selbst setzt.
        self.assertEqual(name.count("\\"), 1)
        for zeichen in ':*?"<>|':
            with self.subTest(zeichen=zeichen):
                self.assertNotIn(zeichen, name)


class BeschreibungTest(unittest.TestCase):
    """Was in der XML-Datei stehen muss."""

    def _abruf(self, takt: int = 30) -> str:
        return ap._xml(
            "Test", r"C:\MailBurg.exe", r'abrufen --leise "C:\Archiv"',
            wiederholung=f"PT{takt}M",
        )

    def test_verpasste_laeufe_werden_nachgeholt(self) -> None:
        """Das Gegenstück zu systemds ``Persistent=true``.

        Ohne das fällt eine tägliche Sicherung schlicht aus, wenn der
        Rechner zur fraglichen Zeit ausgeschaltet war – stillschweigend.
        """
        self.assertIn("<StartWhenAvailable>true</StartWhenAvailable>",
                      self._abruf())

    def test_nur_bei_angemeldetem_benutzer(self) -> None:
        """Sonst kommt der Abruf an kein einziges Passwort heran.

        Die Passwörter liegen in der Anmeldeinformationsverwaltung, und
        die öffnet sich erst mit der Anmeldung. Eine Aufgabe im
        Dienstkontext liefe zwar – aber jedes Mal vergeblich.
        """
        self.assertIn("InteractiveToken", self._abruf())

    def test_ohne_verwaltungsrechte(self) -> None:
        self.assertIn("LeastPrivilege", self._abruf())

    def test_der_abruf_ueberholt_sich_nicht_selbst(self) -> None:
        """Ein Durchgang darf länger dauern als der Abstand.

        Der erste Abruf eines gewachsenen Postfachs lief bei Stephan
        60 Minuten – bei 30 Minuten Takt hätten sich sonst zwei
        Durchgänge überlagert.
        """
        self.assertIn("<MultipleInstancesPolicy>IgnoreNew", self._abruf())

    def test_der_takt_landet_in_der_datei(self) -> None:
        self.assertIn("<Interval>PT15M</Interval>", self._abruf(15))

    def test_im_akkubetrieb_laeuft_es_weiter(self) -> None:
        """Ein Notebook soll seine Post auch ohne Steckdose holen."""
        self.assertIn("<DisallowStartIfOnBatteries>false", self._abruf())
        self.assertIn("<StopIfGoingOnBatteries>false", self._abruf())

    def test_die_sicherung_bekommt_einen_tagesplan(self) -> None:
        xml = ap._xml("Test", r"C:\MailBurg.exe", "sichern", taeglich=7)
        self.assertIn("<DaysInterval>7</DaysInterval>", xml)
        self.assertNotIn("<Repetition>", xml)

    def test_sonderzeichen_im_pfad_zerlegen_die_datei_nicht(self) -> None:
        """Ein ``&`` im Ordnernamen wäre sonst ungültiges XML.

        »Rechnungen & Belege« ist ein völlig gewöhnlicher Ordnername.
        Ohne Maskierung hätte die Aufgabenplanung die Datei abgelehnt –
        mit einer Meldung, die den Grund nicht nennt.
        """
        xml = ap._xml(
            "Test", r"C:\MailBurg.exe",
            r'sichern "C:\Rechnungen & Belege"',
        )
        self.assertIn("&amp;", xml)
        self.assertNotIn("& Belege", xml)

        from xml.etree import ElementTree

        ElementTree.fromstring(xml.split("?>", 1)[1])

    def test_die_datei_ist_gueltiges_xml(self) -> None:
        from xml.etree import ElementTree

        ElementTree.fromstring(self._abruf().split("?>", 1)[1])


class BefehlTest(unittest.TestCase):
    """Womit der Abruf gestartet wird."""

    def test_die_gepackte_fassung_ruft_sich_selbst(self) -> None:
        with mock.patch.object(sys, "frozen", True, create=True):
            with mock.patch.object(sys, "executable", r"C:\MailBurg.exe"):
                programm, vorspann = ap._befehl()

        self.assertEqual(programm, r"C:\MailBurg.exe")
        # Sie *ist* MailBurg - kein "-m mailburg" davor.
        self.assertEqual(vorspann, "")

    def test_sonst_laeuft_es_ueber_python(self) -> None:
        with mock.patch.object(sys, "frozen", False, create=True):
            programm, vorspann = ap._befehl()

        self.assertEqual(vorspann, "-m mailburg")
        self.assertTrue(programm)

    def test_lieber_pythonw_als_python(self) -> None:
        """Sonst blitzt alle 30 Minuten ein schwarzes Fenster auf.

        Bei einem Programm, das im Hintergrund arbeiten soll, ist das
        kein Schönheitsfehler – es sieht nach Fehlfunktion aus, und
        irgendwann schaltet jemand den Zeitplan deswegen ab.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as ordner:
            deuter = pathlib.Path(ordner) / "python.exe"
            deuter.touch()
            (pathlib.Path(ordner) / "pythonw.exe").touch()

            with mock.patch.object(sys, "frozen", False, create=True):
                with mock.patch.object(sys, "executable", str(deuter)):
                    programm, _ = ap._befehl()

        self.assertTrue(programm.endswith("pythonw.exe"))


class WeicheTest(unittest.TestCase):
    """``zeitplan`` muss unter Windows hierher abbiegen.

    Bis zum 2026-08-28 tat es das nicht: Es stand nur ein grauer Kasten
    mit dem Satz »Unter Windows richtet MailBurg den regelmäßigen Abruf
    noch nicht selbst ein«. Stephan hat ihn zwei Tage hintereinander
    gesehen.
    """

    def test_windows_gilt_nicht_mehr_als_unmoeglich(self) -> None:
        from mailburg.core import zeitplan

        with mock.patch.object(zeitplan, "_windows", return_value=True):
            with mock.patch.object(ap, "moeglich", return_value=(True, "")):
                geht, grund = zeitplan.moeglich()

        self.assertTrue(geht, grund)
        self.assertEqual(grund, "")

    def test_der_alte_hinweis_ist_fort(self) -> None:
        quelle = (
            pathlib.Path(__file__).resolve().parent.parent
            / "mailburg" / "core" / "zeitplan.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("noch nicht selbst ein", quelle)

    def test_einrichten_geht_an_die_aufgabenplanung(self) -> None:
        import tempfile

        from mailburg.core import zeitplan

        with tempfile.TemporaryDirectory() as ordner:
            archiv = pathlib.Path(ordner)
            (archiv / "archive.json").write_text("{}", encoding="utf-8")

            with mock.patch.object(zeitplan, "_windows", return_value=True):
                with mock.patch.object(ap, "moeglich", return_value=(True, "")):
                    with mock.patch.object(
                        ap, "einrichten", return_value=(True, "ok")
                    ) as gerufen:
                        zeitplan.einrichten(archiv, 15)

        gerufen.assert_called_once()
        self.assertEqual(gerufen.call_args[0][1], 15)

    def test_die_haltung_wird_nur_an_einer_stelle_entschieden(self) -> None:
        """Ersetzen oder sammeln – die Regel steht in ``zeitplan``.

        Stünde sie zweimal da, liefen Linux und Windows irgendwann
        auseinander, und die Sicherung täte auf einem der beiden Systeme
        etwas anderes, als der Anwender eingestellt hat.
        """
        quelle = (
            pathlib.Path(__file__).resolve().parent.parent
            / "mailburg" / "core" / "aufgabenplanung.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("--ersetzen", quelle)
        self.assertNotIn("--behalten", quelle)


if __name__ == "__main__":
    unittest.main()
