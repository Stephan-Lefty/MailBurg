"""Der Dienst der Server Edition.

Vorerst nur eine Seite, die »läuft« sagt – und genau darum geht es:
Ein Dienst hat mehr Fragen zu klären als eine Funktion. Unter welchem
Benutzer er läuft, wo seine Einstellungen stehen, was er meldet, wenn
etwas fehlt. Diese Antworten werden hier festgehalten, bevor Funktion
dazukommt.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mailburg.core.archive import Archive, Mode
from mailburg.core.benutzer import Benutzer
from mailburg.server import einstellungen as lage
from mailburg.server.dienst import FELDER, _zustand, seite

WURZEL = Path(__file__).resolve().parent.parent

#: Die Pakete, die »mailburg server« vor dem Start nachsieht.
SERVERPAKETE = ("starlette", "uvicorn")


def _spec_vortaeuschen(*fehlend: str):
    """Ein ``find_spec``, das genau ``fehlend`` als nicht installiert meldet.

    **Die übrigen Serverpakete gelten als vorhanden**, auch wenn sie im
    Testlauf fehlen. Die CI fährt einen Lauf bewusst ohne Zusatzpakete
    (siehe CLAUDE.md), und dort soll ein Test über die *Startmeldung*
    nicht daran scheitern, dass uvicorn nicht da ist – er prüft etwas
    anderes.

    Alles, was nicht zu den Serverpaketen gehört, geht an das echte
    ``find_spec``: Ein Platzhalter für jeden Namen träfe auch die
    Importe, die importlib im Hintergrund selbst macht.
    """
    import importlib.util

    echtes = importlib.util.find_spec

    def spec(name, *rest):
        if name in fehlend:
            return None
        if name in SERVERPAKETE:
            # Geprüft wird nur auf »is None«; der Inhalt ist gleichgültig.
            return object()
        return echtes(name, *rest)

    return spec


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

    def test_er_kommt_ohne_standardausgabe_aus(self):
        """**Der Fehler, der den ersten Startversuch umbrachte.**

        Ein Dienst unter pywin32 hat keine Konsole; ``sys.stdout`` ist
        dort ``None``. uvicorns Vorgabe-Protokoll baut einen Formatter,
        der fragt, ob die Ausgabe ein Terminal ist – und bricht ab mit
        ``Unable to configure formatter 'default'``, einer Meldung, die
        nicht entfernt nach der Ursache klingt.

        Am 2026-10-02 auf Windows Server 2025 aufgelaufen. **Der Test
        braucht kein Windows**: Es fehlt nur die Standardausgabe, und
        die lässt sich überall wegnehmen.
        """
        try:
            import uvicorn  # noqa: F401
        except ImportError:
            self.skipTest("uvicorn ist nicht installiert")

        from mailburg.server import windows_dienst

        ordner = tempfile.TemporaryDirectory()
        self.addCleanup(ordner.cleanup)
        wo = Path(ordner.name) / "Archiv"
        Archive.create(wo, name="Probe", mode=Mode.GESCHAEFTLICH).close()

        echtes_aus, echtes_fehler = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = None
        try:
            einstellungen = windows_dienst.uvicorn_einstellungen(
                lage.Serverlage(archiv=wo)
            )
        finally:
            sys.stdout, sys.stderr = echtes_aus, echtes_fehler

        self.assertEqual(einstellungen.port, lage.STANDARD_ANSCHLUSS)
        # Ein Zugriffsprotokoll wüchse im Ereignisprotokoll endlos mit.
        self.assertFalse(einstellungen.access_log)

    def test_uvicorns_meldungen_gehen_nicht_verloren(self):
        """``log_config=None`` allein wäre die halbe Reparatur.

        Ohne eigenen Handler verschwänden danach alle Meldungen von
        uvicorn – auch die über einen belegten Port. Der Dienst liefe
        nicht und sagte nicht, warum.
        """
        self.assertIn("log_config=None", self.quelle)
        self.assertIn("_protokoll_einrichten", self.quelle)
        self.assertIn("LogErrorMsg", self.quelle)

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
        """Was hier erprobt ist und was nicht, muss am Modul stehen.

        **Geprüft wird der Sinn, nicht der Wortlaut.** Bis zum
        2026-10-02 stand hier ``assertIn("Nicht geprüft", …)`` – und als
        der Dienst zum ersten Mal wirklich lief, wurde dieser Test zum
        Bremsklotz gegen die Korrektur, die er schützen sollte. Dieselbe
        Falle wie am 2026-09-07 bei »Microsoft-Konten gehen derzeit
        nicht«, dort nachzulesen in CLAUDE.md.

        Verlangt wird deshalb nur: Der Kopf sagt, dass etwas offen ist,
        und er benennt die beiden Punkte, die es wirklich sind.
        """
        kopf = self.quelle.split('"""')[1]

        self.assertIn("ungeprüft", kopf.lower())
        # Die zwei offenen Punkte, auf die es am 15.10. ankommt.
        self.assertIn("LocalSystem", kopf)
        self.assertIn("Tresor", kopf)


class StartmeldungTest(unittest.TestCase):
    """Was »mailburg server« sagt, bevor er lauscht.

    **Auf einem Server sitzt niemand vor einem Browser.** Ein Rückmelder
    ist am 2026-09-06 genau daran hängengeblieben: Die Meldung nannte
    ``http://127.0.0.1:8383/`` als erreichbar – auf einem Rechner ohne
    Arbeitsumgebung stimmt das und hilft niemandem.
    """

    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.wo = Path(self.ordner.name) / "Archiv"
        Archive.create(self.wo, name="Probe", mode=Mode.GESCHAEFTLICH).close()

    def _laufen_lassen(self, adresse: str) -> tuple[str, str]:
        """Führt den Befehl wirklich aus – nur ohne zu lauschen."""
        import argparse
        import io
        import contextlib

        from mailburg import __main__ as cli

        umgebung = {
            lage.ARCHIV: str(self.wo),
            lage.ADRESSE: adresse,
            lage.ANSCHLUSS: "8383",
        }
        aus, fehler = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, umgebung), \
                mock.patch("importlib.util.find_spec", _spec_vortaeuschen()), \
                mock.patch("mailburg.server.dienst.starten", return_value=0), \
                mock.patch.object(lage, "anschluss_frei", return_value=True), \
                contextlib.redirect_stdout(aus), \
                contextlib.redirect_stderr(fehler):
            cli.cmd_server(argparse.Namespace())

        return aus.getvalue(), fehler.getvalue()

    def test_lokal_steht_der_ssh_tunnel_dabei(self):
        """Sonst nennt die Meldung eine Adresse, die niemand aufrufen kann."""
        aus, _ = self._laufen_lassen("127.0.0.1")

        self.assertIn("ssh -L 8383:127.0.0.1:8383", aus)

    def test_bei_ipv6_steht_die_adresse_in_klammern(self):
        """Ohne sie liest ssh die Doppelpunkte als eigene Trennzeichen."""
        aus, _ = self._laufen_lassen("::1")

        self.assertIn("ssh -L 8383:[::1]:8383", aus)

    def test_oeffentlich_wird_vor_dem_klartext_gewarnt(self):
        """Nicht mehr vor der fehlenden Anmeldung – die gibt es seit 31.08."""
        aus, fehler = self._laufen_lassen("0.0.0.0")  # noqa: S104

        self.assertIn("Klartext", fehler)
        self.assertNotIn("keine Anmeldung", fehler)
        # Wer im ganzen Netz lauscht, braucht keinen Tunnel.
        self.assertNotIn("ssh -L", aus)

    def test_die_sorge_auf_der_zustandsseite_sagt_dasselbe(self):
        """Zwei Texte zur selben Lage dürfen nicht auseinanderlaufen."""
        offen = lage.Serverlage(archiv=self.wo, adresse="0.0.0.0")  # noqa: S104

        sorgen = " ".join(_zustand(offen)["sorgen"])

        self.assertIn("Klartext", sorgen)
        self.assertNotIn("keine Anmeldung", sorgen)


class LeererIndexTest(unittest.TestCase):
    """Ein leerer Index sieht aus wie ein leeres Archiv.

    **Der schwerste Befund vom 2026-10-02.** Der Dienst lief als
    LocalSystem und hatte damit ein anderes ``%LOCALAPPDATA%`` als der
    Mensch, der das Archiv angelegt hatte. Der Index liegt außerhalb des
    Archivs – also sah der Dienst einen leeren.

    Die Anmeldung ging trotzdem: Zugänge liegen *im* Archiv, Mails kommen
    aus dem Index. Wer sich anmeldete, kam herein und bekam auf jede
    Suche eine leere Liste. **Nichts daran sieht nach einer Störung aus**,
    und mit 70.000 echten Mails hätte das niemand als Fehler erkannt.
    """

    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.wo = Path(self.ordner.name) / "Archiv"
        Archive.create(self.wo, name="Probe", mode=Mode.GESCHAEFTLICH).close()

    def _bericht(self, mails: int, journal: int) -> dict:
        """Zustand mit erfundenen Zahlen – Index gegen Journal."""
        echtes_open = Archive.open

        def gefaelscht(*args, **kwargs):
            archiv = echtes_open(*args, **kwargs)
            archiv.index.statistics = lambda: {"mails": mails}
            archiv.index.account_totals = lambda: {}
            type(archiv.journal).count = property(lambda self: journal)
            return archiv

        with mock.patch.object(Archive, "open", gefaelscht):
            return _zustand(lage.Serverlage(archiv=self.wo))

    def test_ein_leerer_index_bei_vollem_archiv_wird_gemeldet(self):
        sorgen = " ".join(self._bericht(mails=0, journal=28)["sorgen"])

        self.assertIn("Suchindex ist leer", sorgen)
        # Der Weg hinaus gehört dazu, sonst ist es nur eine Feststellung.
        self.assertIn("neuaufbau", sorgen)

    def test_ein_frisches_archiv_wird_nicht_angemeckert(self):
        """Beim Anlegen steht ein Eintrag im Journal und nichts im Index.

        Das ist der Normalfall und keine Störung – wer hier warnte,
        erschreckte jeden, der gerade ein Archiv angelegt hat.
        """
        sorgen = " ".join(self._bericht(mails=0, journal=1)["sorgen"])

        self.assertNotIn("Suchindex ist leer", sorgen)

    def test_ein_gefuellter_index_schweigt(self):
        sorgen = " ".join(self._bericht(mails=27, journal=28)["sorgen"])

        self.assertNotIn("Suchindex", sorgen)


class FehlendePaketeTest(unittest.TestCase):
    """Wenn starlette oder uvicorn fehlen.

    **Der Hinweis dafür war unerreichbar.** ``dienst.py`` holt beide
    Pakete erst *in* seinen Funktionen – damit die Kommandozeile ohne sie
    läuft. Der ``try/except ImportError`` um ``from … import starten``
    fing deshalb nichts: Der Import gelingt immer. Wem uvicorn fehlte,
    bekam einen Traceback aus ``dienst.py``, Zeile 332 – und zwar *nach*
    der Startmeldung, was sich liest, als wäre ein laufender Dienst
    abgestürzt.

    Am 2026-10-02 beim Durchspielen des Windows-Probelaufs aufgefallen,
    am Schritt, an dem der Dienst zum ersten Mal von Hand startet.
    """

    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.wo = Path(self.ordner.name) / "Archiv"
        Archive.create(self.wo, name="Probe", mode=Mode.GESCHAEFTLICH).close()

    def _ohne(self, *pakete: str) -> tuple[str, str, int]:
        """Führt den Befehl aus, als wären ``pakete`` nicht installiert."""
        import argparse
        import contextlib
        import io

        from mailburg import __main__ as cli

        umgebung = {lage.ARCHIV: str(self.wo), lage.ANSCHLUSS: "8383"}
        aus, fehler = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, umgebung), \
                mock.patch("importlib.util.find_spec",
                           _spec_vortaeuschen(*pakete)), \
                mock.patch("mailburg.server.dienst.starten", return_value=0), \
                mock.patch.object(lage, "anschluss_frei", return_value=True), \
                contextlib.redirect_stdout(aus), \
                contextlib.redirect_stderr(fehler):
            code = cli.cmd_server(argparse.Namespace())

        return aus.getvalue(), fehler.getvalue(), code

    def test_fehlendes_uvicorn_wird_vorher_gemeldet(self):
        """Vorher kam der Traceback erst nach »Erreichbar: http://…«."""
        aus, fehler, code = self._ohne("uvicorn")

        self.assertEqual(code, 2)
        self.assertIn("uvicorn", fehler)
        self.assertIn("pip install uvicorn", fehler)
        # **Keine Startmeldung.** Wer »Erreichbar« gelesen hat und danach
        # einen Fehler bekommt, sucht ihn beim Dienst statt bei pip.
        self.assertNotIn("Erreichbar", aus)

    def test_beide_fehlend_werden_beide_genannt(self):
        """Zwei Durchläufe à ein Paket sind zwei Fehlschläge zu viel."""
        _, fehler, code = self._ohne("starlette", "uvicorn")

        self.assertEqual(code, 2)
        self.assertIn("pip install starlette uvicorn", fehler)

    def test_der_rat_zeigt_nicht_auf_pypi(self):
        """MailBurg liegt dort nicht – die Lehre vom 2026-10-01."""
        _, fehler, _ = self._ohne("uvicorn")

        self.assertNotIn("mailburg[", fehler)

    def test_mit_beiden_paketen_laeuft_er_durch(self):
        """Sonst prüfte der Test nur, dass die Prüfung überhaupt feuert."""
        aus, fehler, code = self._ohne()

        self.assertEqual(code, 0)
        self.assertIn("Erreichbar", aus)
        self.assertNotIn("pip install", fehler)


if __name__ == "__main__":
    unittest.main()
