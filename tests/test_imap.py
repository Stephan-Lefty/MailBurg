"""Der IMAP-Abruf, geprüft gegen einen nachgebildeten Server."""

from __future__ import annotations

import unittest

from mailburg.core.accounts import Konto
from mailburg.core.sync import Abrufzustand
from mailburg.sources.imap import ImapSource, utf7_dekodieren
from tests.fake_imap import AblehnenderImap, FakeImap, FakeOrdner, mail


def konto(**abweichend) -> Konto:
    vorgabe = {
        "name": "Firma",
        "server": "imap.example.org",
        "benutzer": "post@example.org",
    }
    vorgabe.update(abweichend)
    return Konto(**vorgabe)


def zustand(tmp) -> Abrufzustand:
    return Abrufzustand("egal", datei=tmp / "abruf.json")


class UTF7Test(unittest.TestCase):
    """Ordnernamen, wie IMAP sie überträgt."""

    def test_reiner_ascii_name_bleibt(self):
        self.assertEqual(utf7_dekodieren("INBOX"), "INBOX")
        self.assertEqual(utf7_dekodieren("INBOX/Rechnungen"), "INBOX/Rechnungen")

    def test_umlaute_werden_aufgeloest(self):
        self.assertEqual(utf7_dekodieren("Entw&APw-rfe"), "Entwürfe")
        self.assertEqual(utf7_dekodieren("Gel&APY-scht"), "Gelöscht")

    def test_kaufmanns_und_steht_fuer_sich(self):
        # "&-" ist die Umschreibung für ein einzelnes kaufmännisches Und.
        self.assertEqual(utf7_dekodieren("Meier &- S&APY-hne"), "Meier & Söhne")

    def test_mehrere_bloecke_in_einem_namen(self):
        self.assertEqual(
            utf7_dekodieren("&APw-ber/&APY-fter"), "über/öfter"
        )

    def test_unsinniger_block_bricht_nicht_ab(self):
        # Lieber ein schiefer Name als ein abgebrochener Abruf.
        ergebnis = utf7_dekodieren("Kunden&&&-Partner")
        self.assertIn("Kunden", ergebnis)


class OrdnerlisteTest(unittest.TestCase):
    """Welche Ordner überhaupt archiviert werden."""

    def quelle(self, ordner, *, trenner="/", k=None):
        return ImapSource(k or konto(), verbindung=FakeImap(ordner, trenner))

    def test_gewoehnliche_ordner_kommen_mit(self):
        q = self.quelle([
            FakeOrdner("INBOX", {1: mail("eins")}),
            FakeOrdner("Archiv", {2: mail("zwei")}),
        ])
        self.assertEqual(q.folders(), ["Archiv", "INBOX"])

    def test_papierkorb_und_spam_bleiben_draussen(self):
        q = self.quelle([
            FakeOrdner("INBOX", {}),
            FakeOrdner("Trash", {}),
            FakeOrdner("Junk", {}),
            FakeOrdner("Entw&APw-rfe", {}),
        ])
        self.assertEqual(q.folders(), ["INBOX"])

    def test_unterordner_des_papierkorbs_ebenfalls(self):
        q = self.quelle([
            FakeOrdner("INBOX", {}),
            FakeOrdner("Trash/Alt", {}),
        ])
        self.assertEqual(q.folders(), ["INBOX"])

    def test_gmail_alle_nachrichten_bleibt_draussen(self):
        # Der teuerste Fehler: Dieser Ordner enthält alles ein zweites Mal.
        q = self.quelle([
            FakeOrdner("INBOX", {}),
            FakeOrdner("[Gmail]/Alle Nachrichten", {}, merkmale="\\All \\HasNoChildren"),
        ])
        self.assertEqual(q.folders(), ["INBOX"])

    def test_noselect_ist_kein_ordner(self):
        q = self.quelle([
            FakeOrdner("Kunden", {}, merkmale="\\Noselect \\HasChildren"),
            FakeOrdner("Kunden/Meier", {}),
        ])
        self.assertEqual(q.folders(), ["Kunden/Meier"])

    def test_fremdes_trennzeichen_wird_vereinheitlicht(self):
        # Manche Server trennen mit einem Punkt statt mit einem Schrägstrich.
        q = self.quelle([FakeOrdner("INBOX.Kunden.Meier", {})], trenner=".")
        self.assertEqual(q.folders(), ["INBOX/Kunden/Meier"])

    def test_umlaute_im_ordnernamen(self):
        q = self.quelle([FakeOrdner("Beh&APY-rden", {})])
        self.assertEqual(q.folders(), ["Behörden"])

    def test_eigene_ausschlussliste(self):
        q = self.quelle(
            [FakeOrdner("INBOX", {}), FakeOrdner("Privat", {})],
            k=konto(ausschluss=["Privat"]),
        )
        self.assertEqual(q.folders(), ["INBOX"])


class AbrufTest(unittest.TestCase):
    """Was tatsächlich geholt wird."""

    def test_ohne_vorwissen_kommt_alles(self):
        server = FakeImap([FakeOrdner("INBOX", {1: mail("a"), 2: mail("b")})])
        q = ImapSource(konto(), verbindung=server)
        self.assertEqual([m.uid for m in q.iter_messages()], [1, 2])

    def test_das_postfach_wird_nicht_angefasst(self):
        # Nur lesend öffnen und mit PEEK holen - sonst gilt ungelesene
        # Post nach dem Archivieren als gelesen.
        server = FakeImap([FakeOrdner("INBOX", {1: mail("a")})])
        list(ImapSource(konto(), verbindung=server).iter_messages())
        self.assertEqual(server.nur_lesend, [True])
        self.assertTrue(any("BODY.PEEK[]" in was for was in server.abgefragt))
        self.assertFalse(any("BODY[]" in was for was in server.abgefragt))

    def test_nur_was_neu_ist(self):
        server = FakeImap([FakeOrdner("INBOX", {1: mail("a"), 2: mail("b"), 3: mail("c")})])
        q = ImapSource(konto(), verbindung=server, hoechststand=lambda _o: 2)
        self.assertEqual([m.uid for m in q.iter_messages()], [3])

    def test_nichts_neues_heisst_nichts(self):
        # Der Stern in "UID 4:*" liefert die höchste UID auch dann, wenn
        # sie kleiner ist. Ohne Nachfiltern käme Mail 3 bei jedem Lauf neu.
        server = FakeImap([FakeOrdner("INBOX", {1: mail("a"), 2: mail("b"), 3: mail("c")})])
        q = ImapSource(konto(), verbindung=server, hoechststand=lambda _o: 3)
        self.assertEqual(list(q.iter_messages()), [])

    def test_voll_holt_trotz_hoechststand_alles(self):
        server = FakeImap([FakeOrdner("INBOX", {1: mail("a"), 2: mail("b")})])
        q = ImapSource(konto(), verbindung=server, hoechststand=lambda _o: 2, voll=True)
        self.assertEqual([m.uid for m in q.iter_messages()], [1, 2])

    def test_ordner_und_marken_kommen_mit(self):
        server = FakeImap([FakeOrdner("Beh&APY-rden", {7: mail("Bescheid")})])
        nachricht = next(iter(ImapSource(konto(), verbindung=server).iter_messages()))
        self.assertEqual(nachricht.folder, "Behörden")
        self.assertEqual(nachricht.uid, 7)
        self.assertIn("Seen", nachricht.flags)

    def test_inhalt_kommt_unveraendert_an(self):
        roh = mail("Unverändert")
        server = FakeImap([FakeOrdner("INBOX", {1: roh})])
        nachricht = next(iter(ImapSource(konto(), verbindung=server).iter_messages()))
        self.assertEqual(nachricht.raw, roh)

    def test_leerer_ordner_kostet_keinen_abruf(self):
        server = FakeImap([FakeOrdner("INBOX", {})])
        self.assertEqual(list(ImapSource(konto(), verbindung=server).iter_messages()), [])
        self.assertEqual(server.abgefragt, [])

    def test_ein_stoerrischer_ordner_kostet_nicht_die_anderen(self):
        server = AblehnenderImap(
            [FakeOrdner("Archiv", {1: mail("a")}), FakeOrdner("INBOX", {2: mail("b")})],
            sperrt="Archiv",
        )
        q = ImapSource(konto(), verbindung=server)
        self.assertEqual([m.uid for m in q.iter_messages()], [2])
        self.assertTrue(any("Archiv" in w for w in q.warnungen))

    def test_grosse_mails_werden_auf_bloecke_verteilt(self):
        # Sonst lägen fünfzig Anhänge zugleich im Arbeitsspeicher.
        from mailburg.sources import imap as imap_modul

        gross = 8 * 1024 * 1024
        mails = {n: mail(f"gross {n}", groesse=gross) for n in range(1, 7)}
        server = FakeImap([FakeOrdner("INBOX", mails)])
        q = ImapSource(konto(), verbindung=server)
        self.assertEqual(len(list(q.iter_messages())), 6)

        inhaltsabrufe = [w for w in server.abgefragt if "BODY.PEEK[]" in w]
        self.assertGreater(len(inhaltsabrufe), 1, "alles in einem Zug geholt")
        self.assertLess(gross * 6, imap_modul.BLOCK_BYTES * len(inhaltsabrufe))


class ZustandTest(unittest.TestCase):
    """Zusammenspiel mit dem Abrufzustand."""

    def setUp(self):
        import tempfile
        from pathlib import Path

        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_uidvalidity_wird_festgehalten(self):
        z = zustand(self.tmp)
        server = FakeImap([FakeOrdner("INBOX", {1: mail("a")}, uidvalidity=4242)])
        list(ImapSource(konto(), verbindung=server, zustand=z).iter_messages())
        self.assertEqual(z.uidvalidity("Firma", "INBOX"), 4242)

    def test_neue_uidvalidity_erzwingt_vollabruf(self):
        # Der Server hat die UIDs neu vergeben. Was wir über den Ordner zu
        # wissen glaubten, ist damit wertlos.
        z = zustand(self.tmp)
        z.ordner_gesehen("Firma", "INBOX", 1000)

        server = FakeImap([FakeOrdner("INBOX", {1: mail("a"), 2: mail("b")}, uidvalidity=2000)])
        q = ImapSource(konto(), verbindung=server, zustand=z, hoechststand=lambda _o: 5)
        self.assertEqual([m.uid for m in q.iter_messages()], [1, 2])

    def test_gleiche_uidvalidity_laesst_den_hoechststand_gelten(self):
        z = zustand(self.tmp)
        z.ordner_gesehen("Firma", "INBOX", 1000)

        server = FakeImap([FakeOrdner("INBOX", {1: mail("a"), 2: mail("b")}, uidvalidity=1000)])
        q = ImapSource(konto(), verbindung=server, zustand=z, hoechststand=lambda _o: 1)
        self.assertEqual([m.uid for m in q.iter_messages()], [2])

    def test_vorgemerkte_mail_wird_erneut_geholt(self):
        # Sie war beim letzten Lauf gescheitert und liegt unterhalb des
        # Höchststands - ohne Vormerkung fehlte sie für immer.
        z = zustand(self.tmp)
        z.ordner_gesehen("Firma", "INBOX", 1000)
        z.vormerken("Firma", "INBOX", 2)

        server = FakeImap([FakeOrdner("INBOX", {1: mail("a"), 2: mail("b"), 3: mail("c")})])
        q = ImapSource(konto(), verbindung=server, zustand=z, hoechststand=lambda _o: 3)
        self.assertEqual([m.uid for m in q.iter_messages()], [2])

    def test_geloeschte_vormerkung_verschwindet(self):
        # Der Anwender hat die Mail inzwischen weggeworfen. Sie bei jedem
        # Lauf erneut anzufordern, wäre sinnlos.
        z = zustand(self.tmp)
        z.ordner_gesehen("Firma", "INBOX", 1000)
        z.vormerken("Firma", "INBOX", 99)

        server = FakeImap([FakeOrdner("INBOX", {1: mail("a")})])
        q = ImapSource(konto(), verbindung=server, zustand=z, hoechststand=lambda _o: 1)
        self.assertEqual(list(q.iter_messages()), [])
        self.assertEqual(z.nachzuegler("Firma", "INBOX"), [])

    def test_nicht_geliefertes_wird_vorgemerkt(self):
        # Zwischen Suche und Abruf ist die Mail verschwunden. Beim nächsten
        # Lauf wird sie noch einmal angefordert.
        server = FakeImap([FakeOrdner("INBOX", {1: mail("a"), 2: mail("b")})])
        z = zustand(self.tmp)
        q = ImapSource(konto(), verbindung=server, zustand=z)

        echtes_holen = server._holen

        def verschluckt(bereich, was):
            if "BODY.PEEK[]" in was:
                server.aktuell.mails.pop(2, None)
            return echtes_holen(bereich, was)

        server._holen = verschluckt
        self.assertEqual([m.uid for m in q.iter_messages()], [1])
        self.assertEqual(z.nachzuegler("Firma", "INBOX"), [2])


if __name__ == "__main__":
    unittest.main()
