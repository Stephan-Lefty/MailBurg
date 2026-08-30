"""Regeln, die Post beim Aufnehmen einstufen.

In einem Geschäftsarchiv landet private Post – der Verein, die Familie,
der Handwerker für die eigene Wohnung. Sie liegt dort unter
Aufbewahrungsfristen, die für sie nicht gelten: zehn Jahre Löschsperre
auf einer Einladung zum Grillfest. Umgekehrt verlangt die DSGVO, dass
personenbezogene Daten verschwinden, sobald der Zweck entfällt.

Beschlossen mit Stephan am 2026-08-30: Die Regel greift **beim
Einstufen**, nicht beim Abruf. Eine Regel, die schon das Holen
verhindert, wirft weg, was sie trifft – und ein Archivprogramm soll im
Zweifel behalten.
"""

from __future__ import annotations

import unittest

from mailburg.core.regeln import Regel, Regelwerk
from mailburg.core.retention import Category


class RegelTest(unittest.TestCase):
    def test_ordner_mit_platzhalter(self):
        regel = Regel(feld="ordner", muster="INBOX/Privat*")

        self.assertTrue(regel.trifft(ordner="INBOX/Privat"))
        self.assertTrue(regel.trifft(ordner="INBOX/Privates/Verein"))
        self.assertFalse(regel.trifft(ordner="INBOX/Rechnungen"))

    def test_absender_als_ganze_domain(self):
        regel = Regel(feld="von", muster="*@verein.example")

        self.assertTrue(regel.trifft(von="vorstand@verein.example"))
        self.assertFalse(regel.trifft(von="post@firma.example"))

    def test_gross_und_kleinschreibung_ist_egal(self):
        """»Privat« meint auch »privat« – und Domains sind ohnehin gleich."""
        regel = Regel(feld="von", muster="*@Verein.Example")

        self.assertTrue(regel.trifft(von="VORSTAND@verein.example"))

    def test_eine_abgeschaltete_regel_trifft_nie(self):
        regel = Regel(feld="ordner", muster="*", aktiv=False)

        self.assertFalse(regel.trifft(ordner="beliebig"))

    def test_leeres_feld_trifft_nicht(self):
        """Eine Mail ohne Absender darf nicht auf »*« hereinfallen."""
        regel = Regel(feld="von", muster="*")

        self.assertFalse(regel.trifft(von=""))

    def test_ein_unbekanntes_feld_wird_abgelehnt(self):
        with self.assertRaises(ValueError):
            Regel(feld="betreff", muster="Rechnung")

    def test_ein_leeres_muster_wird_abgelehnt(self):
        """Es träfe alles oder nichts – beides ist kein Wunsch."""
        with self.assertRaises(ValueError):
            Regel(feld="ordner", muster="   ")

    def test_die_beschreibung_nennt_alles_wesentliche(self):
        regel = Regel(feld="von", muster="*@verein.example")

        text = regel.beschreibung()

        self.assertIn("Absender", text)
        self.assertIn("verein.example", text)
        self.assertIn("privat", text)

    def test_hin_und_zurueck(self):
        regel = Regel(
            feld="an", muster="familie@*", kategorie=Category.PRIVAT,
            bemerkung="Post an die Familie",
        )

        wieder = Regel.aus_daten(regel.als_daten())

        self.assertEqual(wieder, regel)


class RegelwerkTest(unittest.TestCase):
    def test_die_erste_passende_gewinnt(self):
        """Nicht die schärfste, nicht die letzte – die erste."""
        werk = Regelwerk([
            Regel(feld="ordner", muster="INBOX/Privat",
                  kategorie=Category.PRIVAT),
            Regel(feld="ordner", muster="INBOX/*",
                  kategorie=Category.HANDELSBRIEF),
        ])

        kategorie, _ = werk.einstufung(ordner="INBOX/Privat")

        self.assertEqual(kategorie, Category.PRIVAT)

    def test_eine_ausnahme_schiebt_man_nach_oben(self):
        werk = Regelwerk([
            Regel(feld="von", muster="steuerberater@verein.example",
                  kategorie=Category.HANDELSBRIEF),
            Regel(feld="von", muster="*@verein.example",
                  kategorie=Category.PRIVAT),
        ])

        kategorie, _ = werk.einstufung(von="steuerberater@verein.example")

        self.assertEqual(kategorie, Category.HANDELSBRIEF)

    def test_ohne_treffer_kommt_nichts(self):
        """None heißt »keine Aussage« – nicht »unbestimmt«.

        Der Unterschied ist wichtig: UNBESTIMMT wird wie die längste
        Aufbewahrungspflicht behandelt, wäre also eine Entscheidung.
        """
        werk = Regelwerk([Regel(feld="ordner", muster="INBOX/Privat")])

        self.assertIsNone(werk.einstufung(ordner="INBOX/Rechnungen"))

    def test_ein_leeres_regelwerk_sagt_nichts(self):
        self.assertIsNone(Regelwerk().einstufung(ordner="beliebig"))

    def test_kaputte_eintraege_werden_uebergangen(self):
        """Eine unbrauchbare Regel darf das Archiv nicht unbenutzbar machen."""
        werk = Regelwerk.aus_daten([
            {"feld": "ordner", "muster": "INBOX/Privat"},
            {"feld": "gibtsnicht", "muster": "x"},
            {"muster": ""},
            "kein Wörterbuch",
            {"feld": "von", "muster": "*@verein.example"},
        ])

        self.assertEqual(len(werk), 2)

    def test_auch_gar_keine_liste(self):
        self.assertEqual(len(Regelwerk.aus_daten(None)), 0)
        self.assertEqual(len(Regelwerk.aus_daten({"a": 1})), 0)


if __name__ == "__main__":
    unittest.main()


class RegelnAmArchivTest(unittest.TestCase):
    """Die Regel muss beim Aufnehmen wirklich greifen – und ins Journal."""

    def setUp(self) -> None:
        import tempfile
        from pathlib import Path
        from unittest import mock

        from mailburg.core import paths
        from mailburg.core.archive import Archive, Mode
        from mailburg.core.retention import Jurisdiction

        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        patcher = mock.patch.object(
            paths, "data_dir", return_value=self.base / "daten"
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        (self.base / "daten").mkdir(parents=True, exist_ok=True)

        self.archiv = Archive.create(
            self.base / "archiv", mode=Mode.GESCHAEFTLICH,
            jurisdiction=Jurisdiction.DE, name="Probe",
        )
        self.addCleanup(self._zu)
        self.addCleanup(self._tmp.cleanup)

    def _zu(self):
        try:
            self.archiv.close()
        except Exception:  # noqa: BLE001
            pass

    def _mail(self, von: str, betreff: str = "Probe") -> bytes:
        return (
            f"From: {von}\r\n"
            f"To: post@firma.example\r\n"
            f"Subject: {betreff}\r\n"
            f"Date: Sat, 30 Aug 2026 09:00:00 +0200\r\n"
            f"Message-ID: <{betreff}@example>\r\n"
            f"\r\nText.\r\n"
        ).encode()

    def _kategorie(self, digest: str) -> str:
        zeile = self.archiv.index.db.execute(
            "SELECT category FROM messages WHERE hash = ?", (digest,)
        ).fetchone()
        return zeile["category"] or ""

    def test_ohne_regeln_bleibt_alles_unbestimmt(self):
        ergebnis = self.archiv.add(
            self._mail("verein@verein.example"),
            account="firma", folder="INBOX",
        )

        self.assertEqual(self._kategorie(ergebnis.hash), "unbestimmt")

    def test_eine_regel_stuft_beim_aufnehmen_ein(self):
        self.archiv.regeln_setzen(
            Regelwerk([Regel(feld="von", muster="*@verein.example")])
        )

        ergebnis = self.archiv.add(
            self._mail("vorstand@verein.example"),
            account="firma", folder="INBOX",
        )

        self.assertEqual(self._kategorie(ergebnis.hash), "privat")

    def test_was_die_regel_nicht_trifft_bleibt_unbestimmt(self):
        self.archiv.regeln_setzen(
            Regelwerk([Regel(feld="von", muster="*@verein.example")])
        )

        ergebnis = self.archiv.add(
            self._mail("kunde@firma.example", betreff="Auftrag"),
            account="firma", folder="INBOX",
        )

        self.assertEqual(self._kategorie(ergebnis.hash), "unbestimmt")

    def test_die_regel_steht_als_urheber_im_journal(self):
        """Nicht der angemeldete Mensch – sonst führt das Protokoll irre."""
        self.archiv.regeln_setzen(
            Regelwerk([Regel(feld="ordner", muster="INBOX/Privat")])
        )

        self.archiv.add(
            self._mail("wer@example.org"),
            account="firma", folder="INBOX/Privat",
        )

        eintraege = [
            e for e in self.archiv.journal.read_all()
            if e.get("op") == "classify"
        ]
        self.assertEqual(len(eintraege), 1)
        self.assertEqual(eintraege[0]["actor"], "Regel")
        self.assertIn("INBOX/Privat", eintraege[0]["note"])

    def test_das_aendern_der_regeln_steht_im_journal(self):
        """Welche Regel wann galt, gehört zur Verfahrensdokumentation."""
        self.archiv.regeln_setzen(
            Regelwerk([Regel(feld="ordner", muster="INBOX/Privat")])
        )

        eintraege = [
            e for e in self.archiv.journal.read_all()
            if e.get("op") == "rules"
        ]
        self.assertEqual(len(eintraege), 1)
        self.assertEqual(eintraege[0]["rules"][0]["muster"], "INBOX/Privat")
        self.assertEqual(eintraege[0]["previous"], [])

    def test_die_regeln_ueberleben_das_schliessen(self):
        self.archiv.regeln_setzen(
            Regelwerk([Regel(feld="von", muster="*@verein.example")])
        )
        wurzel = self.archiv.root
        self.archiv.close()

        from mailburg.core.archive import Archive

        with Archive.open(wurzel) as wieder:
            self.assertEqual(len(wieder.regeln), 1)
            self.assertEqual(wieder.regeln.regeln[0].muster, "*@verein.example")

    def test_dieselben_regeln_noch_einmal_setzen_schreibt_nichts(self):
        """Sonst wüchse das Journal bei jedem Öffnen des Dialogs."""
        werk = Regelwerk([Regel(feld="ordner", muster="INBOX/Privat")])
        self.archiv.regeln_setzen(werk)
        self.archiv.regeln_setzen(werk)

        eintraege = [
            e for e in self.archiv.journal.read_all()
            if e.get("op") == "rules"
        ]
        self.assertEqual(len(eintraege), 1)

    def test_eine_spaetere_regel_ruehrt_bestehende_post_nicht_an(self):
        """Eine Entscheidung von Hand wiegt schwerer als ein Suchmuster."""
        ergebnis = self.archiv.add(
            self._mail("vorstand@verein.example"),
            account="firma", folder="INBOX",
        )
        self.archiv.classify(ergebnis.hash, Category.HANDELSBRIEF)

        self.archiv.regeln_setzen(
            Regelwerk([Regel(feld="von", muster="*@verein.example")])
        )

        self.assertEqual(self._kategorie(ergebnis.hash), "handelsbrief")
