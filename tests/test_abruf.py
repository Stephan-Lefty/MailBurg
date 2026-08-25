"""Der ganze Weg: Postfach → Archiv → zweiter Abruf.

Die Einzelteile sind anderswo geprüft. Hier geht es um die eine Zusage, die
den IMAP-Abruf überhaupt brauchbar macht: Der zweite Lauf holt nur, was
seitdem dazugekommen ist – und er holt *alles*, was dazugekommen ist.

Beides zusammen ist der Punkt. Ein Abruf, der zu viel holt, ist lästig; ein
Abruf, der zu wenig holt, verliert Post, ohne dass es jemand merkt.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mailburg.core import paths
from mailburg.core.accounts import Konto
from mailburg.core.archive import Archive
from mailburg.core.importer import importieren
from mailburg.core.sync import Abrufzustand
from mailburg.sources.imap import ImapSource
from tests.fake_imap import FakeImap, FakeOrdner, mail


class AbrufImArchivTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        patcher = mock.patch.object(paths, "data_dir", return_value=self.base / "daten")
        patcher.start()
        self.addCleanup(patcher.stop)

        self.archive = Archive.create(self.base / "archiv", name="Test")
        self.addCleanup(self._abbauen)

        self.konto = Konto(
            name="Firma", server="imap.example.org", benutzer="post@example.org"
        )
        self.zustand = Abrufzustand("test", datei=self.base / "abruf.json")

    def _abbauen(self) -> None:
        try:
            self.archive.close()
        except Exception:  # noqa: BLE001
            pass
        self._tmp.cleanup()

    # ---------------------------------------------------------------- Hilfe

    def abrufen(self, server: FakeImap, *, voll: bool = False):
        """Ein vollständiger Lauf, so wie ihn die Kommandozeile macht."""
        quelle = ImapSource(
            self.konto,
            verbindung=server,
            zustand=self.zustand,
            voll=voll,
            hoechststand=lambda ordner: self.archive.index.max_uid("Firma", ordner),
        )
        gescheitert: list = []

        def auf_fehler(nachricht, exc):
            gescheitert.append(nachricht)
            if nachricht.uid is not None:
                self.zustand.vormerken("Firma", nachricht.folder, nachricht.uid)

        # Ohne Anhangstext, damit kein Prozesspool anläuft - der hat mit
        # dem, was hier geprüft wird, nichts zu tun.
        stat = importieren(
            self.archive, quelle, mit_anhangstext=False, auf_fehler=auf_fehler
        )
        return stat, gescheitert

    # ---------------------------------------------------------------- Tests

    def test_erster_lauf_holt_alles(self):
        server = FakeImap([FakeOrdner("INBOX", {1: mail("eins"), 2: mail("zwei")})])
        stat, _ = self.abrufen(server)
        self.assertEqual(stat.gelesen, 2)
        self.assertEqual(stat.neu, 2)

    def test_zweiter_lauf_ohne_neue_post_holt_nichts(self):
        server = FakeImap([FakeOrdner("INBOX", {1: mail("eins"), 2: mail("zwei")})])
        self.abrufen(server)
        stat, _ = self.abrufen(server)
        self.assertEqual(stat.gelesen, 0)

    def test_zweiter_lauf_holt_genau_das_neue(self):
        ordner = FakeOrdner("INBOX", {1: mail("eins"), 2: mail("zwei")})
        server = FakeImap([ordner])
        self.abrufen(server)

        ordner.mails[3] = mail("drei")
        stat, _ = self.abrufen(server)
        self.assertEqual(stat.gelesen, 1)
        self.assertEqual(stat.neu, 1)

    def test_der_hoechststand_kommt_aus_dem_index(self):
        server = FakeImap([FakeOrdner("INBOX", {1: mail("eins"), 5: mail("fuenf")})])
        self.abrufen(server)
        self.assertEqual(self.archive.index.max_uid("Firma", "INBOX"), 5)

    def test_hoechststand_ueberlebt_den_neuaufbau_des_index(self):
        # Der Index ist wegwerfbar – aber nur, wenn nach dem Neuaufbau auch
        # der nächste Abruf noch weiß, wo er stehen geblieben war. Die UID
        # steht deshalb im Journal.
        ordner = FakeOrdner("INBOX", {1: mail("eins"), 2: mail("zwei")})
        server = FakeImap([ordner])
        self.abrufen(server)

        self.archive.rebuild_index(mit_anhangstext=False)
        self.assertEqual(self.archive.index.max_uid("Firma", "INBOX"), 2)

        ordner.mails[3] = mail("drei")
        stat, _ = self.abrufen(server)
        self.assertEqual(stat.gelesen, 1)

    def test_jeder_ordner_zaehlt_fuer_sich(self):
        # UIDs gelten je Ordner. Ein gemeinsamer Höchststand ließe den
        # Ordner mit den niedrigeren Nummern leerlaufen.
        server = FakeImap([
            FakeOrdner("INBOX", {10: mail("hoch")}),
            FakeOrdner("Archiv", {2: mail("niedrig")}),
        ])
        stat, _ = self.abrufen(server)
        self.assertEqual(stat.gelesen, 2)
        self.assertEqual(self.archive.index.max_uid("Firma", "INBOX"), 10)
        self.assertEqual(self.archive.index.max_uid("Firma", "Archiv"), 2)

    def test_dieselbe_mail_in_zwei_ordnern_liegt_einmal_auf_der_platte(self):
        gleich = mail("Rundschreiben")
        server = FakeImap([
            FakeOrdner("INBOX", {1: gleich}),
            FakeOrdner("Archiv", {1: gleich}),
        ])
        stat, _ = self.abrufen(server)
        self.assertEqual(stat.gelesen, 2)
        self.assertEqual(stat.neu, 1, "die Datei sollte nur einmal entstehen")
        # Beide Fundorte stehen aber im Journal und im Index.
        self.assertEqual(self.archive.index.statistics()["fundorte"], 2)

    def test_vollabruf_legt_nichts_doppelt_ab(self):
        server = FakeImap([FakeOrdner("INBOX", {1: mail("eins"), 2: mail("zwei")})])
        self.abrufen(server)
        vorher = self.archive.store.disk_usage()

        stat, _ = self.abrufen(server, voll=True)
        self.assertEqual(stat.gelesen, 2)
        self.assertEqual(stat.neu, 0, "alles war schon da")
        self.assertEqual(self.archive.store.disk_usage(), vorher)

    def test_neue_uidvalidity_holt_alles_erneut_ohne_zu_verdoppeln(self):
        ordner = FakeOrdner("INBOX", {1: mail("eins"), 2: mail("zwei")}, uidvalidity=1000)
        server = FakeImap([ordner])
        self.abrufen(server)

        # Der Server ist umgezogen und vergibt die Nummern neu.
        ordner.uidvalidity = 2000
        stat, _ = self.abrufen(server)
        self.assertEqual(stat.gelesen, 2)
        self.assertEqual(stat.neu, 0)

    def test_gescheiterte_mail_wird_beim_naechsten_lauf_nachgeholt(self):
        # Der Kern der Sache: Ohne Vormerkung zöge der Höchststand an der
        # kaputten Mail vorbei, und sie fehlte für immer im Archiv.
        heil, kaputt = mail("heil"), b"\xff\xfe kein gueltiger Mailkopf"
        ordner = FakeOrdner("INBOX", {1: kaputt, 2: heil})
        server = FakeImap([ordner])

        # autospec, damit der Ersatz sein ``self`` mitbekommt – sonst
        # rutschen alle Argumente um eins und es scheitert schlicht alles.
        with mock.patch.object(
            Archive, "add", autospec=True, side_effect=self._nur_heile(heil)
        ):
            stat, gescheitert = self.abrufen(server)

        self.assertEqual(stat.fehlgeschlagen, 1)
        self.assertEqual([n.uid for n in gescheitert], [1])
        self.assertEqual(self.zustand.nachzuegler("Firma", "INBOX"), [1])

        # Zweiter Lauf: Der Höchststand steht auf 2, trotzdem muss die 1
        # noch einmal angefordert werden.
        ordner.mails[1] = heil
        stat, _ = self.abrufen(server)
        self.assertEqual(stat.gelesen, 1)
        self.assertEqual(self.zustand.nachzuegler("Firma", "INBOX"), [])

    def _nur_heile(self, heil: bytes):
        """Lässt ``Archive.add`` an allem scheitern, was nicht ``heil`` ist."""
        echtes_add = Archive.add

        def ersatz(selbst, roh, **rest):
            if roh != heil:
                raise ValueError("Diese Mail ist nicht zu gebrauchen.")
            return echtes_add(selbst, roh, **rest)

        return ersatz

    def test_ausgeschlossene_ordner_landen_nicht_im_archiv(self):
        server = FakeImap([
            FakeOrdner("INBOX", {1: mail("geschaeftlich")}),
            FakeOrdner("Trash", {1: mail("weggeworfen")}),
        ])
        self.abrufen(server)
        ordner = {o for _, o, _ in self.archive.index.accounts()}
        self.assertEqual(ordner, {"INBOX"})

    def test_die_hash_kette_bleibt_heil(self):
        server = FakeImap([FakeOrdner("INBOX", {1: mail("eins"), 2: mail("zwei")})])
        self.abrufen(server)
        self.abrufen(server, voll=True)
        self.assertTrue(self.archive.verify()["ok"])


if __name__ == "__main__":
    unittest.main()
