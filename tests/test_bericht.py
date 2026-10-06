"""Der Tagesbericht und die Störungsmeldung.

**Warum ein Archivdienst eine Mail schreibt.** Ein Dienst, der still
arbeitet, ist von einem Dienst, der still *nicht* arbeitet, nicht zu
unterscheiden. Am 2026-10-06 scheiterte der Abruf tagelang in seiner
ersten Zeile, und gesehen hat es niemand: Die Meldung stand im
Ereignisprotokoll, wo man nur nachsieht, wenn man schon etwas ahnt.

Diese Tests handeln deshalb weniger vom Versand als vom **Wortlaut** und
davon, **wann** etwas hinausgeht. Beides ist im Betrieb das
Entscheidende.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, time as uhrzeit
from pathlib import Path

from mailburg.core import bericht


class LageTest(unittest.TestCase):
    def test_ohne_angaben_wird_nicht_berichtet(self):
        self.assertFalse(bericht.Lage().eingerichtet)

    def test_eine_halbe_einrichtung_zaehlt_nicht(self):
        """**Sonst sieht es eingerichtet aus und verschickt nichts.**

        Eine Empfängeradresse ohne Postausgangsserver ist genau der
        Halbzustand, den dieses Projekt sonst bei anderen findet.
        """
        halb = bericht.Lage(an="chef@example.org")

        self.assertFalse(halb.eingerichtet)

    def test_vollstaendig_eingerichtet(self):
        voll = bericht.Lage(
            an="chef@example.org", smtp="mail.example.org",
            von="archiv@example.org",
        )

        self.assertTrue(voll.eingerichtet)

    def test_der_anschluss_steht_hinter_dem_doppelpunkt(self):
        self.assertEqual(
            bericht._server_lesen("mail.example.org:465"),
            ("mail.example.org", 465),
        )

    def test_ohne_anschluss_gilt_die_vorgabe(self):
        name, anschluss = bericht._server_lesen("mail.example.org")

        self.assertEqual(name, "mail.example.org")
        self.assertEqual(anschluss, bericht.STANDARDANSCHLUSS)

    def test_eine_unsinnige_uhrzeit_faellt_auf_die_vorgabe_zurueck(self):
        """**Ein Tippfehler darf den Bericht nicht abschalten.**

        Bliebe er dann aus, wäre sein Ausbleiben kein Signal mehr –
        und genau darauf beruht die ganze Funktion.
        """
        self.assertIsNone(bericht.zeit_lesen("viertel nach sieben"))

    def test_eine_uhrzeit_wird_gelesen(self):
        self.assertEqual(bericht.zeit_lesen("07:30"), uhrzeit(7, 30))


class FaelligTest(unittest.TestCase):
    def _lage(self):
        return bericht.Lage(
            an="chef@example.org", smtp="mail.example.org",
            von="archiv@example.org", zeit=uhrzeit(7, 0),
        )

    def test_vor_der_uhrzeit_noch_nicht(self):
        self.assertFalse(bericht.faellig(
            self._lage(), bericht.Stand(), datetime(2026, 10, 7, 6, 59)
        ))

    def test_danach_schon(self):
        self.assertTrue(bericht.faellig(
            self._lage(), bericht.Stand(), datetime(2026, 10, 7, 7, 1)
        ))

    def test_nicht_zweimal_am_selben_tag(self):
        stand = bericht.Stand(zuletzt=datetime(2026, 10, 7, 7, 2))

        self.assertFalse(bericht.faellig(
            self._lage(), stand, datetime(2026, 10, 7, 12, 0)
        ))

    def test_am_naechsten_tag_wieder(self):
        stand = bericht.Stand(zuletzt=datetime(2026, 10, 7, 7, 2))

        self.assertTrue(bericht.faellig(
            self._lage(), stand, datetime(2026, 10, 8, 7, 1)
        ))

    def test_wer_den_server_spaeter_einschaltet_bekommt_ihn_trotzdem(self):
        """**Nicht »ist es genau sieben Uhr«.** Sonst entschiede der
        Zufall, ob der Dienst im richtigen Augenblick nachsieht."""
        self.assertTrue(bericht.faellig(
            self._lage(), bericht.Stand(), datetime(2026, 10, 7, 11, 30)
        ))

    def test_ohne_einrichtung_nie(self):
        self.assertFalse(bericht.faellig(
            bericht.Lage(), bericht.Stand(), datetime(2026, 10, 7, 23, 0)
        ))


class TextTest(unittest.TestCase):
    def test_ein_gesunder_tag(self):
        betreff, text, heikel = bericht.bericht_bauen(
            "HaBeFaarchiv", 122, 70181, datetime(2026, 10, 6, 7, 0),
            ("Das Archiv ist in Ordnung.", False),
        )

        self.assertFalse(heikel)
        self.assertIn("in Ordnung", betreff)
        self.assertIn("122 Mails", text)
        self.assertIn("70181", text)
        self.assertIn("06.10.2026, 07:00 Uhr", text)

    def test_der_befund_steht_im_betreff(self):
        """**Wer dreißig Tagesmails hat, liest keine davon.** Einen
        Betreff, der sich ändert, sieht er trotzdem."""
        betreff, _, heikel = bericht.bericht_bauen(
            "HaBeFaarchiv", 0, 70181, None,
            ("Hash-Kette: BESCHÄDIGT an 2 Stelle(n).", True),
        )

        self.assertTrue(heikel)
        self.assertIn("BITTE NACHSEHEN", betreff)

    def test_der_befund_steht_oben_im_text(self):
        _, text, _ = bericht.bericht_bauen(
            "A", 0, 1, None, ("Hash-Kette: BESCHÄDIGT.", True),
        )

        self.assertTrue(text.startswith("Das Archiv hat eine Beanstandung"))

    def test_der_erste_bericht_nennt_keinen_falschen_zeitpunkt(self):
        _, text, _ = bericht.bericht_bauen(
            "A", 5, 5, None, ("in Ordnung", False),
        )

        self.assertIn("dem ersten Bericht", text)

    def test_das_ausbleiben_wird_erklaert(self):
        """Sonst merkt niemand, dass eine fehlende Mail selbst ein
        Befund ist."""
        _, text, _ = bericht.bericht_bauen(
            "A", 5, 5, None, ("in Ordnung", False),
        )

        self.assertIn("Bleibt sie einmal aus", text)


class StoerungTest(unittest.TestCase):
    def test_eine_stoerung_nennt_die_ursache(self):
        betreff, text = bericht.stoerung_bauen(
            "HaBeFaarchiv", "Postfach »buero« übersprungen: Zeitablauf"
        )

        self.assertIn("STÖRUNG", betreff)
        self.assertIn("Zeitablauf", text)

    def test_eine_stoerung_sagt_dass_sie_sich_nicht_wiederholt(self):
        """Sonst legt der Empfänger nach dem dritten Mal eine Regel an –
        und bekommt auch die vierte nicht mehr, die etwas anderes
        sagt."""
        _, text = bericht.stoerung_bauen("A", "irgendwas")

        self.assertIn("nicht wiederholt", text)
        self.assertIn("Entwarnung", text)

    def test_die_entwarnung_nennt_was_es_war(self):
        betreff, text = bericht.entwarnung_bauen("A", "Zeitablauf beim Abruf")

        self.assertIn("wieder in Ordnung", betreff)
        self.assertIn("Zeitablauf beim Abruf", text)


class StandTest(unittest.TestCase):
    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.datei = Path(self.ordner.name) / "bericht.json"

    def test_ohne_datei_ein_leerer_stand(self):
        stand = bericht.Stand.lesen(self.datei)

        self.assertIsNone(stand.zuletzt)
        self.assertEqual(stand.mails_zuletzt, 0)

    def test_schreiben_und_wieder_lesen(self):
        stand = bericht.Stand()
        stand.schreiben(
            self.datei, jetzt=datetime(2026, 10, 7, 7, 0), mails=70181
        )

        wieder = bericht.Stand.lesen(self.datei)

        self.assertEqual(wieder.zuletzt, datetime(2026, 10, 7, 7, 0))
        self.assertEqual(wieder.mails_zuletzt, 70181)

    def test_eine_stoerung_verstellt_den_tagesbericht_nicht(self):
        """**Sonst bliebe der Bericht am Morgen aus**, weil nachts eine
        Störung gemeldet wurde – und das Ausbleiben wäre dann kein
        Signal mehr, sondern ein Nebeneffekt."""
        stand = bericht.Stand()
        stand.schreiben(
            self.datei, jetzt=datetime(2026, 10, 7, 7, 0), mails=100
        )

        stand.schreiben(self.datei, stoerung="Abruf scheitert")

        wieder = bericht.Stand.lesen(self.datei)
        self.assertEqual(wieder.zuletzt, datetime(2026, 10, 7, 7, 0))
        self.assertEqual(wieder.stoerung, "Abruf scheitert")

    def test_eine_kaputte_datei_wirft_nicht(self):
        self.datei.write_text("{kein json", encoding="utf-8")

        self.assertIsNone(bericht.Stand.lesen(self.datei).zuletzt)

    def test_geschrieben_wird_ueber_eine_zwischendatei(self):
        """Ein Stromausfall mitten im Schreiben soll keinen halben Stand
        hinterlassen."""
        stand = bericht.Stand()
        stand.schreiben(self.datei, jetzt=datetime(2026, 10, 7, 7, 0), mails=1)

        daten = json.loads(self.datei.read_text(encoding="utf-8"))
        self.assertEqual(daten["mails"], 1)
        self.assertFalse(
            list(self.datei.parent.glob("*.neu")), "Zwischendatei blieb liegen"
        )


class VersandTest(unittest.TestCase):
    class FakeSMTP:
        """Ein Postausgangsserver, der nichts verschickt."""

        def __init__(self, server, anschluss):
            self.server = server
            self.anschluss = anschluss
            self.tls = False
            self.anmeldung = None
            self.nachricht = None

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def starttls(self):
            self.tls = True

        def login(self, benutzer, passwort):
            self.anmeldung = (benutzer, passwort)

        def send_message(self, nachricht):
            self.nachricht = nachricht

    def _lage(self, **mehr):
        werte = dict(
            an="chef@example.org", smtp="mail.example.org", anschluss=587,
            von="archiv@example.org", benutzer="archiv@example.org",
        )
        werte.update(mehr)
        return bericht.Lage(**werte)

    def test_die_mail_geht_mit_betreff_und_text_hinaus(self):
        gesehen = []

        def verbinden(server, anschluss):
            gesehen.append(self.FakeSMTP(server, anschluss))
            return gesehen[-1]

        bericht.senden(
            self._lage(), "Betreff", "Text", "geheim", verbinden=verbinden
        )

        post = gesehen[0]
        self.assertEqual(post.nachricht["Subject"], "Betreff")
        self.assertEqual(post.nachricht["To"], "chef@example.org")
        self.assertIn("Text", post.nachricht.get_content())

    def test_immer_mit_starttls(self):
        """**Ohne geht es nicht weiter.** Der Bericht nennt Zahlen, die
        niemanden sonst angehen, und die Anmeldung ginge im Klartext
        über die Leitung."""
        gesehen = []

        def verbinden(server, anschluss):
            gesehen.append(self.FakeSMTP(server, anschluss))
            return gesehen[-1]

        bericht.senden(self._lage(), "B", "T", "geheim", verbinden=verbinden)

        self.assertTrue(gesehen[0].tls)

    def test_ohne_benutzer_keine_anmeldung(self):
        """Mancher Postausgangsserver im eigenen Netz will keine."""
        gesehen = []

        def verbinden(server, anschluss):
            gesehen.append(self.FakeSMTP(server, anschluss))
            return gesehen[-1]

        bericht.senden(
            self._lage(benutzer=""), "B", "T", "", verbinden=verbinden
        )

        self.assertIsNone(gesehen[0].anmeldung)

    def test_ohne_einrichtung_eine_klare_absage(self):
        with self.assertRaises(bericht.VersandFehler):
            bericht.senden(bericht.Lage(), "B", "T")

    def test_ein_fehler_des_servers_kommt_als_versandfehler(self):
        def verbinden(server, anschluss):
            raise OSError("Verbindung abgelehnt")

        with self.assertRaises(bericht.VersandFehler) as gefangen:
            bericht.senden(self._lage(), "B", "T", verbinden=verbinden)

        self.assertIn("abgelehnt", str(gefangen.exception))


if __name__ == "__main__":
    unittest.main()
