"""Mails aufbewahrungsrechtlich einordnen.

Das Rechenwerk in :mod:`mailburg.core.retention` stand seit dem
2026-08-25 und war getestet – aber es gab keinen Weg, einer Mail eine
Kategorie *zuzuweisen*. Der Index hatte die Spalte, die Suche kannte
``kategorie:``, die Löschsperre fragte sie ab, und niemand konnte sie
setzen. Ein Weg, der vor der letzten Stufe endet.

**Warum das mehr ist als eine Einstellung:** Von der Kategorie hängt ab,
wie lange MailBurg das Löschen bremst – sechs, acht oder zehn Jahre. Und
für ein Geschäftsarchiv ist »wer hat wann was wozu erklärt« Teil der
Verfahrensdokumentation.
"""

from __future__ import annotations

import contextlib
import io
import pathlib
import tempfile
import unittest

from mailburg.core.archive import Archive, ArchiveError, RetentionLocked
from mailburg.core.retention import Category


def _mail(betreff: str, datum: str, kennung: str) -> bytes:
    return (
        f"From: post@example.org\r\n"
        f"To: ich@example.net\r\n"
        f"Subject: {betreff}\r\n"
        f"Date: {datum}\r\n"
        f"Message-ID: <{kennung}@example.org>\r\n"
        f"\r\n"
        f"Inhalt\r\n"
    ).encode()


class EinstufenTest(unittest.TestCase):
    def setUp(self) -> None:
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.pfad = pathlib.Path(self.ordner.name) / "Geschaeftsarchiv"
        Archive.create(self.pfad, mode="geschaeftlich").close()

        with Archive.open(self.pfad) as archiv:
            self.eintrag = archiv.add(
                _mail("Beleg 2019", "Mon, 14 Jan 2019 09:00:00 +0100", "alt"),
                account="firma", folder="INBOX",
            )

    def test_die_vorherige_stufe_kommt_zurueck(self) -> None:
        """Wer hundert Mails versehentlich umstellt, soll zurückkönnen."""
        with Archive.open(self.pfad) as archiv:
            vorher = archiv.classify(self.eintrag.hash, Category.BUCHUNGSBELEG)

        self.assertEqual(vorher, Category.UNBESTIMMT)

    def test_der_vorgang_steht_im_journal(self) -> None:
        """Für ein Geschäftsarchiv ist das Teil der Verfahrensdokumentation.

        Wer später begründen muss, warum eine Mail nach sechs statt acht
        Jahren gelöscht wurde, will auf einen Eintrag zeigen können.
        """
        with Archive.open(self.pfad) as archiv:
            archiv.classify(self.eintrag.hash, Category.HANDELSBRIEF,
                            note="Vertragskorrespondenz")
            eintraege = [
                v for v in archiv.journal.read_all() if v.get("op") == "classify"
            ]

        self.assertEqual(len(eintraege), 1)
        self.assertEqual(eintraege[0]["category"], "handelsbrief")
        self.assertEqual(eintraege[0]["previous"], "unbestimmt")
        self.assertTrue(eintraege[0]["actor"])
        self.assertIn("Vertrag", eintraege[0]["note"])

    def test_die_hashkette_bleibt_heil(self) -> None:
        with Archive.open(self.pfad) as archiv:
            archiv.classify(self.eintrag.hash, Category.BUCHUNGSBELEG)
            self.assertTrue(archiv.verify()["chain_ok"])

    def test_dieselbe_stufe_erzeugt_keinen_zweiten_eintrag(self) -> None:
        """Sonst wächst das Journal bei jedem Durchlauf einer Regel."""
        with Archive.open(self.pfad) as archiv:
            archiv.classify(self.eintrag.hash, Category.PRIVAT)
            archiv.classify(self.eintrag.hash, Category.PRIVAT)
            eintraege = [
                v for v in archiv.journal.read_all() if v.get("op") == "classify"
            ]

        self.assertEqual(len(eintraege), 1)

    def test_eine_fremde_mail_wird_abgewiesen(self) -> None:
        with Archive.open(self.pfad) as archiv:
            with self.assertRaises(ArchiveError):
                archiv.classify("0" * 64, Category.PRIVAT)

    def test_der_treffer_traegt_die_kategorie(self) -> None:
        """Sonst muss der Aufrufer für jeden Treffer einzeln nachfragen."""
        with Archive.open(self.pfad) as archiv:
            archiv.classify(self.eintrag.hash, Category.BUCHUNGSBELEG)
            treffer = archiv.index.search("beleg")

        self.assertEqual(treffer[0].category, "buchungsbeleg")


class FristenwirkungTest(unittest.TestCase):
    """Die Einstufung muss die Löschsperre wirklich steuern.

    Sonst wäre sie Dekoration. Geprüft an einer Mail von Anfang 2019 in
    einem deutschen Geschäftsarchiv: Buchungsbelege acht Jahre,
    Handelsbriefe sechs.
    """

    def setUp(self) -> None:
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.pfad = pathlib.Path(self.ordner.name) / "Geschaeftsarchiv"
        Archive.create(self.pfad, mode="geschaeftlich").close()
        self.roh = _mail("Beleg 2019", "Mon, 14 Jan 2019 09:00:00 +0100", "alt")

    def _versuch(self, kategorie: Category) -> bool:
        """Ob sich die Mail nach dieser Einstufung löschen lässt."""
        with Archive.open(self.pfad) as archiv:
            eintrag = archiv.add(self.roh, account="firma", folder="INBOX")
            archiv.classify(eintrag.hash, kategorie)
            try:
                archiv.delete(eintrag.hash, eintrag.bucket, reason="probe")
                return True
            except RetentionLocked:
                return False

    def test_buchungsbeleg_bleibt_gesperrt(self) -> None:
        self.assertFalse(self._versuch(Category.BUCHUNGSBELEG))

    def test_handelsbrief_ist_nach_sechs_jahren_frei(self) -> None:
        self.assertTrue(self._versuch(Category.HANDELSBRIEF))

    def test_privat_jederzeit(self) -> None:
        self.assertTrue(self._versuch(Category.PRIVAT))

    def test_unbestimmt_wird_wie_die_laengste_pflicht_behandelt(self) -> None:
        """Im Zweifel aufbewahren – die Richtung, die nichts vernichtet."""
        self.assertFalse(self._versuch(Category.UNBESTIMMT))


class BefehlTest(unittest.TestCase):
    """Über die Suche einstufen, nicht Mail für Mail.

    Wer ein Archiv einstuft, hat hunderte Belege vor sich. »Alles von der
    Steuerkanzlei ist Buchungsbeleg« ist eine Regel, die sich als
    Suchausdruck schreiben lässt.
    """

    def setUp(self) -> None:
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.pfad = pathlib.Path(self.ordner.name) / "Geschaeftsarchiv"
        Archive.create(self.pfad, mode="geschaeftlich").close()

        with Archive.open(self.pfad) as archiv:
            for nr in range(3):
                archiv.add(
                    _mail(f"Rechnung {nr}", "Wed, 26 Aug 2026 10:00:00 +0200",
                          f"r{nr}"),
                    account="firma", folder="INBOX",
                )
            archiv.add(
                _mail("Einladung Sommerfest", "Wed, 26 Aug 2026 10:00:00 +0200",
                      "fest"),
                account="firma", folder="INBOX",
            )

    def _rufen(self, *zusatz: str) -> tuple[int, str]:
        from mailburg.__main__ import main

        ausgabe = io.StringIO()
        with contextlib.redirect_stdout(ausgabe):
            code = main(["einstufen", str(self.pfad), *zusatz])
        return code, ausgabe.getvalue()

    def _kategorien(self) -> list[str]:
        with Archive.open(self.pfad, exclusive=False) as archiv:
            return [t.category for t in archiv.index.search("", limit=100)]

    def test_ohne_wirklich_wird_nichts_geaendert(self) -> None:
        """Ein Tippfehler soll nicht hundert Mails für acht Jahre festsetzen."""
        code, text = self._rufen("rechnung", "buchungsbeleg")

        self.assertEqual(code, 0)
        self.assertIn("Nichts geändert", text)
        self.assertEqual(self._kategorien().count("buchungsbeleg"), 0)

    def test_mit_wirklich_greift_es(self) -> None:
        self._rufen("rechnung", "buchungsbeleg", "--wirklich")

        self.assertEqual(self._kategorien().count("buchungsbeleg"), 3)

    def test_nur_die_treffer_der_suche(self) -> None:
        """Das Sommerfest ist kein Buchungsbeleg."""
        self._rufen("rechnung", "buchungsbeleg", "--wirklich")

        self.assertEqual(self._kategorien().count("unbestimmt"), 1)

    def test_der_zweite_aufruf_meldet_ehrlich_null(self) -> None:
        """Sonst hält man den Befehl für wirkungslos – oder für doppelt wirksam."""
        self._rufen("rechnung", "buchungsbeleg", "--wirklich")
        _code, text = self._rufen("rechnung", "buchungsbeleg", "--wirklich")

        self.assertIn("bereits", text)
        self.assertNotIn("Eingestuft: 3", text)

    def test_eine_unsinnige_kategorie_wird_abgewiesen(self) -> None:
        from mailburg.__main__ import main

        fehler = io.StringIO()
        with contextlib.redirect_stderr(fehler):
            code = main(["einstufen", str(self.pfad), "rechnung", "quatsch"])

        self.assertEqual(code, 2)
        self.assertIn("handelsbrief", fehler.getvalue())

    def test_ohne_treffer_passiert_nichts(self) -> None:
        code, text = self._rufen("gibtesnicht", "privat", "--wirklich")

        self.assertEqual(code, 0)
        self.assertIn("Keine Treffer", text)


if __name__ == "__main__":
    unittest.main()
