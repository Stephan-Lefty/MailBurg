"""Die Prüfungen zum Einrichten des Serverdienstes.

**Warum sie ohne Windows prüfbar sein müssen.** Sie handeln fast
ausschließlich von Dingen, die nur unter Windows passieren – Dienst,
Registry, Ereignisprotokoll. Läge die Entscheidung im Fenster, liefe
hier kein einziger Test, und der erste Durchlauf wäre wieder der am
echten Server. Genau so ist der 2026-10-02 verlaufen.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mailburg.core.archive import Archive, Mode
from mailburg.core.benutzer import Benutzer
from mailburg.server import einrichtung
from mailburg.server.einrichtung import Lage, Umgebung


class PaketeTest(unittest.TestCase):
    """Was fehlt, muss beim Namen genannt werden."""

    def _ohne(self, *fehlend: str):
        echtes = einrichtung._vorhanden

        def gefiltert(name: str) -> bool:
            return name not in fehlend and echtes(name)

        return mock.patch.object(einrichtung, "_vorhanden", gefiltert)

    def test_fehlende_pflichtpakete_werden_genannt(self):
        with self._ohne("uvicorn"):
            befunde = einrichtung.pruefe_pakete()

        pflicht = befunde[0]
        self.assertIs(pflicht.lage, Lage.FEHLT)
        self.assertIn("uvicorn", pflicht.text)

    def test_der_rat_zeigt_nicht_auf_pypi(self):
        """MailBurg liegt dort nicht – die Lehre vom 2026-10-01."""
        with self._ohne("starlette", "uvicorn"):
            befunde = einrichtung.pruefe_pakete()

        self.assertEqual(befunde[0].einzelheiten, "pip install starlette uvicorn")
        self.assertNotIn("mailburg[", befunde[0].einzelheiten)

    def test_ein_fehlendes_kuerpaket_haelt_nichts_auf(self):
        """Ohne keyring läuft der Dienst – nur ohne Passwörter."""
        with self._ohne("keyring"):
            befunde = einrichtung.pruefe_pakete()

        keyring = next(b for b in befunde if b.titel == "keyring")
        self.assertIs(keyring.lage, Lage.ACHTUNG)
        self.assertNotIn(Lage.FEHLT, [b.lage for b in befunde[1:]])

    def test_ein_kaputtes_paket_gilt_als_fehlend(self):
        """``find_spec`` wirft dann, statt None zu liefern."""
        with mock.patch("importlib.util.find_spec", side_effect=ValueError):
            self.assertFalse(einrichtung._vorhanden("irgendwas"))


class ArchivTest(unittest.TestCase):
    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.wo = Path(self.ordner.name) / "Archiv"

    def test_ohne_archiv_steht_das_da(self):
        befund = einrichtung.pruefe_archiv(None)

        self.assertIs(befund.lage, Lage.FEHLT)
        self.assertEqual(befund.abhilfe, "archiv")

    def test_ein_leerer_ordner_ist_kein_archiv(self):
        """Geprüft wird die ``archive.json``, nicht die Existenz."""
        leer = Path(self.ordner.name) / "leer"
        leer.mkdir()

        befund = einrichtung.pruefe_archiv(leer)

        self.assertIs(befund.lage, Lage.FEHLT)
        self.assertIn("archive.json", befund.einzelheiten)

    def test_ein_echtes_archiv_geht_durch(self):
        Archive.create(self.wo, name="Probe", mode=Mode.GESCHAEFTLICH).close()

        self.assertIs(einrichtung.pruefe_archiv(self.wo).lage, Lage.GUT)


class ZugangTest(unittest.TestCase):
    """Die drei Fälle, die in einer Liste gleich aussehen."""

    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.wo = Path(self.ordner.name) / "Archiv"
        Archive.create(self.wo, name="Probe", mode=Mode.GESCHAEFTLICH).close()

    def _anlegen(self, *, passwort: bool, postfaecher: bool) -> None:
        with Archive.open(self.wo, exclusive=True) as archiv:
            liste = archiv.benutzer
            wer = Benutzer("chef")
            if passwort:
                wer.passwort_setzen("Probelauf-2026!")
            wer.alle_postfaecher = postfaecher
            liste.hinzufuegen(wer)
            archiv.benutzer_setzen(liste)

    def test_ohne_zugang_kommt_niemand_hinein(self):
        befund = einrichtung.pruefe_zugaenge(self.wo)

        self.assertIs(befund.lage, Lage.FEHLT)
        self.assertEqual(befund.abhilfe, "zugang")

    def test_ein_zugang_ohne_passwort_zaehlt_nicht(self):
        """In der Liste sieht er aus wie ein fertiger."""
        self._anlegen(passwort=False, postfaecher=True)

        befund = einrichtung.pruefe_zugaenge(self.wo)

        self.assertIs(befund.lage, Lage.FEHLT)
        self.assertIn("Passwort", befund.text)

    def test_ein_zugang_ohne_postfaecher_wird_gemeldet(self):
        """Er kann sich anmelden und sieht eine leere Trefferliste."""
        self._anlegen(passwort=True, postfaecher=False)

        befund = einrichtung.pruefe_zugaenge(self.wo)

        self.assertIs(befund.lage, Lage.ACHTUNG)
        self.assertIn("sehen nichts", befund.text)

    def test_ein_vollstaendiger_zugang_geht_durch(self):
        self._anlegen(passwort=True, postfaecher=True)

        self.assertIs(einrichtung.pruefe_zugaenge(self.wo).lage, Lage.GUT)

    def test_ohne_archiv_wird_nicht_geraten(self):
        """»Unklar« ist richtiger als »fehlt«, wenn nichts da ist."""
        self.assertIs(einrichtung.pruefe_zugaenge(None).lage, Lage.UNKLAR)


class UmgebungTest(unittest.TestCase):
    def test_die_drei_variablen_stehen_drin(self):
        from mailburg.server import einstellungen as lage

        werte = Umgebung(archiv=Path("/pfad"), anschluss=8484).als_variablen()

        self.assertEqual(werte[lage.ARCHIV], "/pfad")
        self.assertEqual(werte[lage.ANSCHLUSS], "8484")
        self.assertEqual(werte[lage.ADRESSE], lage.STANDARD_ADRESSE)


class GesamtbildTest(unittest.TestCase):
    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.wo = Path(self.ordner.name) / "Archiv"
        Archive.create(self.wo, name="Probe", mode=Mode.GESCHAEFTLICH).close()

    def test_die_liste_faengt_oben_an(self):
        """Ein Fehler weit oben macht alles darunter sinnlos."""
        bild = einrichtung.alles_pruefen(Umgebung(archiv=self.wo))

        titel = [b.titel for b in bild.befunde]
        self.assertEqual(titel[0], "Betriebssystem")
        self.assertEqual(titel[1], "Python")
        self.assertLess(titel.index("Archiv"), titel.index("Zugänge"))

    def test_ein_fehlender_punkt_macht_es_nicht_bereit(self):
        bild = einrichtung.alles_pruefen(Umgebung(archiv=None))

        self.assertFalse(bild.bereit)

    def test_jeder_befund_sagt_etwas(self):
        """Eine Zeile ohne Text wäre eine Ampel ohne Auskunft."""
        bild = einrichtung.alles_pruefen(Umgebung(archiv=self.wo))

        for befund in bild.befunde:
            self.assertTrue(befund.titel, "Titel fehlt")
            self.assertTrue(befund.text, f"Text fehlt bei {befund.titel}")

    def test_eine_nicht_erreichbare_oberflaeche_ist_kein_absturz(self):
        """Auf dem Port lauscht im Testlauf nichts – das ist der Normalfall."""
        befund = einrichtung.erreichbar(Umgebung(anschluss=1), zeit=0.5)

        self.assertIs(befund.lage, Lage.FEHLT)


class OhneWindowsTest(unittest.TestCase):
    """Was passiert, wenn jemand das Fenster unter Linux öffnet."""

    def test_das_betriebssystem_wird_gemeldet_statt_verschwiegen(self):
        with mock.patch.object(einrichtung, "ist_windows", return_value=False):
            befund = einrichtung.pruefe_system()

        self.assertIs(befund.lage, Lage.ACHTUNG)
        self.assertIn("kein Windows", befund.text)

    def test_der_dienstzustand_wird_nicht_erfunden(self):
        """**Unklar ist eine Auskunft, »läuft nicht« wäre eine Erfindung.**

        Die Regel aus CLAUDE.md: Ein Auffangnetz darf keine Auskunft
        erfinden. »Nicht eingerichtet« sähe hier aus wie ein Befund und
        wäre eine Aussage über ein Betriebssystem, das gar nicht läuft.
        """
        with mock.patch.object(einrichtung, "ist_windows", return_value=False):
            zustand, _ = einrichtung.dienst_zustand()

        self.assertIs(zustand, Lage.UNKLAR)

    def test_ereignisse_sind_leer_statt_erfunden(self):
        with mock.patch.object(einrichtung, "ist_windows", return_value=False):
            self.assertEqual(einrichtung.ereignisse(), [])


class DienstbefehlTest(unittest.TestCase):
    """Der Dienst wird in einem **eigenen** Prozess gesteuert."""

    def test_nicht_im_eigenen_prozess(self):
        """``HandleCommandLine`` beendet den Prozess, in dem es läuft.

        Ein Fenster, das sich beim Starten des Dienstes selbst schließt,
        wäre eine denkwürdige Bedienung.
        """
        quelle = (
            Path(einrichtung.__file__)
        ).read_text(encoding="utf-8")

        self.assertIn("subprocess.run", quelle)
        self.assertIn("sys.executable", quelle)

    def test_die_konsolenkodierung_wird_angegeben(self):
        """Sonst kommt »enth„lt« an statt »enthält« (2026-08-30)."""
        quelle = Path(einrichtung.__file__).read_text(encoding="utf-8")

        self.assertIn("konsolenkodierung()", quelle)

    def test_ein_fehlschlag_wird_als_solcher_zurueckgegeben(self):
        lauf = mock.Mock(returncode=1, stdout="", stderr="ging nicht")
        with mock.patch("subprocess.run", return_value=lauf):
            geklappt, text = einrichtung.dienst_starten()

        self.assertFalse(geklappt)
        self.assertIn("ging nicht", text)

    def test_ein_fehlender_befehl_bringt_nichts_um(self):
        with mock.patch("subprocess.run", side_effect=OSError("weg")):
            geklappt, text = einrichtung.dienst_anlegen()

        self.assertFalse(geklappt)
        self.assertIn("weg", text)


class EinstellungenTest(unittest.TestCase):
    """Was gewählt ist und was gilt, sind zwei Dinge.

    **Der Fehler, der am 2026-10-02 eine halbe Stunde gekostet hat.** Im
    Fenster stand das neue Archiv, in der Registry das alte – und der
    Dienst nahm die Registry. Im Ereignisprotokoll erschien ein Pfad, den
    im Fenster niemand mehr sah.
    """

    def _mit(self, gesetzt: dict[str, str]):
        return mock.patch.object(
            einrichtung, "gesetzte_variablen", return_value=gesetzt
        )

    def test_ohne_uebernehmen_faellt_es_auf(self):
        from mailburg.server import einstellungen as lage

        with self._mit({lage.ARCHIV: ""}):
            befund = einrichtung.pruefe_einstellungen(
                Umgebung(archiv=Path("/neu"))
            )

        self.assertIs(befund.lage, Lage.FEHLT)
        self.assertEqual(befund.abhilfe, "uebernehmen")

    def test_ein_alter_wert_wird_genannt(self):
        """Der alte Pfad muss im Text stehen – sonst sucht man im Fenster."""
        from mailburg.server import einstellungen as lage

        gesetzt = {
            lage.ARCHIV: r"C:\MailBurg\Probearchiv",
            lage.ADRESSE: "127.0.0.1",
            lage.ANSCHLUSS: "8383",
        }
        with self._mit(gesetzt):
            befund = einrichtung.pruefe_einstellungen(
                Umgebung(archiv=Path(r"C:\MailBurg-Archiv"))
            )

        self.assertIs(befund.lage, Lage.FEHLT)
        self.assertIn("Probearchiv", befund.text)

    def test_stimmt_alles_ueberein_ist_es_gut(self):
        from mailburg.server import einstellungen as lage

        gesetzt = {
            lage.ARCHIV: "/archiv",
            lage.ADRESSE: "127.0.0.1",
            lage.ANSCHLUSS: "8383",
        }
        with self._mit(gesetzt):
            befund = einrichtung.pruefe_einstellungen(Umgebung(archiv=Path("/archiv")))

        self.assertIs(befund.lage, Lage.GUT)


class StarttypTest(unittest.TestCase):
    """Ob der Dienst einen Neustart des Servers übersteht.

    pywin32 legt Dienste ohne Angabe als ``manual`` an – das steht in
    seiner eigenen Hilfe. Ein Archivdienst, der nach jedem Neustart unten
    bleibt, fällt niemandem auf, bis montags jemand sucht.
    """

    def test_manuell_ist_ein_befund(self):
        name, kommt_wieder = einrichtung.STARTARTEN[3]

        self.assertEqual(name, "Manuell")
        self.assertFalse(kommt_wieder)

    def test_automatisch_geht_durch(self):
        _, kommt_wieder = einrichtung.STARTARTEN[2]

        self.assertTrue(kommt_wieder)

    def test_deaktiviert_auch_nicht(self):
        _, kommt_wieder = einrichtung.STARTARTEN[4]

        self.assertFalse(kommt_wieder)

    def test_beim_anlegen_wird_der_starttyp_mitgegeben(self):
        """Sonst steht die Vorgabe »manual«, und die ist die falsche."""
        lauf = mock.Mock(returncode=0, stdout="Service installed", stderr="")
        with mock.patch("subprocess.run", return_value=lauf) as gerufen:
            einrichtung.dienst_anlegen()

        befehl = gerufen.call_args[0][0]
        self.assertIn("--startup", befehl)
        # Vor dem Befehl, nicht danach – so will es pywin32.
        self.assertLess(befehl.index("--startup"), befehl.index("install"))

    def test_ohne_windows_wird_nichts_behauptet(self):
        with mock.patch.object(einrichtung, "ist_windows", return_value=False):
            self.assertIs(einrichtung.pruefe_starttyp().lage, Lage.UNKLAR)


class TresorTest(unittest.TestCase):
    """Ob der Dienst an die Postfach-Passwörter kommt.

    **Ohne sie läuft er und holt keine Post.** Das ist die teuerste
    Fehlerart in diesem Programm: Es sieht funktionierend aus, und
    auffallen wird es dem, der in einem Jahr eine Mail aus diesem Monat
    sucht. Deshalb steht der Tresor in der Prüfliste, auch wenn er für
    das reine Lesen nicht gebraucht wird.
    """

    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.wo = Path(self.ordner.name) / "gemeinsam"

        # **Die Umgebung zurücklegen.** ``tresor_einrichten`` setzt
        # MAILBURG_SCHLUESSELDATEI und MAILBURG_EINSTELLUNGEN - mit
        # Absicht, denn die Prüfung danach soll den neuen Stand sehen.
        # Ohne dieses Aufräumen sah der nächste Test im selben Lauf einen
        # Hauptschlüssel, den es für ihn nicht geben darf. Die drei
        # Fehlschläge in test_tresor.py traten nur in der *vollen* Suite
        # auf, nie beim Einzellauf - die unangenehmste Sorte.
        import os

        umgebung = mock.patch.dict(os.environ, {}, clear=False)
        umgebung.start()
        self.addCleanup(umgebung.stop)

    def _ohne_alles(self):
        """Weder Schlüssel noch Einträge."""
        return mock.patch.multiple(
            einrichtung.tresor,
            verfuegbar=mock.Mock(return_value=False),
            eintraege=mock.Mock(return_value=[]),
        )

    def _mit(self, *, schluessel: bool, passwoerter: int):
        return mock.patch.multiple(
            einrichtung.tresor,
            verfuegbar=mock.Mock(return_value=schluessel),
            eintraege=mock.Mock(return_value=["a"] * passwoerter),
        )

    def test_ohne_tresor_ist_es_eine_warnung_kein_fehler(self):
        """Wer nur liest, braucht ihn nicht – das darf nicht rot sein."""
        with self._ohne_alles():
            befund = einrichtung.pruefe_tresor(Umgebung())

        self.assertIs(befund.lage, Lage.ACHTUNG)
        self.assertIn("holt aber keine neue Post", befund.text)

    def test_passwoerter_ohne_schluessel_sind_ein_fehler(self):
        """Sie liegen da und lassen sich nicht öffnen."""
        with mock.patch.object(Path, "is_file", return_value=True), \
                self._mit(schluessel=False, passwoerter=3):
            befund = einrichtung.pruefe_tresor(Umgebung())

        self.assertIs(befund.lage, Lage.FEHLT)
        self.assertIn("Hauptschlüssel", befund.text)

    def test_der_stille_fall_wird_erkannt(self):
        """**Alles eingerichtet, und der Dienst sucht woanders.**

        Der Mensch hat Schlüssel und Passwörter, beides liegt in seinem
        Profil – und der Dienst als Systemkonto sieht nichts davon. Es
        schlägt nichts fehl; es kommt nur keine Post.
        """
        with mock.patch.object(einrichtung, "ist_windows", return_value=True), \
                mock.patch.object(Path, "is_file", return_value=True), \
                self._mit(schluessel=True, passwoerter=5):
            befund = einrichtung.pruefe_tresor(Umgebung(einstellungen=None))

        self.assertIs(befund.lage, Lage.FEHLT)
        self.assertIn("sucht sie dort nicht", befund.text)

    def test_mit_gemeinsamem_ordner_ist_es_gut(self):
        with mock.patch.object(einrichtung, "ist_windows", return_value=True), \
                mock.patch.object(Path, "is_file", return_value=True), \
                self._mit(schluessel=True, passwoerter=5):
            befund = einrichtung.pruefe_tresor(
                Umgebung(einstellungen=self.wo)
            )

        self.assertIs(befund.lage, Lage.GUT)

    def test_einrichten_verlangt_den_gemeinsamen_ordner(self):
        zeilen = einrichtung.tresor_einrichten(Umgebung())

        self.assertEqual(len(zeilen), 1)
        self.assertIn("gemeinsamen Ort", zeilen[0])

    def test_einrichten_legt_den_schluessel_an(self):
        try:
            import cryptography  # noqa: F401
        except ImportError:
            self.skipTest("cryptography fehlt")

        with mock.patch.object(einrichtung, "ist_windows", return_value=False):
            zeilen = einrichtung.tresor_einrichten(
                Umgebung(einstellungen=self.wo)
            )

        datei = self.wo / einrichtung.SCHLUESSELDATEI
        self.assertTrue(datei.is_file())
        self.assertTrue(datei.read_text("utf-8").strip())
        self.assertTrue(any("erzeugt" in z for z in zeilen))

    def test_ein_vorhandener_schluessel_wird_nie_ueberschrieben(self):
        """**Er ist das Einzige, was die Passwörter noch öffnet.**

        Ihn zu ersetzen hieße, sie alle zu verlieren – und zwar stumm,
        denn die Tresordatei bliebe ja lesbar.
        """
        try:
            import cryptography  # noqa: F401
        except ImportError:
            self.skipTest("cryptography fehlt")

        self.wo.mkdir(parents=True)
        datei = self.wo / einrichtung.SCHLUESSELDATEI
        datei.write_text("der-alte-schluessel", encoding="utf-8")

        with mock.patch.object(einrichtung, "ist_windows", return_value=False):
            einrichtung.tresor_einrichten(Umgebung(einstellungen=self.wo))

        self.assertEqual(datei.read_text("utf-8"), "der-alte-schluessel")

    def test_der_hinweis_zum_getrennt_halten_steht_da(self):
        """Wer Schlüsseldatei und Tresordatei zusammen hat, hat die
        Postfächer. Das muss dastehen, wo jemand beides anfasst."""
        try:
            import cryptography  # noqa: F401
        except ImportError:
            self.skipTest("cryptography fehlt")

        with mock.patch.object(einrichtung, "ist_windows", return_value=False):
            zeilen = einrichtung.tresor_einrichten(
                Umgebung(einstellungen=self.wo)
            )

        zusammen = " ".join(zeilen)
        self.assertIn("nie zusammen", zusammen)

    def test_die_passwoerter_kommen_nicht_von_hier(self):
        """**Ein Fenster, das fremde Schlüsselbünde ausliest, bauen wir
        nicht.** Der Weg dafür heißt »mailburg tresor uebernehmen«, und
        er wird genannt."""
        try:
            import cryptography  # noqa: F401
        except ImportError:
            self.skipTest("cryptography fehlt")

        with mock.patch.object(einrichtung, "ist_windows", return_value=False):
            zeilen = einrichtung.tresor_einrichten(
                Umgebung(einstellungen=self.wo)
            )

        self.assertIn("tresor uebernehmen", " ".join(zeilen))


class GemeinsamerOrtTest(unittest.TestCase):
    """Einstellungen und Index an einem Ort, den beide erreichen."""

    def test_die_variablen_kommen_nur_wenn_gesetzt(self):
        """**Eine leere Variable am Dienst wäre schlimmer als keine.**

        Sie überschriebe die Vorgabe mit nichts, und der Dienst suchte
        in einem Verzeichnis ohne Namen.
        """
        from mailburg.core import paths

        ohne = Umgebung(archiv=Path("/a")).als_variablen()
        mit = Umgebung(
            archiv=Path("/a"), einstellungen=Path("/b"), daten=Path("/c")
        ).als_variablen()

        self.assertNotIn(paths.EINSTELLUNGEN, ohne)
        self.assertNotIn(paths.DATEN, ohne)
        self.assertEqual(mit[paths.EINSTELLUNGEN], "/b")
        self.assertEqual(mit[paths.DATEN], "/c")


class VerknuepfungTest(unittest.TestCase):
    def test_ohne_windows_gibt_es_keine(self):
        with mock.patch.object(einrichtung, "ist_windows", return_value=False):
            zeilen = einrichtung.verknuepfungen_anlegen(Umgebung())

        self.assertEqual(len(zeilen), 1)
        self.assertIn("Windows", zeilen[0])

    def test_beide_namen_stehen_in_der_tabelle(self):
        """Ein Aufräumen muss dieselben Namen finden wie das Anlegen."""
        self.assertIn("MailBurg im Browser", einrichtung.VERKNUEPFUNGEN)
        self.assertIn("MailBurg einrichten", einrichtung.VERKNUEPFUNGEN)


if __name__ == "__main__":
    unittest.main()
