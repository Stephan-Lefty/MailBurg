"""Der Abruf über JMAP.

Geprüft wird gegen ``tests/fake_jmap.py``, einen nachgebauten Server.
**Am 2026-09-03 ist der Abruf zum ersten Mal gegen einen echten Server
gelaufen** – ein selbst betriebenes Stalwart, rund 5.000 Nachrichten,
gemeldet von einem Anwender. Fastmail bleibt offen; dort meldet man sich
mit einer Zugriffsmarke an statt mit Benutzername und Passwort.

Was sich damit trotzdem verlässlich prüfen lässt, ist der Umgang mit
dem, was das Protokoll vorschreibt: Ordnerrollen, Mails in mehreren
Ordnern, ein Stand, den der Server nicht mehr auflösen kann. Genau an
diesen Stellen liefe ein Abruf sonst stillschweigend vorbei.
"""

from __future__ import annotations

import unittest
from unittest import mock

from mailburg.core.accounts import Konto
from mailburg.sources.jmap import JmapFehler, JmapSource, sitzung_holen
from tests.fake_jmap import SITZUNG, FakeJmap


def _konto(**mehr) -> Konto:
    angaben = {"name": "Fastmail", "server": SITZUNG, "benutzer": "",
               "port": 443}
    angaben.update(mehr)
    return Konto(**angaben)


class SitzungTest(unittest.TestCase):
    """Der Einstieg in jede JMAP-Verbindung."""

    def setUp(self):
        self.server = FakeJmap()

    def test_sie_nennt_api_download_und_konto(self):
        with mock.patch("urllib.request.urlopen", self.server.urlopen):
            sitzung = sitzung_holen(SITZUNG, "", "marke")

        self.assertTrue(sitzung.api)
        self.assertTrue(sitzung.download)
        self.assertEqual(sitzung.konto, "konto-1")

    def test_eine_marke_wird_zum_bearer(self):
        """Fastmail und Verwandte vergeben Zugriffsmarken, keine Passwörter."""
        with mock.patch("urllib.request.urlopen", self.server.urlopen):
            sitzung_holen(SITZUNG, "", "geheime-marke")

        self.assertEqual(self.server.anmeldung, "Bearer geheime-marke")

    def test_benutzer_und_passwort_werden_zu_basic(self):
        """Ein selbst betriebener Server nimmt oft beides."""
        with mock.patch("urllib.request.urlopen", self.server.urlopen):
            sitzung_holen(SITZUNG, "ich", "geheim")

        self.assertTrue(self.server.anmeldung.startswith("Basic "))

    def test_ein_server_ohne_mail_wird_abgewiesen(self):
        """JMAP ist ein allgemeines Protokoll; Mail nur eine Anwendung."""
        def ohne_mail(bitte, timeout=None):
            import json

            from tests.fake_jmap import KERN, _Antwort

            return _Antwort(json.dumps({
                "capabilities": {KERN: {}},
                "accounts": {}, "primaryAccounts": {},
                "apiUrl": "x", "downloadUrl": "y",
            }).encode())

        with mock.patch("urllib.request.urlopen", ohne_mail):
            with self.assertRaises(JmapFehler) as gefangen:
                sitzung_holen(SITZUNG, "", "marke")

        self.assertIn("nicht für Mail", str(gefangen.exception))

    def test_eine_abgelehnte_anmeldung_erklaert_die_marke(self):
        """Der häufigste Anfängerfehler: das Kontopasswort eintragen."""
        from urllib.error import HTTPError

        def abgelehnt(bitte, timeout=None):
            raise HTTPError(SITZUNG, 401, "Unauthorized", {}, None)

        with mock.patch("urllib.request.urlopen", abgelehnt):
            with self.assertRaises(JmapFehler) as gefangen:
                sitzung_holen(SITZUNG, "", "falsch")

        self.assertIn("Zugriffsmarke", str(gefangen.exception))

    def test_kein_json_heisst_falsche_adresse(self):
        def kein_json(bitte, timeout=None):
            from tests.fake_jmap import _Antwort

            return _Antwort(b"<html>Hier ist kein JMAP</html>")

        with mock.patch("urllib.request.urlopen", kein_json):
            with self.assertRaises(JmapFehler) as gefangen:
                sitzung_holen(SITZUNG, "", "marke")

        self.assertIn("Stimmt die Adresse", str(gefangen.exception))


class OrdnerTest(unittest.TestCase):
    def setUp(self):
        self.server = FakeJmap()

    def _ordner(self, konto=None) -> list[str]:
        with mock.patch("urllib.request.urlopen", self.server.urlopen):
            return JmapSource(konto or _konto(), "marke").folders()

    def test_verschachtelte_ordner_bekommen_ihren_pfad(self):
        """Das Archiv will »INBOX/Rechnungen«, JMAP nennt nur den Namen."""
        self.assertIn("INBOX/Rechnungen", self._ordner())

    def test_papierkorb_und_spam_bleiben_draussen(self):
        """Über die Rolle, nicht über den Namen.

        Ein Ordner heißt je nach Sprache »Papierkorb«, »Trash« oder
        »Corbeille«; seine Rolle heißt überall ``trash``.
        """
        ordner = self._ordner()

        self.assertNotIn("Papierkorb", ordner)
        self.assertNotIn("Spam", ordner)

    def test_der_gmail_ordner_alle_nachrichten_bleibt_draussen(self):
        """Er enthält sämtliche Mails ein zweites Mal.

        Auf der Platte gäbe das keine doppelte Datei, wohl aber einen
        zweiten Fundort je Mail im Journal.
        """
        self.server.ordner["m9"] = ("Alle Nachrichten", None, "all")

        self.assertNotIn("Alle Nachrichten", self._ordner())

    def test_die_ausschlussliste_des_kontos_gilt_auch(self):
        self.server.ordner["m5"] = ("Newsletter", "m1", "")

        ordner = self._ordner(_konto(ausschluss=["INBOX/Newsletter"]))

        self.assertNotIn("INBOX/Newsletter", ordner)

    def test_ein_kreis_in_den_elternangaben_haengt_nicht(self):
        """Ein Server, der sich vertut, darf uns nicht ewig kreisen lassen."""
        self.server.ordner["m6"] = ("A", "m7", "")
        self.server.ordner["m7"] = ("B", "m6", "")

        self._ordner()  # darf nur nicht hängen


class AbrufTest(unittest.TestCase):
    def setUp(self):
        self.server = FakeJmap()
        self.server.mail_hinzufuegen("e1", "Rechnung Mai", ["m1"])
        self.server.mail_hinzufuegen("e2", "Angebot", ["m2"], {"$seen": True})
        self.server.mail_hinzufuegen("e3", "Werbung", ["m4"])
        self.server.mail_hinzufuegen("e4", "Geloescht", ["m3"])

    def _holen(self, **mehr):
        with mock.patch("urllib.request.urlopen", self.server.urlopen):
            quelle = JmapSource(_konto(), "marke", **mehr)
            return list(quelle.iter_messages()), quelle

    def test_nur_die_gewuenschten_ordner_kommen_mit(self):
        mails, _ = self._holen()

        self.assertEqual(len(mails), 2)
        self.assertEqual(
            sorted(m.folder for m in mails), ["INBOX", "INBOX/Rechnungen"]
        )

    def test_die_nachricht_kommt_bytegenau(self):
        """Über die Download-Adresse, nicht aus dem JSON.

        Die zerlegte Fassung wäre bequemer und für ein Archiv wertlos –
        mit ihr wäre keine DKIM-Signatur mehr prüfbar.
        """
        mails, _ = self._holen()

        roh = next(m.raw for m in mails if b"Rechnung Mai" in m.raw)
        self.assertTrue(roh.startswith(b"From: "))
        self.assertIn(b"Message-ID:", roh)

    def test_marken_kommen_in_imap_schreibweise(self):
        """Sonst stünde im Archiv zweierlei, je nach Herkunft."""
        mails, _ = self._holen()

        gesehen = next(m for m in mails if b"Angebot" in m.raw)
        self.assertEqual(gesehen.flags, "\\Seen")

    def test_eine_mail_in_mehreren_ordnern_kommt_einmal(self):
        """Bei Gmail der Normalfall – dort sind Ordner Etiketten."""
        self.server.mail_hinzufuegen("e5", "Doppelt", ["m1", "m2"])

        mails, _ = self._holen()

        doppelte = [m for m in mails if b"Doppelt" in m.raw]
        self.assertEqual(len(doppelte), 1)

    def test_eine_unerreichbare_mail_beendet_den_lauf_nicht(self):
        """Eine unter zehntausend darf die übrigen nicht mitreißen."""
        self.server.mails["e9"] = (b"", ["m1"], {})  # blob fehlt

        mails, _ = self._holen()

        self.assertGreaterEqual(len(mails), 2)


class InkrementellTest(unittest.TestCase):
    """``Email/changes`` – der eigentliche Grund für JMAP.

    Es beantwortet die Frage, die ein Archiv bei jedem Lauf stellt: Was
    ist seit dem letzten Mal dazugekommen? Über IMAP muss MailBurg das
    mit ``UID n:*`` und Nachfiltern nachbauen, und selbst das ist nur
    eine Näherung.
    """

    def setUp(self):
        self.server = FakeJmap()
        self.server.mail_hinzufuegen("e1", "Alte Mail")

    def _lauf(self, **mehr):
        with mock.patch("urllib.request.urlopen", self.server.urlopen):
            quelle = JmapSource(_konto(), "marke", **mehr)
            return list(quelle.iter_messages()), quelle

    def test_der_zweite_lauf_holt_nur_das_neue(self):
        _, erste = self._lauf()
        stand = erste.zustand

        self.server.mail_hinzufuegen("e2", "Neu A")
        self.server.mail_hinzufuegen("e3", "Neu B")
        self.server.aenderungen[stand] = ["e2", "e3"]
        self.server.zustand = "z-2"
        self.server.geholte_blobs.clear()

        mails, _ = self._lauf(seit_zustand=stand)

        self.assertEqual(len(mails), 2)
        self.assertEqual(
            sorted(self.server.geholte_blobs), ["blob-e2", "blob-e3"]
        )

    def test_die_alte_mail_wird_nicht_noch_einmal_geladen(self):
        """Das ist der ganze Gewinn – sonst könnte man auch IMAP nehmen."""
        _, erste = self._lauf()
        self.server.aenderungen[erste.zustand] = []
        self.server.geholte_blobs.clear()

        mails, _ = self._lauf(seit_zustand=erste.zustand)

        self.assertEqual(mails, [])
        self.assertEqual(self.server.geholte_blobs, [])

    def test_ein_zu_alter_stand_faellt_auf_den_vollen_weg_zurueck(self):
        """Server halten ihre Änderungslisten nicht ewig.

        Wer das nicht behandelt, holt ab irgendwann gar nichts mehr –
        und merkt es nicht, weil kein Fehler kommt.
        """
        self.server.zu_alte_staende.add("uralt")

        mails, _ = self._lauf(seit_zustand="uralt")

        self.assertEqual(len(mails), 1)
        self.assertIn("Email/query", self.server.aufrufe)

    def test_der_neue_stand_wird_zurueckgegeben(self):
        """Ohne ihn fängt der nächste Lauf wieder von vorn an."""
        _, quelle = self._lauf()

        self.assertTrue(quelle.zustand)


class PruefenTest(unittest.TestCase):
    """Was die Oberfläche beim Einrichten anzeigt."""

    def test_eine_stehende_verbindung_meldet_die_ordner(self):
        from mailburg.sources.jmap import pruefen

        server = FakeJmap()
        with mock.patch("urllib.request.urlopen", server.urlopen):
            geklappt, text = pruefen(_konto(), "marke")

        self.assertTrue(geklappt)
        self.assertIn("Ordner", text)

    def test_ein_fehler_kommt_als_satz_zurueck(self):
        from urllib.error import HTTPError

        from mailburg.sources.jmap import pruefen

        def abgelehnt(bitte, timeout=None):
            raise HTTPError(SITZUNG, 401, "Unauthorized", {}, None)

        with mock.patch("urllib.request.urlopen", abgelehnt):
            geklappt, text = pruefen(_konto(), "falsch")

        self.assertFalse(geklappt)
        self.assertIn("Zugriffsmarke", text)


class SchnittstelleTest(unittest.TestCase):
    """JMAP muss aussehen wie jede andere Quelle."""

    def test_es_ist_eine_source(self):
        from mailburg.sources.base import Source

        self.assertTrue(issubclass(JmapSource, Source))

    def test_es_beschreibt_sich(self):
        with mock.patch("urllib.request.urlopen", FakeJmap().urlopen):
            self.assertIn("JMAP", JmapSource(_konto(), "marke").describe())


if __name__ == "__main__":
    unittest.main()
