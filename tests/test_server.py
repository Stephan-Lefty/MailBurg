"""Der Dienst der Server Edition.

Vorerst nur eine Seite, die »läuft« sagt – und genau darum geht es:
Ein Dienst hat mehr Fragen zu klären als eine Funktion. Unter welchem
Benutzer er läuft, wo seine Einstellungen stehen, was er meldet, wenn
etwas fehlt. Diese Antworten werden hier festgehalten, bevor Funktion
dazukommt.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mailburg.core.archive import Archive, Mode
from mailburg.core.benutzer import Benutzer
from mailburg.server import einstellungen as lage
from mailburg.server.dienst import FELDER, _zustand, seite

WURZEL = Path(__file__).resolve().parent.parent


class UmgebungTest(unittest.TestCase):
    """Ein Dienst hat niemanden, den er fragen kann."""

    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.wo = Path(self.ordner.name) / "Archiv"
        Archive.create(self.wo, name="Probe", mode=Mode.GESCHAEFTLICH).close()

        leer = mock.patch.dict(
            os.environ,
            {lage.ARCHIV: "", lage.ADRESSE: "", lage.ANSCHLUSS: ""},
        )
        leer.start()
        self.addCleanup(leer.stop)

    def test_ohne_archiv_startet_er_nicht(self):
        with self.assertRaises(lage.Fehlt) as gefangen:
            lage.Serverlage.aus_umgebung()

        self.assertIn(lage.ARCHIV, str(gefangen.exception))

    def test_ein_ordner_ohne_archiv_wird_erkannt(self):
        """Sonst startete der Dienst und fiele erst beim ersten Zugriff um."""
        os.environ[lage.ARCHIV] = self.ordner.name

        with self.assertRaises(lage.Fehlt):
            lage.Serverlage.aus_umgebung()

    def test_mit_archiv_geht_es(self):
        os.environ[lage.ARCHIV] = str(self.wo)

        gelesen = lage.Serverlage.aus_umgebung()
        self.assertEqual(gelesen.archiv, self.wo)

    def test_die_vorgabe_ist_der_eigene_rechner(self):
        """Ein Dienst, der beim ersten Start im ganzen Netz lauscht,
        wäre eine böse Überraschung."""
        os.environ[lage.ARCHIV] = str(self.wo)

        gelesen = lage.Serverlage.aus_umgebung()
        self.assertEqual(gelesen.adresse, "127.0.0.1")
        self.assertFalse(gelesen.oeffentlich)

    def test_eine_andere_adresse_gilt_als_oeffentlich(self):
        os.environ[lage.ARCHIV] = str(self.wo)
        os.environ[lage.ADRESSE] = "0.0.0.0"  # noqa: S104 – genau darum geht es

        self.assertTrue(lage.Serverlage.aus_umgebung().oeffentlich)

    def test_ein_unsinniger_port(self):
        os.environ[lage.ARCHIV] = str(self.wo)
        for wert in ("achtzig", "0", "70000", "-1"):
            os.environ[lage.ANSCHLUSS] = wert
            with self.subTest(port=wert):
                with self.assertRaises(lage.Fehlt):
                    lage.Serverlage.aus_umgebung()


class ZustandTest(unittest.TestCase):
    """Was die Seite zeigt – und woran sie erinnert."""

    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.wo = Path(self.ordner.name) / "Archiv"
        self.archiv = Archive.create(
            self.wo, name="Geschäftsarchiv", mode=Mode.GESCHAEFTLICH
        )
        self.archiv.add(
            b"From: a@example.org\r\nSubject: Test\r\n\r\nText\r\n",
            account="buchhaltung", folder="INBOX",
        )
        self.archiv.close()

        leer = mock.patch.dict(
            os.environ,
            {"MAILBURG_SCHLUESSEL": "", "MAILBURG_SCHLUESSELDATEI": "",
             "XDG_CONFIG_HOME": self.ordner.name},
        )
        leer.start()
        self.addCleanup(leer.stop)

        self.lage = lage.Serverlage(archiv=self.wo)

    def test_der_bericht_nennt_das_archiv(self):
        bericht = _zustand(self.lage)

        self.assertEqual(bericht["name"], "Geschäftsarchiv")
        self.assertEqual(bericht["mails"], 1)
        self.assertEqual(bericht["postfaecher"], 1)

    def test_ohne_zugang_wird_erinnert(self):
        bericht = _zustand(self.lage)

        self.assertTrue(
            any("kein Zugang" in s for s in bericht["sorgen"]),
            bericht["sorgen"],
        )

    def test_ohne_tresor_wird_erinnert(self):
        """Der Dienst liefe sonst und holte nichts – ohne dass es auffällt."""
        bericht = _zustand(self.lage)

        self.assertTrue(
            any("Tresor" in s for s in bericht["sorgen"]), bericht["sorgen"]
        )

    def test_mit_zugang_und_verwalter_verschwindet_die_erinnerung(self):
        with Archive.open(self.wo) as archiv:
            liste = archiv.benutzer
            chef = Benutzer("chef", verwalter=True, alle_postfaecher=True)
            chef.passwort_setzen("ein-langes-passwort")
            liste.hinzufuegen(chef)
            archiv.benutzer_setzen(liste)

        bericht = _zustand(self.lage)

        self.assertEqual(bericht["zugaenge"], 1)
        self.assertEqual(bericht["verwalter"], 1)
        self.assertFalse(any("kein Zugang" in s for s in bericht["sorgen"]))

    def test_ein_zugang_ohne_verwalter_wird_gemeldet(self):
        with Archive.open(self.wo) as archiv:
            liste = archiv.benutzer
            liste.hinzufuegen(Benutzer("anna"))
            archiv.benutzer_setzen(liste)

        bericht = _zustand(self.lage)

        self.assertTrue(
            any("kein Verwalter" in s.lower() or "keinen Verwalter" in s
                for s in bericht["sorgen"]),
            bericht["sorgen"],
        )

    def test_oeffentliches_lauschen_wird_gemeldet(self):
        offen = lage.Serverlage(archiv=self.wo, adresse="0.0.0.0")  # noqa: S104

        bericht = _zustand(offen)

        self.assertTrue(
            any("VPN" in s or "Firewall" in s for s in bericht["sorgen"]),
            bericht["sorgen"],
        )

    def test_ein_kaputtes_archiv_bringt_die_seite_nicht_um(self):
        """Sie muss gerade dann antworten, wenn etwas nicht stimmt."""
        kaputt = lage.Serverlage(archiv=Path(self.ordner.name) / "gibt-es-nicht")

        bericht = _zustand(kaputt)

        self.assertTrue(bericht["sorgen"])
        self.assertIn("<html", seite(bericht))

    def test_die_seite_maskiert_sonderzeichen(self):
        """Der Archivname kommt aus einer Datei – er darf kein HTML sein."""
        bericht = _zustand(self.lage)
        bericht["name"] = "<script>alarm()</script>"

        self.assertNotIn("<script>", seite(bericht))
        self.assertIn("&lt;script&gt;", seite(bericht))

    def test_die_seite_zeigt_jedes_feld_das_da_ist(self):
        bericht = _zustand(self.lage)
        gebaut = seite(bericht)

        for schluessel, beschriftung in FELDER:
            if schluessel in bericht:
                with self.subTest(feld=schluessel):
                    self.assertIn(beschriftung, gebaut)


class SystemdTest(unittest.TestCase):
    """Die mitgelieferte Dienstvorlage.

    Sie lässt sich hier nicht ausführen – aber prüfen, dass die Zusagen
    darin stehen. Eine Vorlage, die als root läuft oder alles schreiben
    darf, wäre schlechter als keine.
    """

    def setUp(self):
        self.text = (WURZEL / "werkzeuge" / "mailburg-server.service").read_text(
            encoding="utf-8"
        )

    def test_nicht_als_root(self):
        self.assertIn("User=mailburg", self.text)
        self.assertNotIn("User=root", self.text)

    def test_der_dienst_kommt_nach_einem_absturz_wieder(self):
        self.assertIn("Restart=on-failure", self.text)
        self.assertIn("RestartSec=", self.text)

    def test_er_darf_nur_sein_eigenes_verzeichnis_beschreiben(self):
        self.assertIn("ProtectSystem=strict", self.text)
        self.assertIn("ReadWritePaths=/var/lib/mailburg", self.text)

    def test_der_hauptschluessel_kommt_ueber_loadcredential(self):
        """Dann steht er nicht im Dateisystem des Dienstes."""
        self.assertIn("LoadCredential=schluessel:", self.text)
        self.assertIn("MAILBURG_SCHLUESSELDATEI=%d/schluessel", self.text)

    def test_die_vorgabe_lauscht_nur_lokal(self):
        self.assertIn("MAILBURG_ADRESSE=127.0.0.1", self.text)


class WindowsDienstTest(unittest.TestCase):
    """Der Dienst unter Windows – geprüft am Quelltext, nicht im Betrieb.

    **Hier steht kein Windows-Rechner zur Verfügung.** Die Prüfung im
    Betrieb ist für Mitte Oktober 2026 verabredet; bis dahin ist dieser
    Teil geschrieben, aber nie gelaufen. Was sich ohne Windows prüfen
    lässt, ist, dass die Zusagen im Quelltext stehen – und dass der
    Rest von MailBurg nicht darüber stolpert.
    """

    def setUp(self):
        self.quelle = (
            WURZEL / "mailburg" / "server" / "windows_dienst.py"
        ).read_text(encoding="utf-8")

    def test_das_modul_laesst_sich_ohne_pywin32_laden(self):
        """Sonst brächte ein Import unter Linux alles zum Stehen."""
        from mailburg.server import windows_dienst

        self.assertIn(windows_dienst.HAT_PYWIN32, (True, False))

    def test_ohne_pywin32_gibt_es_eine_klare_ansage(self):
        from mailburg.server import windows_dienst

        if windows_dienst.HAT_PYWIN32:  # pragma: no cover – nur auf Windows
            self.skipTest("pywin32 ist vorhanden")

        self.assertEqual(windows_dienst.main([]), 2)

    def test_der_dienst_traegt_einen_namen_und_eine_beschreibung(self):
        """In services.msc steht sonst nur eine Kennung."""
        from mailburg.server import windows_dienst

        self.assertTrue(windows_dienst.NAME)
        self.assertTrue(windows_dienst.ANZEIGE)
        self.assertIn("MAILBURG_ARCHIV", windows_dienst.BESCHREIBUNG)

    def test_uvicorn_laeuft_in_einem_eigenen_faden(self):
        """Sonst könnte SvcStop nichts ausrichten.

        ``uvicorn.run()`` kehrt erst zurück, wenn der Server endet – der
        Faden des Dienstes muss aber frei bleiben, um auf das
        Halte-Ereignis zu warten.
        """
        self.assertIn("threading.Thread", self.quelle)
        self.assertIn("WaitForSingleObject", self.quelle)

    def test_beim_beenden_wird_uvicorn_zuerst_bescheid_gesagt(self):
        """Andersherum endete der Prozess mitten in einer Anfrage."""
        stelle = self.quelle.index("def SvcStop")
        ende = self.quelle.index("def SvcDoRun")
        stop = self.quelle[stelle:ende]

        self.assertLess(stop.index("should_exit"), stop.index("SetEvent"))

    def test_fehler_gehen_ins_ereignisprotokoll(self):
        """Ein Dienst hat keine Konsole, auf die er schreiben könnte."""
        self.assertIn("LogErrorMsg", self.quelle)

    def test_der_vermerk_ueber_die_fehlende_pruefung_steht_da(self):
        """Er gilt, bis jemand es wirklich ausprobiert hat."""
        self.assertIn("Nicht geprüft", self.quelle)


if __name__ == "__main__":
    unittest.main()
