"""Der dritte Weg aus dem Archiv: »In Mailprogramm öffnen«.

Geprüft wird weniger das Öffnen – das tut das Betriebssystem – als
das, was dabei auf der Platte zurückbleibt. Eine ``.eml`` ist die
vollständige Nachricht mit Anhängen und Adressen; wo sie liegt und wann
sie verschwindet, ist bei einem Archivprogramm kein Detail.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from mailburg.core import paths, rueckgabe

MAIL = (
    b"From: Bauhof Nordwest <buchhaltung@bauhof-nordwest.example>\r\n"
    b"To: Martha Muster <martha@mailburg.example>\r\n"
    b"Subject: Rechnung 0417\r\n"
    b"Date: Mon, 12 May 2025 09:14:00 +0000\r\n"
    b"\r\n"
    b"Guten Tag,\r\n"
)


class OrtTest(unittest.TestCase):
    """Wo die Datei liegt – und wer hineinsehen darf."""

    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.patch = mock.patch.dict(
            os.environ, {"XDG_CACHE_HOME": self.ordner.name}
        )
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_nicht_im_allgemeinen_tmp(self):
        """Dort darf auf einem Mehrbenutzersystem jeder mitlesen."""
        wo = paths.geoeffnet_dir()

        self.assertNotIn(wo, (Path("/tmp"), Path("/var/tmp")))
        self.assertTrue(wo.is_dir())

    @unittest.skipIf(sys.platform == "win32", "Rechte gibt es dort anders")
    def test_der_ordner_gehoert_nur_dem_benutzer(self):
        wo = paths.geoeffnet_dir()

        self.assertEqual(wo.stat().st_mode & 0o777, 0o700)

    @unittest.skipIf(sys.platform == "win32", "Rechte gibt es dort anders")
    def test_auch_ein_alter_ordner_wird_geschuetzt(self):
        """Er kann aus einer Fassung stammen, die das noch nicht tat."""
        wo = paths.geoeffnet_dir()
        wo.chmod(0o755)

        self.assertEqual(paths.geoeffnet_dir().stat().st_mode & 0o777, 0o700)


class AblegenTest(unittest.TestCase):
    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.patch = mock.patch.dict(
            os.environ, {"XDG_CACHE_HOME": self.ordner.name}
        )
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.uebergeben = mock.patch.object(rueckgabe, "_dem_system_uebergeben")
        self.aufruf = self.uebergeben.start()
        self.addCleanup(self.uebergeben.stop)

    def test_die_mail_liegt_bytegenau_da(self):
        """Verändert würde sie sonst zwischen Archiv und Mailprogramm."""
        datei = rueckgabe.im_mailprogramm_oeffnen(MAIL, "Rechnung 0417")

        self.assertEqual(datei.read_bytes(), MAIL)
        self.aufruf.assert_called_once_with(datei)

    def test_der_betreff_steht_im_namen(self):
        """Sonst steht »tmp8f2a.eml« im Fenstertitel des Mailprogramms."""
        datei = rueckgabe.im_mailprogramm_oeffnen(MAIL, "Rechnung 0417")

        self.assertTrue(datei.name.startswith("Rechnung 0417-"))
        self.assertEqual(datei.suffix, ".eml")

    def test_zwei_gleiche_betreffs_ueberschreiben_sich_nicht(self):
        """Beide können gleichzeitig offen sein."""
        erste = rueckgabe.im_mailprogramm_oeffnen(MAIL, "Rechnung")
        zweite = rueckgabe.im_mailprogramm_oeffnen(MAIL, "Rechnung")

        self.assertNotEqual(erste, zweite)
        self.assertTrue(erste.is_file())
        self.assertTrue(zweite.is_file())

    def test_ein_betreff_mit_schraegstrich_geht_auch(self):
        """»Re: 12/2025« wäre sonst ein Pfad statt eines Namens."""
        datei = rueckgabe.im_mailprogramm_oeffnen(MAIL, 'Re: 12/2025 <"?>')

        self.assertEqual(datei.parent, paths.geoeffnet_dir())
        self.assertTrue(datei.is_file())

    def test_ohne_betreff_bekommt_sie_trotzdem_einen_namen(self):
        datei = rueckgabe.im_mailprogramm_oeffnen(MAIL, "")

        self.assertTrue(datei.name.startswith("Nachricht-"))

    @unittest.skipIf(sys.platform == "win32", "Rechte gibt es dort anders")
    def test_die_datei_gehoert_nur_dem_benutzer(self):
        datei = rueckgabe.im_mailprogramm_oeffnen(MAIL, "Rechnung")

        self.assertEqual(datei.stat().st_mode & 0o777, 0o600)


class AufraeumenTest(unittest.TestCase):
    """Sie muss auch wieder verschwinden."""

    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.patch = mock.patch.dict(
            os.environ, {"XDG_CACHE_HOME": self.ordner.name}
        )
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.uebergeben = mock.patch.object(rueckgabe, "_dem_system_uebergeben")
        self.uebergeben.start()
        self.addCleanup(self.uebergeben.stop)

    def test_frisches_bleibt_beim_naechsten_oeffnen_liegen(self):
        """Das Mailprogramm liest sie womöglich noch."""
        erste = rueckgabe.im_mailprogramm_oeffnen(MAIL, "Erste")
        rueckgabe.im_mailprogramm_oeffnen(MAIL, "Zweite")

        self.assertTrue(erste.is_file())

    def test_altes_wird_beim_naechsten_oeffnen_weggeraeumt(self):
        alt = rueckgabe.im_mailprogramm_oeffnen(MAIL, "Vorgestern")
        # Fünf Stunden zurückdatieren – über der Haltbarkeit.
        vorher = time.time() - rueckgabe.HALTBARKEIT - 3600
        os.utime(alt, (vorher, vorher))

        rueckgabe.im_mailprogramm_oeffnen(MAIL, "Jetzt")

        self.assertFalse(alt.exists())

    def test_beim_beenden_geht_alles(self):
        erste = rueckgabe.im_mailprogramm_oeffnen(MAIL, "Erste")
        zweite = rueckgabe.im_mailprogramm_oeffnen(MAIL, "Zweite")

        weg = rueckgabe.aufraeumen_beim_beenden()

        self.assertEqual(weg, 2)
        self.assertFalse(erste.exists())
        self.assertFalse(zweite.exists())

    def test_fremde_dateien_bleiben_unangetastet(self):
        """Der Ordner gehört MailBurg – aber Vorsicht kostet nichts."""
        rueckgabe.im_mailprogramm_oeffnen(MAIL, "Meine")
        fremd = paths.geoeffnet_dir() / "notizen.txt"
        fremd.write_text("nicht von uns", encoding="utf-8")

        rueckgabe.aufraeumen_beim_beenden()

        self.assertTrue(fremd.is_file())

    def test_ein_gesperrtes_stueck_bricht_nichts_ab(self):
        """Unter Windows hält das Mailprogramm die Datei offen."""
        erste = rueckgabe.im_mailprogramm_oeffnen(MAIL, "Offen")
        zweite = rueckgabe.im_mailprogramm_oeffnen(MAIL, "Zu")

        echtes_unlink = Path.unlink

        def klemmt(self, *args, **kwargs):
            if self == erste:
                raise PermissionError("wird gerade gelesen")
            return echtes_unlink(self, *args, **kwargs)

        with mock.patch.object(Path, "unlink", klemmt):
            weg = rueckgabe.aufraeumen_beim_beenden()

        self.assertEqual(weg, 1)
        self.assertFalse(zweite.exists())


class SystemuebergabeTest(unittest.TestCase):
    """Wie die Datei an das System weitergereicht wird."""

    @unittest.skipIf(sys.platform == "win32", "dort ist es os.startfile")
    def test_ohne_xdg_open_kommt_eine_erklaerung(self):
        """Auf schlanken Arbeitsumgebungen fehlt es – mit Rat, nicht mit Absturz."""
        with mock.patch.object(
            rueckgabe.subprocess, "Popen", side_effect=OSError("nicht da")
        ):
            with self.assertRaises(rueckgabe.RueckgabeFehler) as gefangen:
                rueckgabe._dem_system_uebergeben(Path("/tmp/x.eml"))

        self.assertIn("xdg-utils", str(gefangen.exception))

    @unittest.skipIf(sys.platform == "win32", "dort ist es os.startfile")
    def test_keine_shell(self):
        """Ein Dateiname darf nicht als Befehl gelesen werden können."""
        with mock.patch.object(rueckgabe.subprocess, "Popen") as popen:
            rueckgabe._dem_system_uebergeben(Path("/tmp/Rechnung; rm -rf ~.eml"))

        argumente, benannt = popen.call_args
        self.assertIsInstance(argumente[0], list)
        self.assertNotIn("shell", benannt)


if __name__ == "__main__":
    unittest.main()


class AnhangOeffnenTest(unittest.TestCase):
    """Der Anhang einer Mail, wenn man ihn zum Ansehen öffnet.

    **Bis zum 2026-09-03 ging er nach /tmp und blieb dort liegen.**
    ``ui/vorschau.py`` legte ihn mit ``mkdtemp`` ab und räumte nie auf.
    Für die vollständige Mail daneben war seit jeher begründet, warum
    sie dort nicht hingehört – für den PDF-Anhang derselben Mail galt
    dieselbe Begründung, nur tat es niemand.

    Ein Anhang aus einem Geschäftsarchiv ist eine Rechnung, ein
    Vertrag, ein Arztbericht.
    """

    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        patch = mock.patch.dict(
            os.environ, {"XDG_CACHE_HOME": self.ordner.name}
        )
        patch.start()
        self.addCleanup(patch.stop)

        # Das System soll im Test nichts starten.
        uebergeben = mock.patch.object(rueckgabe, "_dem_system_uebergeben")
        self.uebergeben = uebergeben.start()
        self.addCleanup(uebergeben.stop)

    def test_liegt_im_geschuetzten_ordner_neben_den_mails(self):
        # Nicht mehr in einem eigenen mkdtemp-Verzeichnis: Das lag in
        # /tmp, wo auf einem Mehrbenutzersystem jeder mitlesen darf, und
        # es blieb liegen. (Im Test zeigt XDG_CACHE_HOME selbst nach
        # /tmp - deshalb wird hier der Ordner verglichen, nicht der Pfad.)
        ziel = rueckgabe.anhang_oeffnen(b"%PDF-1.4", "Rechnung.pdf")

        self.assertEqual(ziel.parent, paths.geoeffnet_dir())

    def test_jeder_anhang_bekommt_kein_eigenes_verzeichnis(self):
        # Der alte Weg legte je Anhang ein mkdtemp-Verzeichnis an, das
        # niemand je wieder entfernte.
        eine = rueckgabe.anhang_oeffnen(b"eins", "A.pdf")
        andere = rueckgabe.anhang_oeffnen(b"zwei", "B.pdf")

        self.assertEqual(eine.parent, andere.parent)

    @unittest.skipIf(sys.platform == "win32", "Rechte gibt es dort anders")
    def test_nur_der_benutzer_darf_hineinsehen(self):
        ziel = rueckgabe.anhang_oeffnen(b"%PDF-1.4", "Rechnung.pdf")

        self.assertEqual(ziel.stat().st_mode & 0o777, 0o600)

    def test_die_endung_bleibt_erhalten(self):
        # Ohne sie weiß das System nicht, womit es die Datei öffnen soll.
        ziel = rueckgabe.anhang_oeffnen(b"%PDF-1.4", "Rechnung.pdf")

        self.assertEqual(ziel.suffix, ".pdf")

    def test_der_inhalt_kommt_unveraendert_an(self):
        ziel = rueckgabe.anhang_oeffnen(b"%PDF-1.4\nInhalt", "Rechnung.pdf")

        self.assertEqual(ziel.read_bytes(), b"%PDF-1.4\nInhalt")

    def test_zwei_gleichnamige_anhaenge_ueberschreiben_sich_nicht(self):
        # Zwei Rechnungen aus verschiedenen Mails, beide "Rechnung.pdf",
        # beide zugleich offen.
        eine = rueckgabe.anhang_oeffnen(b"eins", "Rechnung.pdf")
        andere = rueckgabe.anhang_oeffnen(b"zwei", "Rechnung.pdf")

        self.assertNotEqual(eine, andere)
        self.assertEqual(eine.read_bytes(), b"eins")
        self.assertEqual(andere.read_bytes(), b"zwei")

    def test_ein_anhang_ohne_namen_bekommt_einen(self):
        ziel = rueckgabe.anhang_oeffnen(b"daten", "")

        self.assertTrue(ziel.name)
        self.assertTrue(ziel.is_file())

    def test_beim_beenden_ist_er_weg(self):
        ziel = rueckgabe.anhang_oeffnen(b"%PDF-1.4", "Rechnung.pdf")
        self.assertTrue(ziel.is_file())

        rueckgabe.aufraeumen_beim_beenden()

        self.assertFalse(
            ziel.is_file(),
            "ein Anhang aus einem Geschäftsarchiv darf nicht liegen bleiben",
        )

    def test_nach_vier_stunden_raeumt_ihn_der_naechste_auf(self):
        alt = rueckgabe.anhang_oeffnen(b"%PDF-1.4", "Alt.pdf")
        vorgestern = time.time() - rueckgabe.HALTBARKEIT - 60
        os.utime(alt, (vorgestern, vorgestern))

        rueckgabe.anhang_oeffnen(b"%PDF-1.4", "Neu.pdf")

        self.assertFalse(alt.is_file())

    def test_fremdes_bleibt_auch_hier_liegen(self):
        rueckgabe.anhang_oeffnen(b"%PDF-1.4", "Rechnung.pdf")
        fremd = paths.geoeffnet_dir() / "notizen.txt"
        fremd.write_text("nicht von uns", encoding="utf-8")

        rueckgabe.aufraeumen_beim_beenden()

        self.assertTrue(fremd.is_file())
