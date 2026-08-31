"""Passwörter auf einem Rechner ohne Schlüsselbund.

Ohne den Tresor läuft ein Server zwar, holt aber keine Post: Der
Schlüsselbund hängt an einer Anmeldesitzung, und ein Dienst läuft ohne.

Geprüft wird vor allem, was still schiefgehen kann – ein Passwort, das
doch im Klartext landet; ein falscher Hauptschlüssel, der als »nichts
hinterlegt« durchgeht; ein Tresor, der auf dem Arbeitsplatz ungefragt
den Schlüsselbund verdrängt.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mailburg.core import accounts, tresor
from mailburg.core.accounts import Konto

try:
    import cryptography  # noqa: F401

    HAT_KRYPTO = True
except ImportError:  # pragma: no cover
    HAT_KRYPTO = False

try:
    import keyring  # noqa: F401

    HAT_KEYRING = True
except ImportError:  # pragma: no cover
    HAT_KEYRING = False


class Umgebung(unittest.TestCase):
    """Jeder Test in seinem eigenen Konfigurationsordner."""

    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.umgebung = mock.patch.dict(
            os.environ,
            {"XDG_CONFIG_HOME": self.ordner.name,
             "APPDATA": self.ordner.name,
             "MAILBURG_SCHLUESSEL": "",
             "MAILBURG_SCHLUESSELDATEI": ""},
        )
        self.umgebung.start()
        self.addCleanup(self.umgebung.stop)

    def _einrichten(self) -> str:
        schluessel = tresor.schluessel_erzeugen()
        os.environ["MAILBURG_SCHLUESSEL"] = schluessel
        return schluessel


@unittest.skipUnless(HAT_KRYPTO, "cryptography fehlt")
class GrundlagenTest(Umgebung):
    def test_ohne_hauptschluessel_ist_kein_tresor_da(self):
        """Sonst schriebe MailBurg auf dem Arbeitsplatz am Schlüsselbund vorbei."""
        self.assertFalse(tresor.verfuegbar())

    def test_mit_hauptschluessel_schon(self):
        self._einrichten()

        self.assertTrue(tresor.verfuegbar())

    def test_hin_und_zurueck(self):
        self._einrichten()
        tresor.setzen("post@example.org", "geheimes-passwort")

        self.assertEqual(tresor.holen("post@example.org"), "geheimes-passwort")

    def test_unbekannter_eintrag(self):
        self._einrichten()

        self.assertIsNone(tresor.holen("gibt-es-nicht"))

    def test_das_passwort_steht_nicht_im_klartext_in_der_datei(self):
        """Der ganze Zweck – und leicht zu verlieren, wenn jemand »vereinfacht«."""
        self._einrichten()
        tresor.setzen("post@example.org", "geheimes-passwort")

        roh = (tresor._datei()).read_text(encoding="utf-8")
        self.assertNotIn("geheimes-passwort", roh)
        # Der Name des Eintrags steht drin - das ist Absicht, sonst
        # ließe sich nicht sagen, was fehlt.
        self.assertIn("post@example.org", roh)

    @unittest.skipIf(sys.platform == "win32", "Rechte gibt es dort anders")
    def test_die_datei_gehoert_nur_dem_benutzer(self):
        self._einrichten()
        tresor.setzen("post@example.org", "geheim")

        self.assertEqual(tresor._datei().stat().st_mode & 0o777, 0o600)

    def test_loeschen(self):
        self._einrichten()
        tresor.setzen("post@example.org", "geheim")
        tresor.loeschen("post@example.org")

        self.assertIsNone(tresor.holen("post@example.org"))
        tresor.loeschen("post@example.org")  # zweimal wirft nicht

    def test_ein_zweiter_eintrag_verdraengt_den_ersten_nicht(self):
        self._einrichten()
        tresor.setzen("erst@example.org", "eins")
        tresor.setzen("dann@example.org", "zwei")

        self.assertEqual(tresor.holen("erst@example.org"), "eins")
        self.assertEqual(tresor.holen("dann@example.org"), "zwei")

    def test_zweimal_dasselbe_passwort_sieht_verschieden_aus(self):
        """Sonst verriete die Datei, welche Postfächer dasselbe Passwort haben."""
        self._einrichten()
        tresor.setzen("erst@example.org", "dasselbe")
        tresor.setzen("dann@example.org", "dasselbe")

        inhalt = json.loads(tresor._datei().read_text(encoding="utf-8"))
        self.assertNotEqual(inhalt["erst@example.org"], inhalt["dann@example.org"])

    def test_die_liste_geht_auch_ohne_schluessel(self):
        """Für die Auskunft »was liegt hier eigentlich«."""
        self._einrichten()
        tresor.setzen("post@example.org", "geheim")
        os.environ["MAILBURG_SCHLUESSEL"] = ""

        self.assertEqual(tresor.eintraege(), ["post@example.org"])


@unittest.skipUnless(HAT_KRYPTO, "cryptography fehlt")
class FalscherSchluesselTest(Umgebung):
    def test_ein_falscher_schluessel_wirft(self):
        """Er darf nicht als »kein Passwort hinterlegt« durchgehen.

        Sonst fragte der Dienst bei jedem Abruf nach einem Passwort, das
        längst da ist – und niemand käme darauf, dass nur der Schlüssel
        nicht stimmt.
        """
        self._einrichten()
        tresor.setzen("post@example.org", "geheim")
        os.environ["MAILBURG_SCHLUESSEL"] = tresor.schluessel_erzeugen()

        with self.assertRaises(tresor.TresorFehler):
            tresor.holen("post@example.org")

    def test_ein_unsinniger_schluessel_wirft(self):
        os.environ["MAILBURG_SCHLUESSEL"] = "kein-gueltiger-schluessel"
        tresor.setzen  # noqa: B018 – nur der Zugriff, nicht der Aufruf

        with self.assertRaises(tresor.TresorFehler):
            tresor.setzen("post@example.org", "geheim")

    def test_eine_fehlende_schluesseldatei_wirft(self):
        """Und gilt trotzdem als eingerichtet – sonst fiele es niemandem auf."""
        os.environ["MAILBURG_SCHLUESSELDATEI"] = "/gibt/es/nicht"

        self.assertTrue(tresor.verfuegbar())
        with self.assertRaises(tresor.TresorFehler):
            tresor.hauptschluessel()


@unittest.skipUnless(HAT_KRYPTO, "cryptography fehlt")
class AusDateiTest(Umgebung):
    def test_der_schluessel_darf_in_einer_datei_stehen(self):
        """Der bessere Weg: Eine Umgebungsvariable steht in Prozesslisten."""
        schluessel = tresor.schluessel_erzeugen()
        ort = Path(self.ordner.name) / "schluessel"
        ort.write_text(schluessel + "\n", encoding="utf-8")
        os.environ["MAILBURG_SCHLUESSELDATEI"] = str(ort)

        tresor.setzen("post@example.org", "geheim")
        self.assertEqual(tresor.holen("post@example.org"), "geheim")

    def test_die_datei_geht_vor(self):
        """Wer beides gesetzt hat, meint vermutlich die Datei."""
        aus_datei = tresor.schluessel_erzeugen()
        ort = Path(self.ordner.name) / "schluessel"
        ort.write_text(aus_datei, encoding="utf-8")
        os.environ["MAILBURG_SCHLUESSELDATEI"] = str(ort)
        os.environ["MAILBURG_SCHLUESSEL"] = tresor.schluessel_erzeugen()

        self.assertEqual(tresor.hauptschluessel(), aus_datei)


@unittest.skipUnless(HAT_KRYPTO, "cryptography fehlt")
class KontenTest(Umgebung):
    """Das Zusammenspiel mit der Kontenverwaltung."""

    def setUp(self):
        super().setUp()
        self.konto = Konto(
            name="Firma", server="imap.example.org", benutzer="post@example.org"
        )

    @unittest.skipUnless(HAT_KEYRING, "keyring fehlt")
    def test_ohne_tresor_bleibt_der_schluesselbund_zustaendig(self):
        """Auf einem Arbeitsplatz soll nichts an ihm vorbei geschrieben werden."""
        with mock.patch.object(
            accounts, "schluesselbund_verfuegbar", return_value=True
        ):
            with mock.patch("keyring.set_password") as gesetzt:
                accounts.passwort_setzen(self.konto, "geheim")

        gesetzt.assert_called_once()
        self.assertEqual(tresor.eintraege(), [])

    def test_mit_tresor_geht_es_dorthin(self):
        """Und am Schlüsselbund vorbei – auch wenn es ihn gäbe."""
        self._einrichten()

        with mock.patch.object(
            accounts, "schluesselbund_verfuegbar", return_value=True
        ):
            self.assertTrue(accounts.passwort_setzen(self.konto, "geheim"))
            self.assertEqual(accounts.passwort_holen(self.konto), "geheim")

        self.assertEqual(tresor.eintraege(), [self.konto.schluessel])

    def test_auch_ohne_erreichbaren_schluesselbund(self):
        """Der eigentliche Fall: ein Server ohne Desktop."""
        self._einrichten()

        with mock.patch.object(
            accounts, "schluesselbund_verfuegbar", return_value=False
        ):
            self.assertTrue(accounts.passwort_setzen(self.konto, "geheim"))
            self.assertEqual(accounts.passwort_holen(self.konto), "geheim")

    def test_loeschen_geht_auch_in_den_tresor(self):
        self._einrichten()
        accounts.passwort_setzen(self.konto, "geheim")
        accounts.passwort_loeschen(self.konto)

        self.assertIsNone(accounts.passwort_holen(self.konto))

    def test_oauth2_token_landen_ebenfalls_im_tresor(self):
        """Ein Erneuerungs-Token ist mehr wert als das Passwort."""
        from mailburg.core.oauth2 import Token

        self._einrichten()
        token = Token(zugriff="abc", erneuerung="geheimes-erneuerungstoken")

        self.assertTrue(accounts.token_setzen(self.konto, token))
        zurueck = accounts.token_holen(self.konto)

        self.assertEqual(zurueck.erneuerung, "geheimes-erneuerungstoken")
        roh = tresor._datei().read_text(encoding="utf-8")
        self.assertNotIn("geheimes-erneuerungstoken", roh)


class OhneKryptoTest(Umgebung):
    """Fehlt ``cryptography``, gibt es keinen Rückfall auf Klartext."""

    def test_es_gibt_eine_klare_ansage(self):
        os.environ["MAILBURG_SCHLUESSEL"] = "irgendwas"

        with mock.patch.dict(sys.modules, {"cryptography.fernet": None}):
            with self.assertRaises(tresor.TresorFehler) as gefangen:
                tresor.setzen("post@example.org", "geheim")

        self.assertIn("cryptography", str(gefangen.exception))

    def test_und_nichts_wird_geschrieben(self):
        """Eine Datei, die aussieht wie ein Tresor und keiner ist, wäre schlimmer."""
        os.environ["MAILBURG_SCHLUESSEL"] = "irgendwas"

        with mock.patch.dict(sys.modules, {"cryptography.fernet": None}):
            with self.assertRaises(tresor.TresorFehler):
                tresor.setzen("post@example.org", "geheim")

        self.assertFalse(tresor._datei().exists())


if __name__ == "__main__":
    unittest.main()
