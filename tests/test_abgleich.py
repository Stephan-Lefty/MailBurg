"""Der Nachweis vor dem Aufräumen.

Hier zählt nicht nur, dass richtig gezählt wird, sondern vor allem, dass
im Zweifel **nicht** grünes Licht kommt. Auf diesen Befund hin löscht
jemand Post auf einem Server – eine Auskunft, die nur meistens stimmt,
wäre schlimmer als gar keine.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from mailburg.core import abgleich, paths
from mailburg.core.accounts import Konto
from mailburg.core.archive import Archive
from mailburg.core.importer import importieren
from mailburg.core.sync import Abrufzustand
from mailburg.sources.imap import ImapSource
from tests.fake_imap import FakeImap, FakeOrdner, mail


class AbgleichTestFall(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        patcher = mock.patch.object(paths, "data_dir", return_value=self.base / "daten")
        patcher.start()
        self.addCleanup(patcher.stop)

        self.archive = Archive.create(self.base / "archiv", name="Test")
        self.addCleanup(self._abbauen)
        self.konto = Konto(name="Firma", server="imap.example.org", benutzer="post")
        self.zustand = Abrufzustand("test", datei=self.base / "abruf.json")

    def _abbauen(self) -> None:
        try:
            self.archive.close()
        except Exception:  # noqa: BLE001
            pass
        self._tmp.cleanup()

    def abrufen(self, server: FakeImap) -> None:
        quelle = ImapSource(
            self.konto, verbindung=server, zustand=self.zustand,
            hoechststand=lambda o: self.archive.index.max_uid("Firma", o),
        )
        importieren(self.archive, quelle, mit_anhangstext=False)

    def pruefen(self, server: FakeImap, stichtag=date(2026, 3, 1)):
        quelle = ImapSource(self.konto, verbindung=server, zustand=self.zustand)
        return abgleich.pruefen(
            self.archive, quelle, "Firma", stichtag, zustand=self.zustand
        )


class VollstaendigTest(AbgleichTestFall):
    def test_alles_archiviert_ergibt_gruenes_licht(self):
        server = FakeImap([FakeOrdner("INBOX", {1: mail("a"), 2: mail("b")})])
        self.abrufen(server)

        befund = self.pruefen(server)
        self.assertEqual(befund.geprueft, 2)
        self.assertEqual(befund.fehlend, 0)
        self.assertTrue(befund.unbedenklich)
        self.assertIn("gefahrlos", abgleich.urteil(befund))

    def test_leeres_postfach_ist_kein_fehler(self):
        server = FakeImap([FakeOrdner("INBOX", {})])
        befund = self.pruefen(server)
        self.assertTrue(befund.unbedenklich)
        self.assertIn("nichts", abgleich.urteil(befund).lower())

    def test_mehrere_ordner_einzeln_ausgewiesen(self):
        server = FakeImap([
            FakeOrdner("INBOX", {1: mail("a")}),
            FakeOrdner("Archiv", {5: mail("b")}),
        ])
        self.abrufen(server)
        befund = self.pruefen(server)
        self.assertEqual({o.ordner for o in befund.ordner}, {"INBOX", "Archiv"})
        self.assertTrue(all(o.vollstaendig for o in befund.ordner))


class LueckenTest(AbgleichTestFall):
    def test_nicht_archivierte_mail_wird_gemeldet(self):
        # Der Fall, um den es geht: Der Server hat mehr als das Archiv.
        ordner = FakeOrdner("INBOX", {1: mail("a")})
        server = FakeImap([ordner])
        self.abrufen(server)

        ordner.mails[2] = mail("noch nicht geholt")
        befund = self.pruefen(server)

        self.assertEqual(befund.fehlend, 1)
        self.assertEqual(befund.ordner[0].fehlend, [2])
        self.assertFalse(befund.unbedenklich)

    def test_urteil_verlangt_erst_abrufen(self):
        ordner = FakeOrdner("INBOX", {1: mail("a")})
        server = FakeImap([ordner])
        self.abrufen(server)
        ordner.mails[2] = mail("neu")

        text = abgleich.urteil(self.pruefen(server))
        self.assertIn("fehlen", text)
        self.assertIn("abrufen", text)
        self.assertIn("nichts", text)

    def test_nach_dem_abrufen_ist_es_wieder_gut(self):
        ordner = FakeOrdner("INBOX", {1: mail("a")})
        server = FakeImap([ordner])
        self.abrufen(server)
        ordner.mails[2] = mail("neu")
        self.assertFalse(self.pruefen(server).unbedenklich)

        self.abrufen(server)
        self.assertTrue(self.pruefen(server).unbedenklich)


class UnsicherheitTest(AbgleichTestFall):
    """Wenn der Vergleich nicht taugt, darf kein grünes Licht kommen."""

    def test_geaenderte_nummerierung_macht_den_befund_unklar(self):
        # Nach einem Serverumzug zeigen alte UIDs ins Leere. Ein Vergleich
        # über sie behauptete Vollständigkeit, die niemand belegen kann.
        ordner = FakeOrdner("INBOX", {1: mail("a"), 2: mail("b")}, uidvalidity=1000)
        server = FakeImap([ordner])
        self.abrufen(server)

        ordner.uidvalidity = 2000
        befund = self.pruefen(server)

        self.assertTrue(befund.ordner[0].uidvalidity_geaendert)
        self.assertTrue(befund.unklar)
        self.assertFalse(befund.unbedenklich)

    def test_urteil_bei_geaenderter_nummerierung_warnt(self):
        ordner = FakeOrdner("INBOX", {1: mail("a")}, uidvalidity=1000)
        server = FakeImap([ordner])
        self.abrufen(server)
        ordner.uidvalidity = 2000

        text = abgleich.urteil(self.pruefen(server))
        self.assertIn("nichts löschen", text)
        self.assertIn("--voll", text)

    def test_ein_fehler_beim_abfragen_ist_kein_gruenes_licht(self):
        server = FakeImap([FakeOrdner("INBOX", {1: mail("a")})])
        quelle = ImapSource(self.konto, verbindung=server)

        def scheitern(_stichtag):
            raise OSError("Verbindung abgebrochen")

        quelle.uids_vor = scheitern
        befund = abgleich.pruefen(self.archive, quelle, "Firma", date(2026, 3, 1))

        self.assertTrue(befund.unklar)
        self.assertFalse(befund.unbedenklich)
        self.assertIn("nicht durchgelaufen", abgleich.urteil(befund))


class StichtagTest(unittest.TestCase):
    def test_tage_werden_zu_einem_datum(self):
        self.assertEqual(
            abgleich.stichtag_aus_tagen(180, heute=date(2026, 8, 26)),
            date(2026, 2, 27),
        )

    def test_null_tage_ist_heute(self):
        self.assertEqual(
            abgleich.stichtag_aus_tagen(0, heute=date(2026, 8, 26)),
            date(2026, 8, 26),
        )


class DatumsformatTest(unittest.TestCase):
    """IMAP verlangt englische Monatskürzel, unabhängig vom System."""

    def test_monat_wird_englisch_abgekuerzt(self):
        gesucht = []
        server = FakeImap([FakeOrdner("INBOX", {1: mail("a")})])
        echtes_suchen = server._suchen

        def merken(ausdruck):
            gesucht.append(ausdruck)
            return echtes_suchen(ausdruck)

        server._suchen = merken
        konto = Konto(name="F", server="imap.example.org", benutzer="post")
        quelle = ImapSource(konto, verbindung=server)
        list(quelle.uids_vor(date(2026, 3, 7)))

        self.assertTrue(gesucht)
        self.assertIn("BEFORE 07-Mar-2026", gesucht[0])



class StichtagWirktTest(AbgleichTestFall):
    """Nur die alten Mails gehören in die Prüfung."""

    def test_junge_mails_bleiben_aussen_vor(self):
        # Sonst hielte der Abgleich Post für fehlend, die der Mailclient
        # ohnehin nicht anfassen wird - und gäbe grundlos Alarm.
        server = FakeImap([
            FakeOrdner(
                "INBOX",
                {1: mail("alt"), 2: mail("neu")},
                empfangen={1: date(2026, 1, 5), 2: date(2026, 8, 20)},
            )
        ])
        self.abrufen(server)

        befund = self.pruefen(server, stichtag=date(2026, 3, 1))
        self.assertEqual(befund.geprueft, 1, "nur die alte Mail zählt")
        self.assertTrue(befund.unbedenklich)

    def test_junge_nicht_archivierte_mail_loest_keinen_alarm_aus(self):
        ordner = FakeOrdner(
            "INBOX", {1: mail("alt")}, empfangen={1: date(2026, 1, 5)}
        )
        server = FakeImap([ordner])
        self.abrufen(server)

        # Frisch angekommen, noch nicht abgerufen - und trotzdem kein
        # Hindernis fürs Aufräumen alter Post.
        ordner.mails[2] = mail("ganz neu")
        ordner.empfangen[2] = date(2026, 8, 26)

        befund = self.pruefen(server, stichtag=date(2026, 3, 1))
        self.assertEqual(befund.fehlend, 0)
        self.assertTrue(befund.unbedenklich)

if __name__ == "__main__":
    unittest.main()
