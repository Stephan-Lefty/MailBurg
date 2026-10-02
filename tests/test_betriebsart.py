"""Betriebsart und Rechtsraum eines bestehenden Archivs ändern.

**Warum es das braucht.** Beim Anlegen wird beides gewählt, und dort
rät man. Stephans Firmenarchiv stand ein Jahr lang auf »privat«, bei
70.000 Geschäftsmails – also ohne Aufbewahrungsfristen und ohne
Fristprüfung beim Löschen. Aufgefallen ist es erst, als es auf einen
Server sollte, am 2026-10-02.

Ein Archiv, das man dafür neu aufbauen müsste, wäre in genau dem Fall
unbrauchbar, für den es gedacht ist.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mailburg.core.archive import Archive, Mode
from mailburg.core.retention import Jurisdiction


class BetriebsartTest(unittest.TestCase):
    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.wo = Path(self.ordner.name) / "Archiv"
        Archive.create(self.wo, name="Probe", mode=Mode.PRIVAT).close()

    def _eintraege(self) -> list[dict]:
        zeilen = []
        for datei in sorted((self.wo / "meta").glob("*.jsonl")):
            zeilen += [
                json.loads(z) for z in datei.read_text("utf-8").splitlines()
                if z.strip()
            ]
        return zeilen

    def test_privat_wird_geschaeftlich(self):
        with Archive.open(self.wo, exclusive=True) as archiv:
            self.assertTrue(
                archiv.betriebsart_setzen(Mode.GESCHAEFTLICH, actor="stephan")
            )

        with Archive.open(self.wo) as archiv:
            self.assertIs(archiv.mode, Mode.GESCHAEFTLICH)

    def test_die_aenderung_steht_im_journal(self):
        """**Mit Zeitpunkt und Urheber.**

        Wer Jahre später fragt, warum Fristen erst ab einem bestimmten
        Tag galten, findet hier die Antwort. Ohne Eintrag wäre die
        Umstellung von einer Manipulation nicht zu unterscheiden.
        """
        with Archive.open(self.wo, exclusive=True) as archiv:
            archiv.betriebsart_setzen(Mode.GESCHAEFTLICH, actor="stephan")

        letzter = self._eintraege()[-1]

        self.assertEqual(letzter["op"], "mode")
        self.assertEqual(letzter["mode"], "geschaeftlich")
        self.assertEqual(letzter["previous"], "privat")
        self.assertEqual(letzter["actor"], "stephan")
        self.assertTrue(letzter.get("ts"))

    def test_dieselbe_betriebsart_schreibt_nichts(self):
        """Sonst wüchse das Journal mit jedem versehentlichen Aufruf."""
        vorher = len(self._eintraege())

        with Archive.open(self.wo, exclusive=True) as archiv:
            self.assertFalse(archiv.betriebsart_setzen(Mode.PRIVAT))

        self.assertEqual(len(self._eintraege()), vorher)

    def test_rueckwaerts_geht_auch(self):
        """**Absicht.** Wer sich vertippt hat, soll es zurücknehmen
        können; die Sicherung liegt im Protokoll, nicht im Verbot."""
        with Archive.open(self.wo, exclusive=True) as archiv:
            archiv.betriebsart_setzen(Mode.GESCHAEFTLICH)
        with Archive.open(self.wo, exclusive=True) as archiv:
            self.assertTrue(archiv.betriebsart_setzen(Mode.PRIVAT))

        self.assertEqual(
            [e["op"] for e in self._eintraege()], ["create", "mode", "mode"]
        )

    def test_die_hashkette_bleibt_heil(self):
        """Eine Änderung an der Betriebsart darf die Kette nicht reißen."""
        with Archive.open(self.wo, exclusive=True) as archiv:
            archiv.betriebsart_setzen(Mode.GESCHAEFTLICH)

        with Archive.open(self.wo) as archiv:
            bericht = archiv.verify()

        self.assertTrue(bericht.get("chain_ok", True), bericht)

    def test_keine_mail_wird_angefasst(self):
        """**Das Wichtigste, und es steht auch in der Meldung.**

        Die Fristen gelten ab jetzt. Was vorher ohne Prüfung gelöscht
        wurde, bleibt gelöscht; keine Einstufung wird überschrieben.
        """
        roh = (
            b"From: wer@example.org\r\nTo: du@example.org\r\n"
            b"Subject: Probe\r\nDate: Mon, 12 May 2025 09:14:00 +0000\r\n"
            b"Message-ID: <1@example.org>\r\n\r\nText\r\n"
        )
        with Archive.open(self.wo, exclusive=True) as archiv:
            archiv.add(roh, account="buero", folder="INBOX")
            vorher = archiv.index.statistics()["mails"]

        with Archive.open(self.wo, exclusive=True) as archiv:
            archiv.betriebsart_setzen(Mode.GESCHAEFTLICH)

        with Archive.open(self.wo) as archiv:
            self.assertEqual(archiv.index.statistics()["mails"], vorher)


class RechtsraumTest(unittest.TestCase):
    """Nach welchem Recht die Fristen gelten.

    Gehört zur Betriebsart, ist aber nicht dasselbe: Ein Archiv kann
    geschäftlich sein und trotzdem im falschen Rechtsraum stehen – die
    Fristen unterscheiden sich zwischen DE, AT und CH.
    """

    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.wo = Path(self.ordner.name) / "Archiv"
        Archive.create(
            self.wo, name="Probe", mode=Mode.GESCHAEFTLICH,
            jurisdiction=Jurisdiction.DE,
        ).close()

    def test_das_land_laesst_sich_aendern(self):
        with Archive.open(self.wo, exclusive=True) as archiv:
            self.assertTrue(archiv.rechtsraum_setzen(Jurisdiction.AT))

        with Archive.open(self.wo) as archiv:
            self.assertIs(archiv.policy.jurisdiction, Jurisdiction.AT)

    def test_die_fristen_gehen_mit(self):
        """Sonst wäre die Umstellung eine Zahl ohne Wirkung."""
        from mailburg.core.retention import describe

        with Archive.open(self.wo) as archiv:
            vorher = describe(archiv.policy)
        with Archive.open(self.wo, exclusive=True) as archiv:
            archiv.rechtsraum_setzen(Jurisdiction.CH)
        with Archive.open(self.wo) as archiv:
            nachher = describe(archiv.policy)

        self.assertNotEqual(vorher, nachher)
        self.assertIn("Schweiz", nachher)

    def test_die_betriebsart_bleibt_unberuehrt(self):
        """Zwei Entscheidungen, zwei Befehle – sie hängen zusammen, sind
        aber nicht dasselbe."""
        with Archive.open(self.wo, exclusive=True) as archiv:
            archiv.rechtsraum_setzen(Jurisdiction.AT)

        with Archive.open(self.wo) as archiv:
            self.assertIs(archiv.mode, Mode.GESCHAEFTLICH)


if __name__ == "__main__":
    unittest.main()
