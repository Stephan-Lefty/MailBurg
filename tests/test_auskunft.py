"""Auskunft nach Art. 15 DSGVO.

Wer fragt, was über ihn gespeichert ist, hat Anspruch auf eine Kopie.
Bei einem Mailarchiv sind das die Nachrichten, in denen er vorkommt.

**Was hier ausdrücklich nicht geprüft wird, weil es niemand kann:** ob
die Kopie herausgegeben werden darf. Eine Mail an Herrn Müller enthält
oft auch Daten von Frau Schmidt, und Art. 15 Abs. 4 DSGVO sagt, dass
die Kopie die Rechte anderer nicht beeinträchtigen darf. Diese Abwägung
gehört zum Verantwortlichen. Geprüft wird deshalb, dass MailBurg das
*sagt*.
"""

from __future__ import annotations

import pathlib
import tempfile
import unittest
import zipfile

from mailburg.core import auskunft
from mailburg.core.archive import Archive


def _mail(von: str, an: str, betreff: str, jahr: int, kennung: str,
          text: str = "Inhalt") -> bytes:
    return (
        f"From: {von}\r\n"
        f"To: {an}\r\n"
        f"Subject: {betreff}\r\n"
        f"Date: Mon, 14 Jan {jahr} 09:00:00 +0100\r\n"
        f"Message-ID: <{kennung}@example.org>\r\n"
        f"\r\n"
        f"{text}\r\n"
    ).encode()


class ZusammenstellenTest(unittest.TestCase):
    def setUp(self) -> None:
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.pfad = pathlib.Path(self.ordner.name) / "Geschaeftsarchiv"
        Archive.create(self.pfad, mode="geschaeftlich").close()

        with Archive.open(self.pfad) as archiv:
            archiv.add(
                _mail("mueller@example.org", "wir@example.net",
                      "Anfrage", 2020, "a"),
                account="firma", folder="INBOX",
            )
            archiv.add(
                _mail("wir@example.net", "mueller@example.org",
                      "Antwort", 2020, "b"),
                account="firma", folder="Gesendet",
            )
            archiv.add(
                _mail("schmidt@example.org", "wir@example.net",
                      "Etwas anderes", 2021, "c",
                      text="Bitte an mueller@example.org weiterleiten."),
                account="firma", folder="INBOX",
            )

    def _befund(self, **zusatz):
        with Archive.open(self.pfad, exclusive=False) as archiv:
            return auskunft.zusammenstellen(
                archiv, "mueller@example.org", **zusatz
            )

    def test_absender_und_empfaenger(self) -> None:
        befund = self._befund()

        self.assertEqual(befund.anzahl, 2)
        self.assertEqual(befund.als_absender, 1)
        self.assertEqual(befund.als_empfaenger, 1)

    def test_blosse_erwaehnung_bleibt_draussen(self) -> None:
        """Voreingestellt aus – und das aus gutem Grund.

        Eine Erwähnung im Fließtext trifft oft Weiterleitungen, in denen
        die Person nicht Beteiligte ist. Und jede zusätzliche Mail im
        Paket ist eine, in der womöglich Daten Dritter stehen.
        """
        self.assertEqual(self._befund().anzahl, 2)

    def test_auf_wunsch_aber_doch(self) -> None:
        befund = self._befund(im_text=True)

        self.assertEqual(befund.anzahl, 3)
        self.assertEqual(befund.im_text, 1)

    def test_keine_doppelten(self) -> None:
        """Wer Absender und Empfänger war, zählt einmal."""
        with Archive.open(self.pfad) as archiv:
            archiv.add(
                _mail("mueller@example.org", "mueller@example.org",
                      "An sich selbst", 2022, "d"),
                account="firma", folder="INBOX",
            )

        befund = self._befund()
        haeufigkeiten = [t.hash for t in befund.treffer]
        self.assertEqual(len(haeufigkeiten), len(set(haeufigkeiten)))

    def test_nach_datum_sortiert(self) -> None:
        daten = [t.date for t in self._befund(im_text=True).treffer]
        self.assertEqual(daten, sorted(daten))


class PaketTest(unittest.TestCase):
    """Was im ZIP liegt und was das Begleitblatt sagt."""

    def setUp(self) -> None:
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.wurzel = pathlib.Path(self.ordner.name)
        self.pfad = self.wurzel / "Geschaeftsarchiv"
        Archive.create(self.pfad, mode="geschaeftlich").close()

        self.roh = _mail("mueller@example.org", "wir@example.net",
                         "Anfrage", 2020, "a")
        with Archive.open(self.pfad) as archiv:
            archiv.add(self.roh, account="firma", folder="INBOX")

    def _packen(self, name: str = "auskunft.zip"):
        with Archive.open(self.pfad) as archiv:
            befund = auskunft.zusammenstellen(archiv, "mueller@example.org")
            return auskunft.packen(archiv, befund, self.wurzel / name)

    def test_die_mails_liegen_unveraendert_darin(self) -> None:
        """Kein PDF, kein Umbau: Eine Mail als PDF zu drucken heißt, sie
        zu verändern – Anhänge fallen weg, Kopfzeilen verschwinden."""
        befund = self._packen()

        with zipfile.ZipFile(befund.ziel) as paket:
            namen = [n for n in paket.namelist() if n.endswith(".eml")]
            self.assertEqual(len(namen), 1)
            self.assertEqual(paket.read(namen[0]), self.roh)

    def test_das_begleitblatt_liegt_bei(self) -> None:
        befund = self._packen()

        with zipfile.ZipFile(befund.ziel) as paket:
            text = paket.read(auskunft.BEGLEITBLATT).decode("utf-8")

        self.assertIn("Artikel 15", text)
        self.assertIn("mueller@example.org", text)
        self.assertIn("Geschaeftsarchiv", text)

    def test_es_warnt_vor_daten_dritter(self) -> None:
        """Der wichtigste Satz im ganzen Paket.

        Art. 15 Abs. 4 DSGVO: Die Kopie darf die Rechte anderer Personen
        nicht beeinträchtigen. Wo diese Grenze verläuft, kann kein
        Programm entscheiden – aber es muss darauf hinweisen.
        """
        with zipfile.ZipFile(self._packen().ziel) as paket:
            text = paket.read(auskunft.BEGLEITBLATT).decode("utf-8")

        self.assertIn("DATEN DRITTER", text)
        self.assertIn("Abs. 4", text)
        self.assertIn("muss ein Mensch entscheiden", text)

    def test_und_vor_unvollstaendigkeit(self) -> None:
        with zipfile.ZipFile(self._packen().ziel) as paket:
            text = paket.read(auskunft.BEGLEITBLATT).decode("utf-8")

        self.assertIn("VOLLSTÄNDIGKEIT", text)
        self.assertIn("anderen Adresse", text.replace("weiteren Adressen",
                                                      "anderen Adresse"))

    def test_der_zweck_steht_dabei(self) -> None:
        """Art. 15 Abs. 1 lit. a verlangt die Verarbeitungszwecke."""
        with zipfile.ZipFile(self._packen().ziel) as paket:
            text = paket.read(auskunft.BEGLEITBLATT).decode("utf-8")

        self.assertIn("Zweck der Speicherung", text)
        self.assertIn("Aufbewahrungspflicht", text)

    def test_die_endung_wird_ergaenzt(self) -> None:
        befund = self._packen("auskunft")
        self.assertEqual(befund.ziel.suffix, ".zip")

    def test_keine_halbfertige_datei_bleibt_liegen(self) -> None:
        """Eine halbfertige Auskunft, die aussieht wie eine fertige,
        wäre schlimmer als keine."""
        self._packen()
        uebrig = [p.name for p in self.wurzel.glob(".*unfertig")]
        self.assertEqual(uebrig, [])

    def test_der_vorgang_steht_im_journal(self) -> None:
        """Art. 5 Abs. 2 DSGVO – die Rechenschaftspflicht.

        Wer in einem Jahr gefragt wird, ob er fristgerecht Auskunft
        erteilt hat, will auf einen Eintrag zeigen können.
        """
        self._packen()

        with Archive.open(self.pfad, exclusive=False) as archiv:
            eintraege = [
                v for v in archiv.journal.read_all()
                if v.get("art") == "auskunft_art15"
            ]

        self.assertEqual(len(eintraege), 1)
        self.assertEqual(eintraege[0]["betroffen"], "mueller@example.org")
        self.assertEqual(eintraege[0]["nachrichten"], 1)

    def test_die_hashkette_bleibt_heil(self) -> None:
        self._packen()
        with Archive.open(self.pfad, exclusive=False) as archiv:
            self.assertTrue(archiv.verify()["chain_ok"])


class PrivatarchivTest(unittest.TestCase):
    """Ein Privatarchiv nennt keine Aufbewahrungspflicht.

    Wer ausschließlich eigene Mails archiviert, fällt unter die
    Haushaltsausnahme der DSGVO. Ein Begleitblatt, das dort von
    handelsrechtlichen Pflichten spräche, wäre schlicht falsch.
    """

    def test_der_zweck_lautet_anders(self) -> None:
        with tempfile.TemporaryDirectory() as ordner:
            pfad = pathlib.Path(ordner) / "Privatarchiv"
            Archive.create(pfad, mode="privat").close()
            with Archive.open(pfad) as archiv:
                archiv.add(
                    _mail("mueller@example.org", "ich@example.net",
                          "Hallo", 2020, "a"),
                    account="privat", folder="INBOX",
                )
                befund = auskunft.zusammenstellen(
                    archiv, "mueller@example.org"
                )
                befund = auskunft.packen(
                    archiv, befund, pathlib.Path(ordner) / "a.zip"
                )

            with zipfile.ZipFile(befund.ziel) as paket:
                text = paket.read(auskunft.BEGLEITBLATT).decode("utf-8")

        self.assertIn("keiner gesetzlichen", text)
        self.assertNotIn("handels- und steuerrechtlicher", text)


if __name__ == "__main__":
    unittest.main()
