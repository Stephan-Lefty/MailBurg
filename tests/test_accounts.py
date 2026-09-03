"""Kontenverwaltung und Abrufzustand."""

from __future__ import annotations

import json
import os
import stat as stat_modul
import sys
import tempfile
import pathlib
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

    def test_schluessel_ohne_benutzer_nimmt_den_kontonamen(self):
        # Zwei JMAP-Konten beim selben Anbieter, beide mit einer
        # Zugriffsmarke statt eines Benutzernamens: Ohne den Kontonamen
        # bekämen sie denselben Schlüssel, und das zweite Passwort
        # überschriebe das erste, ohne dass jemand etwas merkt.
        adresse = "https://api.example.org/jmap/session"
        einer = Konto(name="Privat", server=adresse, benutzer="", protokoll="jmap")
        anderer = Konto(name="Firma", server=adresse, benutzer="", protokoll="jmap")
        self.assertNotEqual(einer.schluessel, anderer.schluessel)

    def test_beschreibung_bei_jmap_klebt_keinen_port_an_die_adresse(self):
        konto = Konto(
            name="Firma",
            server="https://api.example.org/jmap/session",
            benutzer="",
            port=443,
            protokoll="jmap",
        )
        text = konto.beschreibung()
        self.assertIn("JMAP", text)
        self.assertNotIn(":443", text)
        # Und keine Lücke da, wo der Benutzername fehlt.
        self.assertNotIn("( auf", text)

    def test_beschreibung_bei_imap_bleibt_wie_sie_war(self):
        konto = Konto(name="A", server="imap.example.org", benutzer="post", port=993)
        self.assertEqual(konto.beschreibung(), "A (post auf imap.example.org:993)")

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


class SchluesselbundNameTest(unittest.TestCase):
    """Der Schlüsselbund muss beim richtigen Namen genannt werden.

    »KDE-Brieftasche« vor einem GNOME-Nutzer ist schlimmer als gar keine
    Auskunft: Er sucht dann in seinem Menü nach etwas, das es dort nicht
    gibt.
    """

    def name_bei(self, modulname: str, dienst: str = "") -> str:
        from unittest import mock

        from mailburg.core import accounts

        class GefaelschtesBackend:
            pass

        GefaelschtesBackend.__module__ = modulname

        with mock.patch.object(accounts, "schluesselbund_verfuegbar", return_value=True), \
             mock.patch.dict("sys.modules", {"keyring": mock.MagicMock()}), \
             mock.patch.object(accounts, "_secretservice_anbieter", return_value=dienst):
            import sys

            sys.modules["keyring"].get_keyring.return_value = GefaelschtesBackend()
            return accounts.schluesselbund_name()

    def test_windows(self):
        self.assertEqual(
            self.name_bei("keyring.backends.Windows"), "Anmeldeinformationsverwaltung"
        )

    def test_macos(self):
        self.assertEqual(self.name_bei("keyring.backends.macOS"), "Schlüsselbund")

    def test_kde_ueber_kwallet_backend(self):
        self.assertEqual(self.name_bei("keyring.backends.kwallet"), "KDE-Brieftasche")

    def test_secretservice_fragt_nach_dem_dienst(self):
        # Dieselbe Schnittstelle bedienen mehrere Programme - wer gerade
        # antwortet, entscheidet den Namen.
        self.assertEqual(
            self.name_bei("keyring.backends.SecretService", "GNOME-Schlüsselbund"),
            "GNOME-Schlüsselbund",
        )
        self.assertEqual(
            self.name_bei("keyring.backends.SecretService", "KDE-Brieftasche"),
            "KDE-Brieftasche",
        )

    def test_unbekanntes_backend_bleibt_neutral(self):
        self.assertEqual(self.name_bei("keyring.backends.irgendwas"), "Schlüsselbund")

    def test_ohne_schluesselbund_kein_name(self):
        from unittest import mock

        from mailburg.core import accounts

        with mock.patch.object(accounts, "schluesselbund_verfuegbar", return_value=False):
            self.assertEqual(accounts.schluesselbund_name(), "")


class PostfachErkennenTest(unittest.TestCase):
    """Dasselbe Postfach darf nicht zweimal eingerichtet werden."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.liste = Kontenliste(Path(self._tmp.name) / "konten.json")
        self.liste.hinzufuegen(
            Konto(name="Kontakt", server="s111.hoster.example",
                  benutzer="kontakt@beispiel.de", port=143, ssl=False)
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_gefunden_trotz_anderem_namen(self):
        # Genau der Fall: von Hand als "Kontakt" eingerichtet, aus
        # Thunderbird käme es als "kontakt@beispiel.de" wieder.
        gefunden = self.liste.finden_nach_postfach(
            "kontakt@beispiel.de", "s111.hoster.example"
        )
        self.assertIsNotNone(gefunden)
        self.assertEqual(gefunden.name, "Kontakt")

    def test_gross_und_kleinschreibung_egal(self):
        self.assertIsNotNone(
            self.liste.finden_nach_postfach("Kontakt@Beispiel.DE", "S111.Hoster.Example")
        )

    def test_anderes_postfach_auf_demselben_server(self):
        # Bei einem Massenhoster liegen dutzende Postfächer auf einer
        # Maschine - der Server allein sagt gar nichts.
        self.assertIsNone(
            self.liste.finden_nach_postfach("service@beispiel.de", "s111.hoster.example")
        )

    def test_derselbe_server_unter_anderem_namen(self):
        # Der Fall aus der Erprobung: von Hand über s111.hoster.example
        # eingerichtet, aus Thunderbird käme es über imap.beispiel.de. Ein
        # Rechner, zwei Namen - und dasselbe Postfach.
        gefunden = self.liste.finden_nach_postfach(
            "kontakt@beispiel.de", "imap.beispiel.de"
        )
        self.assertIsNotNone(gefunden)
        self.assertEqual(gefunden.name, "Kontakt")

    def test_anmeldename_ohne_adresse_braucht_den_server(self):
        # "p1234567" kann es bei zwei Anbietern geben; dann sagt der
        # Benutzername allein nichts.
        self.liste.hinzufuegen(
            Konto(name="Alt", server="imap.anbieter-a.de", benutzer="p1234567")
        )
        self.assertIsNotNone(
            self.liste.finden_nach_postfach("p1234567", "imap.anbieter-a.de")
        )
        self.assertIsNone(
            self.liste.finden_nach_postfach("p1234567", "imap.anbieter-b.de")
        )


class ArchivzuordnungTest(unittest.TestCase):
    """Ein Postfach gehört in ein bestimmtes Archiv – nicht in jedes.

    Der teuerste Fehler in der Geschichte dieses Programms. Die
    Kontenliste gilt für das ganze Programm, das Archiv aber nicht:
    Jedes »Abrufen« holte alle eingerichteten Postfächer in das gerade
    geöffnete Archiv. Wer geschäftlich und privat trennt – wie es die
    Aufbewahrungsfristen nahelegen –, bekam in beiden denselben Bestand.

    Am 2026-08-26 an einem echten Aufbau aufgefallen: Von 9.866 Mails im
    Geschäftsarchiv gehörten 176 dorthin. Die übrigen 9.690 waren private
    Post – und lagen damit unter zehnjährigen Aufbewahrungsfristen.
    """

    def setUp(self) -> None:
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.datei = Path(self.ordner.name) / "konten.json"
        self.liste = Kontenliste(self.datei)
        for name in ("Geschaeftlich", "Privat", "Ungeklaert"):
            self.liste.hinzufuegen(
                Konto(name=name, server="imap.example.com", benutzer=f"{name}@example.com")
            )

    def test_neue_konten_sind_keinem_archiv_zugeordnet(self) -> None:
        """Die Voreinstellung ist »nirgends«, nicht »überall«.

        Unbequem, aber die einzige vertretbare Richtung: Post, die
        fälschlich nicht archiviert wurde, holt der nächste Lauf nach.
        Post, die fälschlich in einem Geschäftsarchiv landet, unterliegt
        dort zehn Jahre lang Aufbewahrungsfristen.
        """
        self.assertEqual(len(self.liste.ohne_archiv()), 3)
        self.assertEqual(self.liste.fuer_archiv("irgendeine-kennung"), [])

    def test_zuordnen_und_abfragen(self) -> None:
        self.liste.zuordnen("Geschaeftlich", "archiv-A")
        self.liste.zuordnen("Privat", "archiv-B")

        self.assertEqual(
            [k.name for k in self.liste.fuer_archiv("archiv-A")], ["Geschaeftlich"]
        )
        self.assertEqual(
            [k.name for k in self.liste.fuer_archiv("archiv-B")], ["Privat"]
        )
        self.assertEqual([k.name for k in self.liste.ohne_archiv()], ["Ungeklaert"])

    def test_ein_postfach_darf_in_mehrere_archive(self) -> None:
        """Selten, aber es gibt Gründe – etwa ein Archiv je Geschäftsjahr."""
        self.liste.zuordnen("Geschaeftlich", "archiv-A")
        self.liste.zuordnen("Geschaeftlich", "archiv-B")

        self.assertEqual(len(self.liste.fuer_archiv("archiv-A")), 1)
        self.assertEqual(len(self.liste.fuer_archiv("archiv-B")), 1)

    def test_zweimal_zuordnen_bleibt_einmal(self) -> None:
        self.liste.zuordnen("Geschaeftlich", "archiv-A")
        self.liste.zuordnen("Geschaeftlich", "archiv-A")

        self.assertEqual(self.liste.finden("Geschaeftlich").archive, ["archiv-A"])

    def test_loesen_nimmt_es_wieder_heraus(self) -> None:
        self.liste.zuordnen("Geschaeftlich", "archiv-A")

        self.assertTrue(self.liste.loesen("Geschaeftlich", "archiv-A"))
        self.assertEqual(self.liste.fuer_archiv("archiv-A"), [])

    def test_loesen_einer_nicht_vorhandenen_zuordnung(self) -> None:
        self.assertFalse(self.liste.loesen("Geschaeftlich", "archiv-A"))
        self.assertFalse(self.liste.loesen("Gibtsnicht", "archiv-A"))

    def test_die_zuordnung_bleibt_auf_der_platte(self) -> None:
        self.liste.zuordnen("Geschaeftlich", "archiv-A")

        wieder = Kontenliste(self.datei)

        self.assertEqual(
            [k.name for k in wieder.fuer_archiv("archiv-A")], ["Geschaeftlich"]
        )

    def test_abgeschaltete_konten_bleiben_aussen_vor(self) -> None:
        self.liste.zuordnen("Geschaeftlich", "archiv-A")
        self.liste.finden("Geschaeftlich").aktiv = False

        self.assertEqual(self.liste.fuer_archiv("archiv-A"), [])
        # Und es taucht auch nicht unter den offenen auf: Ein
        # abgeschaltetes Postfach ist keine unerledigte Zuordnung.
        self.assertNotIn(
            "Geschaeftlich", [k.name for k in self.liste.ohne_archiv()]
        )

    def test_eine_alte_kontendatei_ordnet_nichts_zu(self) -> None:
        """Aus einer Fassung ohne dieses Feld darf kein »überall« werden.

        Nach dem Update ruft zunächst nichts mehr ab. Das ist gewollt:
        Lieber eine Meldung, die zum Zuordnen auffordert, als ein
        stillschweigend falsch befülltes Archiv.
        """
        self.datei.write_text(
            json.dumps({"konten": [{
                "name": "Alt", "server": "imap.example.com",
                "benutzer": "alt@example.com",
            }]}),
            encoding="utf-8",
        )

        liste = Kontenliste(self.datei)

        self.assertEqual(liste.finden("Alt").archive, [])
        self.assertEqual(liste.fuer_archiv("irgendwas"), [])
        self.assertEqual([k.name for k in liste.ohne_archiv()], ["Alt"])


class ZuordnungsanzeigeTest(unittest.TestCase):
    """»konten zuordnung« soll Archivnamen zeigen, keine Kennungen.

    Vorher stand dort je Postfach eine Zeile mit
    ``c89fdf58-7ec8-4804-af89-915b71440b7b``. Für einen Menschen ist das
    keine Information – und die Frage lautet ohnehin »was landet in
    meinem Geschäftsarchiv?«, nicht »welche Kennung hat dieses
    Postfach?«.

    Die Zuordnung entscheidet über zehnjährige Aufbewahrungsfristen. Am
    2026-08-26 lagen deswegen 9.690 Mails im falschen Archiv – ein
    Befehl, der das sichtbar machen soll, muss lesbar sein.
    """

    def setUp(self) -> None:
        import json
        import tempfile

        from mailburg.core.archive import Archive

        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        wurzel = pathlib.Path(self.ordner.name)

        self.pfade = []
        self.kennungen = []
        for name in ("Geschäftsarchiv", "Privatarchiv"):
            pfad = wurzel / name
            Archive.create(pfad, name=name).close()
            self.pfade.append(str(pfad))
            self.kennungen.append(
                json.loads((pfad / "archive.json").read_text(encoding="utf-8"))["uuid"]
            )

    def _namen(self) -> dict[str, str]:
        """Die Auflösung steht seit dem 2026-08-29 in core.archive.

        Vorher gab es sie zweimal – einmal für die Kommandozeile, einmal
        für die Oberfläche. Zwei Stellen, die dasselbe tun, laufen
        irgendwann auseinander.
        """
        from unittest import mock

        from mailburg.core.archive import archivnamen

        with mock.patch("mailburg.core.einstellungen.zuletzt_benutzte_pfade",
                        return_value=self.pfade):
            return archivnamen()

    def test_die_kennung_wird_zum_namen(self) -> None:
        namen = self._namen()
        self.assertEqual(namen[self.kennungen[0]], "Geschäftsarchiv")
        self.assertEqual(namen[self.kennungen[1]], "Privatarchiv")

    def test_ein_unbekanntes_archiv_stoert_nicht(self) -> None:
        """Eine abgezogene Platte hat trotzdem Postfächer.

        Was sich nicht auflösen lässt, bleibt eine Kennung – das ist
        kein Fehler, sondern ehrlicher als sie wegzulassen.
        """
        from unittest import mock

        from mailburg.core.archive import archivnamen

        with mock.patch("mailburg.core.einstellungen.zuletzt_benutzte_pfade",
                        return_value=[*self.pfade, "/gibt/es/nicht"]):
            namen = archivnamen()

        self.assertEqual(len(namen), 2)

    def test_die_anzeige_gruppiert_nach_archiv(self) -> None:
        import contextlib
        import io
        from unittest import mock

        from mailburg import __main__ as cli
        from mailburg.core.accounts import Konto, Kontenliste

        liste = Kontenliste()
        liste.konten = [
            Konto(name="Firma", server="imap.example.org",
                  benutzer="post@example.org", archive=[self.kennungen[0]]),
            Konto(name="Privat", server="imap.example.net",
                  benutzer="ich@example.net", archive=[self.kennungen[1]]),
            Konto(name="Ohne Ziel", server="imap.example.com",
                  benutzer="rest@example.com"),
        ]

        ausgabe = io.StringIO()
        with mock.patch("mailburg.core.einstellungen.zuletzt_benutzte_pfade",
                        return_value=self.pfade):
            with mock.patch.object(cli, "Kontenliste", return_value=liste):
                with contextlib.redirect_stdout(ausgabe):
                    cli.cmd_konten_zuordnung(None)

        text = ausgabe.getvalue()
        self.assertIn("Geschäftsarchiv", text)
        self.assertIn("Privatarchiv", text)
        # Keine nackten Kennungen mehr für Archive, die MailBurg kennt.
        self.assertNotIn(self.kennungen[0], text)
        # Und das Postfach ohne Ziel wird ausdrücklich benannt.
        self.assertIn("Ohne Ziel", text)
        self.assertIn("wird nicht abgerufen", text)

    def test_der_archivname_steht_vor_seinen_postfaechern(self) -> None:
        import contextlib
        import io
        from unittest import mock

        from mailburg import __main__ as cli
        from mailburg.core.accounts import Konto, Kontenliste

        liste = Kontenliste()
        liste.konten = [
            Konto(name="Firma", server="imap.example.org",
                  benutzer="post@example.org", archive=[self.kennungen[0]]),
        ]

        ausgabe = io.StringIO()
        with mock.patch("mailburg.core.einstellungen.zuletzt_benutzte_pfade",
                        return_value=self.pfade):
            with mock.patch.object(cli, "Kontenliste", return_value=liste):
                with contextlib.redirect_stdout(ausgabe):
                    cli.cmd_konten_zuordnung(None)

        text = ausgabe.getvalue()
        self.assertLess(text.index("Geschäftsarchiv"), text.index("Firma"))


class SchluesselbundLageTest(unittest.TestCase):
    """Zwei Gründe, ein Ergebnis – aber völlig verschiedene Abhilfen.

    Entweder fehlt das Paket ``keyring``, dann hilft eine Installation.
    Oder es ist da, findet auf diesem System aber keinen Speicher – dann
    hilft nur eine andere Arbeitsumgebung.

    Bis zum 2026-08-28 stand in beiden Fällen »Auf diesem Rechner ist
    kein Schlüsselbund erreichbar«. Im ersten Fall ist das falsch: Der
    Rechner hat einen, MailBurg wurde nur ohne den passenden Zusatz
    installiert. Wer das liest, sucht am falschen Ende – am 2026-08-27
    unter Windows genau so passiert.
    """

    def _ohne_keyring(self):
        import builtins
        from unittest import mock

        echt = builtins.__import__

        def ohne(name, *args, **kwargs):
            if name == "keyring" or name.startswith("keyring."):
                raise ImportError("keyring fehlt")
            return echt(name, *args, **kwargs)

        return mock.patch.object(builtins, "__import__", ohne)

    def test_fehlendes_paket_wird_als_solches_benannt(self) -> None:
        from mailburg.core import accounts

        with self._ohne_keyring():
            geht, grund = accounts.schluesselbund_lage()

        self.assertFalse(geht)
        self.assertIn("keyring", grund)
        self.assertIn("pip install", grund)
        # Und ausdrücklich *nicht* dem Rechner angelastet.
        self.assertIn("nicht am Rechner", grund)

    def test_fehlender_speicher_bleibt_ein_systemproblem(self) -> None:
        from unittest import mock

        from mailburg.core import accounts

        try:
            import keyring
            from keyring.backends import fail
        except ImportError:
            self.skipTest("keyring nicht installiert")

        with mock.patch.object(keyring, "get_keyring",
                               return_value=fail.Keyring()):
            geht, grund = accounts.schluesselbund_lage()

        self.assertFalse(geht)
        self.assertIn("Rechner", grund)
        self.assertNotIn("pip install", grund)

    def test_die_alte_auskunft_baut_darauf_auf(self) -> None:
        """``schluesselbund_verfuegbar`` bleibt, damit nichts bricht."""
        from mailburg.core import accounts

        self.assertEqual(
            accounts.schluesselbund_verfuegbar(),
            accounts.schluesselbund_lage()[0],
        )


class ZusaetzeTest(unittest.TestCase):
    """Wer die Oberfläche installiert, muss Passwörter merken können.

    ``[oberflaeche]`` brachte bis zum 2026-08-28 nur PySide6 mit. Heraus
    kam ein Programm, das Postfächer einrichten und abrufen kann, aber
    kein Passwort behält – und die Meldung dazu klang nach einem Mangel
    des Rechners. Ein Assistent, der nach Passwörtern fragt und sie dann
    vergisst, ist schlimmer als einer, der gar nicht erst fragt.
    """

    def test_die_oberflaeche_bringt_den_schluesselbund_mit(self) -> None:
        wurzel = pathlib.Path(__file__).resolve().parent.parent
        text = (wurzel / "pyproject.toml").read_text(encoding="utf-8")

        zeile = next(
            z for z in text.splitlines() if z.startswith("oberflaeche = ")
        )
        self.assertIn("keyring", zeile)
