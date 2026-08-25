"""Kontenverwaltung und Abrufzustand."""

from __future__ import annotations

import json
import os
import stat as stat_modul
import sys
import tempfile
import unittest
from pathlib import Path

from mailburg.core.accounts import STANDARD_AUSSCHLUSS, Konto, Kontenliste
from mailburg.core.sync import ZUSTAND_VERSION, Abrufzustand


class KontoTest(unittest.TestCase):
    def test_schluessel_traegt_server_und_benutzer(self):
        # Zwei Postfächer mit demselben Benutzernamen auf verschiedenen
        # Servern dürfen sich im Schlüsselbund nicht überschreiben.
        einer = Konto(name="A", server="imap.example.org", benutzer="post")
        anderer = Konto(name="B", server="imap.example.net", benutzer="post")
        self.assertNotEqual(einer.schluessel, anderer.schluessel)

    def test_papierkorb_ist_von_haus_aus_ausgeschlossen(self):
        konto = Konto(name="A", server="s", benutzer="b")
        self.assertIn("Trash", konto.ausschluss)
        self.assertIn("Papierkorb", konto.ausschluss)

    def test_jedes_konto_bekommt_eine_eigene_ausschlussliste(self):
        # Eine gemeinsame Liste wäre der klassische Fehler mit
        # veränderlichen Vorgabewerten: Ein Konto zu ändern, änderte alle.
        einer = Konto(name="A", server="s", benutzer="b")
        anderer = Konto(name="B", server="s", benutzer="b")
        einer.ausschluss.append("Privat")
        self.assertNotIn("Privat", anderer.ausschluss)
        self.assertEqual(len(anderer.ausschluss), len(STANDARD_AUSSCHLUSS))


class BrueckeTest(unittest.TestCase):
    """Wann die Zertifikatsprüfung entfallen darf – und wann nicht."""

    def konto(self, server: str, bruecke: bool = True) -> Konto:
        return Konto(
            name="Proton", server=server, benutzer="post@proton.me",
            port=1143, ssl=False, bruecke=bruecke,
        )

    def test_auf_dem_eigenen_rechner_greift_sie(self):
        for adresse in ("127.0.0.1", "localhost", "::1", "LOCALHOST"):
            with self.subTest(adresse=adresse):
                self.assertTrue(self.konto(adresse).ist_lokale_bruecke)

    def test_bei_einem_fremden_server_greift_sie_nicht(self):
        # Das ist der Punkt: Sonst ließe sich mit --bruecke die
        # Zertifikatsprüfung für jeden beliebigen Server abschalten, und
        # zwar unbemerkt.
        for adresse in ("imap.example.org", "192.168.1.50", "127.0.0.1.example.org"):
            with self.subTest(adresse=adresse):
                self.assertFalse(self.konto(adresse).ist_lokale_bruecke)

    def test_ohne_das_kennzeichen_gar_nicht(self):
        self.assertFalse(self.konto("127.0.0.1", bruecke=False).ist_lokale_bruecke)

    def test_gewoehnliche_konten_sind_keine_bruecke(self):
        konto = Konto(name="A", server="imap.example.org", benutzer="b")
        self.assertFalse(konto.bruecke)
        self.assertFalse(konto.ist_lokale_bruecke)


class KontenlisteTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.datei = Path(self._tmp.name) / "konten.json"

    def tearDown(self):
        self._tmp.cleanup()

    def liste(self) -> Kontenliste:
        return Kontenliste(self.datei)

    def konto(self, name="Firma") -> Konto:
        return Konto(name=name, server="imap.example.org", benutzer="post@example.org")

    def test_hinzufuegen_und_wiederfinden(self):
        self.liste().hinzufuegen(self.konto())
        wieder = self.liste()
        self.assertEqual(len(wieder), 1)
        self.assertEqual(wieder.finden("Firma").server, "imap.example.org")

    def test_derselbe_name_zweimal_geht_nicht(self):
        liste = self.liste()
        liste.hinzufuegen(self.konto())
        with self.assertRaises(ValueError):
            liste.hinzufuegen(self.konto())

    def test_entfernen(self):
        liste = self.liste()
        liste.hinzufuegen(self.konto())
        self.assertTrue(liste.entfernen("Firma"))
        self.assertFalse(liste.entfernen("Firma"))
        self.assertEqual(len(self.liste()), 0)

    def test_nur_aktive_werden_abgerufen(self):
        liste = self.liste()
        liste.hinzufuegen(self.konto("Firma"))
        stillgelegt = self.konto("Alt")
        stillgelegt.aktiv = False
        liste.hinzufuegen(stillgelegt)
        self.assertEqual([k.name for k in liste.aktive()], ["Firma"])

    def test_kein_passwort_in_der_datei(self):
        # Das ist der Punkt der ganzen Übung: Wer die Datei kopiert, hat
        # noch lange keinen Zugang zu den Postfächern.
        self.liste().hinzufuegen(self.konto())
        inhalt = self.datei.read_text(encoding="utf-8")
        self.assertNotIn("passwort", inhalt.lower())
        self.assertNotIn("password", inhalt.lower())
        gespeichert = json.loads(inhalt)["konten"][0]
        self.assertEqual(set(gespeichert) & {"passwort", "password"}, set())

    @unittest.skipIf(sys.platform == "win32", "Zugriffsrechte anders geregelt")
    def test_datei_gehoert_nur_dem_benutzer(self):
        self.liste().hinzufuegen(self.konto())
        rechte = stat_modul.S_IMODE(os.stat(self.datei).st_mode)
        self.assertEqual(rechte, 0o600)

    def test_kaputte_datei_macht_keinen_absturz(self):
        self.datei.write_text("{kein json", encoding="utf-8")
        self.assertEqual(len(self.liste()), 0)


class AbrufzustandTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.datei = Path(self._tmp.name) / "abruf.json"

    def tearDown(self):
        self._tmp.cleanup()

    def zustand(self) -> Abrufzustand:
        return Abrufzustand("kennung", datei=self.datei)

    def test_ohne_datei_ist_nichts_bekannt(self):
        self.assertIsNone(self.zustand().uidvalidity("Firma", "INBOX"))

    def test_uidvalidity_ueberdauert(self):
        z = self.zustand()
        z.ordner_gesehen("Firma", "INBOX", 1234)
        z.speichern()
        self.assertEqual(self.zustand().uidvalidity("Firma", "INBOX"), 1234)

    def test_erstes_sehen_verlangt_keinen_neuaufbau(self):
        self.assertFalse(self.zustand().ordner_gesehen("Firma", "INBOX", 1234))

    def test_gleicher_wert_verlangt_keinen_neuaufbau(self):
        z = self.zustand()
        z.ordner_gesehen("Firma", "INBOX", 1234)
        self.assertFalse(z.ordner_gesehen("Firma", "INBOX", 1234))

    def test_geaenderter_wert_verlangt_neuaufbau(self):
        z = self.zustand()
        z.ordner_gesehen("Firma", "INBOX", 1234)
        self.assertTrue(z.ordner_gesehen("Firma", "INBOX", 9999))

    def test_neuaufbau_wirft_die_vormerkungen_weg(self):
        # Die alten Nummern zeigen auf Mails, die es so nicht mehr gibt.
        z = self.zustand()
        z.ordner_gesehen("Firma", "INBOX", 1234)
        z.vormerken("Firma", "INBOX", 42)
        z.ordner_gesehen("Firma", "INBOX", 9999)
        self.assertEqual(z.nachzuegler("Firma", "INBOX"), [])

    def test_vormerken_und_streichen(self):
        z = self.zustand()
        z.vormerken("Firma", "INBOX", 7)
        z.vormerken("Firma", "INBOX", 3)
        self.assertEqual(z.nachzuegler("Firma", "INBOX"), [3, 7])
        z.erledigt("Firma", "INBOX", 3)
        self.assertEqual(z.nachzuegler("Firma", "INBOX"), [7])

    def test_dieselbe_uid_zweimal_bleibt_einmal(self):
        z = self.zustand()
        z.vormerken("Firma", "INBOX", 7)
        z.vormerken("Firma", "INBOX", 7)
        self.assertEqual(z.nachzuegler("Firma", "INBOX"), [7])

    def test_vormerkungen_wachsen_nicht_endlos(self):
        # Wer so viele Fehlschläge hat, dem hilft nur ein Vollabruf.
        from mailburg.core.sync import HOECHSTZAHL_NACHZUEGLER

        z = self.zustand()
        for uid in range(HOECHSTZAHL_NACHZUEGLER + 50):
            z.vormerken("Firma", "INBOX", uid)
        self.assertEqual(
            len(z.nachzuegler("Firma", "INBOX")), HOECHSTZAHL_NACHZUEGLER
        )

    def test_streichen_ohne_vormerkung_ist_harmlos(self):
        self.zustand().erledigt("Unbekannt", "INBOX", 5)

    def test_konto_vergessen(self):
        z = self.zustand()
        z.ordner_gesehen("Firma", "INBOX", 1234)
        z.konto_vergessen("Firma")
        self.assertIsNone(z.uidvalidity("Firma", "INBOX"))

    def test_fremde_fassung_wird_nicht_uebernommen(self):
        # Lieber alles neu holen als etwas halb Verstandenes glauben.
        self.datei.write_text(
            json.dumps({"version": ZUSTAND_VERSION + 1, "konten": {"Firma": {"INBOX": {}}}}),
            encoding="utf-8",
        )
        self.assertIsNone(self.zustand().uidvalidity("Firma", "INBOX"))

    def test_kaputte_datei_macht_keinen_absturz(self):
        self.datei.write_text("{kein json", encoding="utf-8")
        self.assertIsNone(self.zustand().uidvalidity("Firma", "INBOX"))


if __name__ == "__main__":
    unittest.main()


class ZertifikatsnamenTest(unittest.TestCase):
    """Namensprüfung nach RFC 6125, für die Diagnose bei Massenhostern."""

    def test_genauer_name(self):
        from mailburg.core.tlsdiagnose import passt

        self.assertTrue(passt("mail.example.org", "mail.example.org"))
        self.assertFalse(passt("mail.example.org", "mail.example.com"))

    def test_gross_und_kleinschreibung_egal(self):
        from mailburg.core.tlsdiagnose import passt

        self.assertTrue(passt("Mail.Example.ORG", "mail.example.org"))

    def test_platzhalter_deckt_genau_eine_ebene(self):
        from mailburg.core.tlsdiagnose import passt

        self.assertTrue(passt("s111.hoster.example", "*.hoster.example"))
        # Zwei Ebenen deckt ein Stern nicht ab - sonst gälte ein Zertifikat
        # für *.example.org auch für fremde Unterdomänen.
        self.assertFalse(passt("a.b.hoster.example", "*.hoster.example"))
        # Und die nackte Domäne ebenfalls nicht.
        self.assertFalse(passt("hoster.example", "*.hoster.example"))

    def test_platzhalter_greift_nicht_ueber_die_domaene_hinaus(self):
        from mailburg.core.tlsdiagnose import passt

        self.assertFalse(passt("s111.boeser.host", "*.hoster.example"))
        self.assertFalse(passt("hoster.example.boese.de", "*.hoster.example"))

    def test_abschliessender_punkt_stoert_nicht(self):
        from mailburg.core.tlsdiagnose import passt

        self.assertTrue(passt("s111.hoster.example.", "*.hoster.example"))
