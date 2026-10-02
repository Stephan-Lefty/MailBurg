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


if __name__ == "__main__":
    unittest.main()
